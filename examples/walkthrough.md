# Walkthrough

End-to-end tour: from a recorded meeting to structured action items
in your task tracker.

## Step 1: Get the transcript

From wherever your team meets:

| Source | Output | What to do |
|---|---|---|
| Zoom Cloud Recording | `.vtt` file | Download from Zoom dashboard |
| Microsoft Teams | `.vtt` via Graph API | `GET /me/onlineMeetings/{id}/transcripts/{tid}/content` |
| Otter.ai | JSON export | Settings → Export → JSON |
| Whisper (local) | `.vtt` | `whisper audio.mp3 --output_format vtt` |
| Human notes | `.txt` | Type "Speaker Name: utterance" per line |

For this walkthrough, use a bundled fixture:

```bash
cp fixtures/01-product-sync.txt my-meeting.txt
```

## Step 2: Parse + summarize

```python
from meeting_summarizer.transcript import parse_file
from meeting_summarizer.summarizer import Summarizer

transcript = parse_file("my-meeting.txt")
recap = Summarizer().summarize(transcript)
```

`recap` is a structured `Recap`:

```python
Recap(
    summary="Okay, let's get started. The main topic today is the Q3 roadmap.",
    decisions=["Agreed on the dashboard."],
    action_items=[
        ActionItem(owner="Bob", description="draft the dashboard spec and circulate it for review", due="Friday", evidence="..."),
        ActionItem(owner="Carol", description="set up a customer panel for the integrations refresh", due="next Wednesday", evidence="..."),
        ActionItem(owner="Carol", description="reach out to the top five accounts", due="", evidence="..."),
        ActionItem(owner="Alice", description="loop in mobile and get an answer", due="end of week", evidence="..."),
        ActionItem(owner="Alice", description="send the updated launch dates to the team", due="tomorrow", evidence="..."),
    ],
    open_questions=["One more thing - what should we do about the feedback form on the help page?"],
    backend="template",
)
```

## Step 3: Render to markdown

```python
print(recap.to_markdown())
```

```markdown
# Meeting recap

## Summary

Okay, let's get started. The main topic today is the Q3 roadmap.

## Decisions

- Agreed on the dashboard.

## Action items

- [Bob] draft the dashboard spec and circulate it for review (due Friday)
- [Carol] set up a customer panel for the integrations refresh (due next Wednesday)
- [Carol] reach out to the top five accounts
- [Alice] loop in mobile and get an answer (due end of week)
- [Alice] send the updated launch dates to the team (due tomorrow)

## Open questions

- One more thing - what should we do about the feedback form on the help page?
```

Paste into your team's Notion / Confluence / Slack canvas. Done in
~5 seconds vs ~10 minutes of manual note-taking.

## Step 4: Pipe action items to your task tracker

```python
import requests
from dataclasses import asdict

LINEAR_TOKEN = "lin_api_..."

def owner_to_linear_id(name: str) -> str:
    # Maintain a dict in your codebase
    return {"Bob": "uuid-bob", "Carol": "uuid-carol", "Alice": "uuid-alice"}.get(name)

for item in recap.action_items:
    assignee_id = owner_to_linear_id(item.owner)
    if not assignee_id:
        continue  # owner not in our team - skip
    requests.post("https://api.linear.app/graphql",
        headers={"Authorization": f"Bearer {LINEAR_TOKEN}"},
        json={
            "query": "mutation { issueCreate(input: {title: $title, assigneeId: $aid}) { success } }",
            "variables": {
                "title": f"{item.description} (from meeting recap)",
                "aid": assignee_id,
            },
        })
```

Action items in Linear within seconds of the meeting ending. No
manual transcription, no "wait, what did I commit to?" Slack threads
the next day.

## Step 5: Persist for later search

```python
import json, time
from dataclasses import asdict

record = {
    "meeting_id": "weekly-product-sync-2026-06-28",
    "ts": int(time.time()),
    "speakers": transcript.speakers(),
    "duration_seconds": int(transcript.duration_seconds()),
    "recap_markdown": recap.to_markdown(),
    "action_items": [asdict(a) for a in recap.action_items],
}
# Insert into your meeting-history DB (Postgres, Cosmos, etc.)
db.meetings.insert(record)
```

Pair with [rag-over-docs-kit](https://github.com/derekgallardo01/rag-over-docs-kit):
index every recap, then ask "what did we decide about pricing in
the last 6 months?" across all meeting histories.

## When the extraction is wrong

Run `meeting-summarizer summarize` and inspect:

```
$ meeting-summarizer summarize my-meeting.txt

  ACTION ITEMS (3):                  <-- expected 5
    - [Bob] draft the spec
    - [Carol] set up panel
    - [Alice] send dates
```

Missing 2? Two diagnostic paths:

1. **Look at the raw transcript** — did the missing actions use a
   pattern the extractor doesn't know? Add it to
   `_FIRST_PERSON_PATTERNS` / `_THIRD_PERSON_PATTERNS` /
   `_REQUEST_PATTERNS`.

2. **Look at the assignment verb gate** — does the missing action use
   a verb not in `_ASSIGNMENT_VERBS`? Add it.

Then add the missing case to `evals/action-items.json` so the
regression can't come back.

## Step 6: Wire the Claude backend for better prose

If the template summary is too terse:

```bash
pip install -e ".[llm]"
export ANTHROPIC_API_KEY=sk-...
export MEETING_SUMMARIZER_LLM=claude
```

Implement `_summarize_claude` (~25 lines per the docstring).

The structured pieces (decisions, action items) stay regex-extracted
for reliability + cost; only the prose summary uses the LLM. ~$0.001
per meeting at Haiku rates.

## The whole loop, every meeting

```
Meeting ends → transcript auto-downloads from Zoom/Teams/Otter
            → parse_file()
            → Summarizer().summarize()
            → recap.to_markdown() → paste into team doc
            → pipe action items to Linear/Asana/Jira
            → persist recap for later RAG search

  Total time: ~5 seconds per meeting + your task tracker's API latency.
```
