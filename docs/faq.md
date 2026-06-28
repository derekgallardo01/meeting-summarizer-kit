# FAQ

## How is this different from Otter.ai / Fireflies.ai / tl;dv?

Those are **products** — hosted SaaS that joins your meetings, records,
transcribes, and produces auto-summaries. They charge per-meeting,
own the transcript, and lock you into their summary format.

This kit is **the summarization layer alone**, designed for when you
**already have** transcripts (from any of those services, or from
Zoom/Teams native recording) and want:

- Self-hosted summarization (transcripts never leave your infra)
- Custom recap format
- Structured action items piped to your task tracker (not Otter's UI)
- Eval-gated CI so changes don't break the recap format

The kit reads Otter's JSON export format natively. Use Otter for
the recording + transcript; use this kit for the recap. Pay once.

## Why not just use one big LLM prompt?

You can. Naive LLM-only summarizers fail in three predictable ways
this kit fixes:

1. **Owner attribution for first-person commitments.** When Bob says
   "I'll draft the spec by Friday", a naive prompt often returns the
   action with no owner or owner="I". The kit's regex extractor
   knows to map "I" → current speaker. A well-prompted LLM can do
   this too, but the regex extractor gets it right deterministically
   and for free.
2. **Hallucinated action items.** LLMs sometimes invent action items
   that no one agreed to. The kit's regex extractor is conservative
   — if there's no assignment verb, it's not an action item, period.
3. **Format drift.** "Please summarize this meeting" returns
   different shapes across model upgrades. The kit's mechanical
   4-section structure is the same every time.

For the prose summary itself, the LLM is better — that's why the
LLM backend swap exists. **Hybrid is the right answer**: regex
extractor for action items + decisions; LLM for the prose summary.

## Why four formats and not more?

Plain text, VTT, SRT, and Otter-style JSON cover 90%+ of what's in
the wild:

- **Plain text** — human notes, AI-generated transcripts that lost
  formatting, Microsoft Teams "Get-Transcript" output
- **VTT** — Zoom Cloud Recording, Microsoft Teams cloud recording,
  Google Meet (Workspace Premium)
- **SRT** — most desktop transcription tools (Whisper UI wrappers,
  Descript, Riverside, etc.)
- **Otter JSON** — Otter.ai, Fireflies.ai, Grain (their JSON exports
  share the speaker-attributed segment shape)

Adding a 5th format is one new parser function +
[a detect_format branch](customization.md#add-a-new-transcript-format).
Common asks would be AssemblyAI's utterance JSON or Deepgram's
diarized output.

## Does it handle audio files directly?

No — the kit operates on transcripts. For audio:

1. **Whisper (local)** — `whisper audio.mp3 --output_format vtt` →
   feed the VTT to this kit
2. **OpenAI Whisper API** — `client.audio.transcriptions.create(...)`
   → pass the response to `parse()`
3. **AssemblyAI / Deepgram / AWS Transcribe** — hosted services that
   handle diarization too; export to JSON and feed in

The kit + Whisper combo runs entirely offline on your laptop. That's
the privacy-preserving combo for sensitive meetings (legal, HR,
M&A) where you don't want transcripts sent to a SaaS.

## What if the transcript has no speaker labels?

The parser handles this — `Segment.speaker` becomes empty string.
The first-person extractor won't fire (it needs a known speaker to
attribute to), but the third-person and request patterns still work.

For unattributed transcripts, run a diarizer upstream
(`pyannote-audio` is the OSS option, AssemblyAI/Deepgram are the
hosted options). The kit's parser accepts the diarized output via
the Otter JSON format.

## How do I localize for non-English meetings?

The pattern dictionaries (decision verbs, assignment verbs, due-date
phrases, first-person patterns) are all hardcoded English. For Spanish:

```python
# Copy extractor.py → extractor_es.py
_FIRST_PERSON_PATTERNS_ES = [
    re.compile(r"\b(?:Yo\s+)?voy\s+a\s+([a-záéíóú][^.!?]*)", re.I),
    re.compile(r"\bharé\s+([a-záéíóú][^.!?]*)", re.I),
]
_ASSIGNMENT_VERBS_ES = {"enviar", "redactar", "revisar", ...}
```

Detect language from the transcript and dispatch to the right
extractor. The kit doesn't ship multi-language because each language
needs its own pattern library.

## Can I export to Linear / Asana / Jira?

The kit emits structured `ActionItem(owner, description, due, evidence)`.
Your integration code maps `owner` to the user ID in your system
and pushes the item:

```python
import requests

LINEAR_API = "https://api.linear.app/graphql"

for item in recap.action_items:
    requests.post(LINEAR_API, headers={"Authorization": f"Bearer {token}"},
        json={"query": """
            mutation { issueCreate(input: {
                title: $title, assigneeId: $assignee, dueDate: $due
            }) { success } }
        """, "variables": {
            "title": item.description,
            "assignee": owner_to_linear_id(item.owner),
            "due": parse_due_date(item.due),
        }})
```

Owner-to-user-id mapping is the integration boundary. Often a
simple dict (`{"Bob": "user-uuid"}`) is enough.

## How do I de-dupe across meetings?

If the same action item shows up in multiple meetings ("we need to
ship the dashboard"), you'll get duplicate task creations. Two
options:

1. **Track in your task tracker** — query before creating: "is there
   an open task with this description?"
2. **Maintain a recent-actions cache** — keep a hash of recent action
   items, skip duplicates within a time window:

```python
import hashlib, json
from datetime import datetime, timedelta

def action_hash(item):
    return hashlib.sha256(
        f"{item.owner}|{item.description.lower()}".encode()
    ).hexdigest()

recent = {}  # hash -> created_at
for item in recap.action_items:
    h = action_hash(item)
    if h in recent and (datetime.utcnow() - recent[h]) < timedelta(days=7):
        continue
    create_task(item)
    recent[h] = datetime.utcnow()
```

## How does the kit handle very long meetings?

`Transcript` is in-memory. For a 4-hour meeting that's maybe 200KB
of text — well within Python memory limits. For genuinely huge
transcripts (multi-day workshops), chunk the transcript and call
`summarize` per chunk, then merge:

```python
def chunk_and_summarize(transcript, chunk_seconds=1800):  # 30-min chunks
    chunks = chunk_by_time(transcript, chunk_seconds)
    recaps = [Summarizer().summarize(c) for c in chunks]
    return merge_recaps(recaps)
```

Merge logic: concat summaries, dedupe action items, append decisions
+ open questions chronologically.

## Why isn't the open-question heuristic better?

The current heuristic is "?-ended sentence where the next segment is
short or also a question." It misses cases like "what about X?" where
the answer is in the same segment.

The LLM backend can do much better here — pass the transcript and
ask "list questions raised that weren't substantively answered."
The kit's template heuristic is the deterministic baseline; the LLM
swap is where this section's quality jumps.

## What's the cost story for the LLM backend?

A 1-hour meeting is roughly 6,000-9,000 tokens. With overhead and
output:

- Claude Haiku: ~$0.001 per meeting
- Claude Sonnet: ~$0.025 per meeting
- Claude Opus: ~$0.20 per meeting

For an org running 50 meetings/week, Haiku is ~$3/month. The
template backend is $0/month if you only need structured pieces.
Pick based on whether the prose quality matters more than the cost
(usually: Haiku is enough).
