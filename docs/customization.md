# Customization

How to shape the kit for a real engagement.

## Add a new transcript format

Edit `src/meeting_summarizer/transcript.py`. Add a new `_parse_xyz`
function that returns `list[Segment]`, then wire it into `detect_format`
and `parse`:

```python
def _parse_assembly_ai(content: str) -> list[Segment]:
    data = json.loads(content)
    return [
        Segment(
            speaker=u.get("speaker") or "",
            text=u.get("text", ""),
            start_seconds=u.get("start", 0) / 1000,  # ms -> s
            end_seconds=u.get("end", 0) / 1000,
        )
        for u in data.get("utterances", [])
    ]

def detect_format(content: str) -> str:
    # ... existing detection ...
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "utterances" in data:
            return "assembly_ai"
    except json.JSONDecodeError:
        pass
    # ...

def parse(content, source_format=None, ...):
    # ...
    elif fmt == "assembly_ai":
        segments = _parse_assembly_ai(content)
    # ...
```

That's it. The summarizer, extractor, eval harness, and CLI all work
with the new format automatically.

## Add a new action item pattern

Edit `src/meeting_summarizer/extractor.py`. Three pattern lists to
choose from based on what you're matching:

```python
# Add to _FIRST_PERSON_PATTERNS if owner == current speaker
_FIRST_PERSON_PATTERNS = [
    # ... existing ...
    re.compile(r"\bI\s+commit\s+to\s+([a-z][^.!?]*)", re.M),
]

# Add to _THIRD_PERSON_PATTERNS if owner is named explicitly
_THIRD_PERSON_PATTERNS = [
    # ... existing ...
    re.compile(r"\b([A-Z][a-zA-Z\-']+)\s+volunteers?\s+to\s+([a-z][^.!?]*)", re.M),
]

# Add to _REQUEST_PATTERNS if it's a direct ask
_REQUEST_PATTERNS = [
    # ... existing ...
    re.compile(r"([A-Z][a-zA-Z\-']+),\s*would\s+you\s+([a-z][^.!?]*)", re.M),
]
```

Add a test case to lock in the new behavior:

```python
def test_new_pattern_extracted():
    t = parse("Bob: I commit to shipping the feature by Friday.")
    items = extract_action_items(t)
    assert len(items) == 1
    assert items[0].owner == "Bob"
```

## Add a new assignment verb

```python
_ASSIGNMENT_VERBS = {
    # ... existing ...
    "merge", "approve", "kick off", "stand up", "spin up",
}
```

Without an assignment verb, sentences that structurally match an
action item pattern get filtered out. Adding verbs widens the catch
net.

## Add a new due-date pattern

```python
_DUE_PATTERNS = [
    # ... existing ...
    re.compile(r"in\s+(\d+)\s+(days?|weeks?|months?)", re.I),  # "in 3 days"
    re.compile(r"by\s+(Q[1-4])\b"),                            # "by Q3"
]
```

Pattern's first capture group is the due-date text that gets
attached to the action item.

## Customize the decision verbs

The summarizer captures sentences containing any of:

```python
_DECISION_VERBS = [
    "agreed", "decided", "approved", "resolved", "settled on",
    "will go with", "going with", "chose to", "concluded", "ratified",
]
```

Add or remove based on how your team talks. For more conservative
extraction, remove the looser ones (`chose to`, `going with`).

## Change the summary length

`_extract_summary` returns 2 sentences. To return more:

```python
def _extract_summary(transcript, n_sentences=2):
    # ... iterate, collect n_sentences instead of 2 ...
```

For a 3-bullet executive summary, pass `n_sentences=3`.

## Localize the patterns (non-English meetings)

The bundled patterns are English-only. For Spanish:

```python
_FIRST_PERSON_PATTERNS_ES = [
    re.compile(r"\b(?:Yo\s+)?voy\s+a\s+([a-záéíóú][^.!?]*)", re.I),  # "voy a hacer..."
    re.compile(r"\bharé\s+([a-záéíóú][^.!?]*)", re.I),                # "haré..."
]
```

Plus a Spanish `_ASSIGNMENT_VERBS` and `_DUE_PATTERNS`. Detect
language from the transcript and dispatch to the right pattern set.

The kit doesn't ship multi-language because each language needs its
own pattern library and verb set. For a real localization project,
copy the file once per language and dispatch by language code.

## Wire the Claude summarizer

```python
def _summarize_claude(self, transcript):
    from anthropic import Anthropic
    client = Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=(
            "You write meeting recaps. Return JSON with keys: "
            "summary (string, 2-3 sentences), "
            "decisions (list of strings), "
            "action_items (list of {owner, description, due}), "
            "open_questions (list of strings). "
            "Use the current speaker as owner for 'I'll' / 'I will' commitments."
        ),
        messages=[{"role": "user", "content": transcript.full_text()}],
    )
    import json
    from .extractor import ActionItem
    data = json.loads(response.content[0].text)
    return Recap(
        summary=data["summary"],
        decisions=data["decisions"],
        action_items=[ActionItem(**a) for a in data["action_items"]],
        open_questions=data["open_questions"],
        backend="claude",
    )
```

About 25 lines. Tests pin the backend to `template` so they stay
green.

## Hybrid (template + LLM) for best of both

```python
def hybrid_summarize(self, transcript):
    # Use regex extractor for action items (predictable + free)
    from .extractor import extract_action_items
    action_items = extract_action_items(transcript)

    # Use LLM only for the prose summary (writes better English)
    summary_text = self._llm_summarize_only(transcript)

    return Recap(
        summary=summary_text,
        decisions=_extract_decisions(transcript),
        action_items=action_items,
        open_questions=_extract_open_questions(transcript),
        backend="hybrid",
    )
```

`_llm_summarize_only` is just a Claude call asking for a 2-3 sentence
summary. ~$0.0005 per meeting at Haiku rates.

## Persist recaps for later search

`recap.to_markdown()` is your storage payload:

```python
import json, time

record = {
    "meeting_id": derived_from_transcript,
    "ts": int(time.time()),
    "source_format": transcript.source_format,
    "speakers": transcript.speakers(),
    "duration_seconds": transcript.duration_seconds(),
    "recap_markdown": recap.to_markdown(),
    "action_items": [asdict(a) for a in recap.action_items],
}
db.insert("meetings", record)
```

Pair with [rag-over-docs-kit](https://github.com/derekgallardo01/rag-over-docs-kit)
to make recaps searchable ("what did we decide about pricing in the
last 6 months?").

## Pipe action items to a task tracker

```python
import requests

for item in recap.action_items:
    requests.post(LINEAR_API, json={
        "title": item.description,
        "assignee": resolve_email(item.owner),
        "dueDate": parse_due_date(item.due),
        "labels": ["meeting-action"],
    })
```

Owner string ("Bob") → email via a directory lookup. Due string
("Friday") → ISO date via `dateparser` or similar. The kit emits
the structured data; your integration layer handles the mapping to
your tools.
