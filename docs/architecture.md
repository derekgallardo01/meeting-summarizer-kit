# Architecture

Three components, clean separation:

1. **Parser** (`transcript.py`) — N-format → one shape.
2. **Extractor** (`extractor.py`) — pulls structured action items.
3. **Summarizer** (`summarizer.py`) — orchestrates the 4-section recap.

The CLI glues them together. Each component is independently testable.

## End-to-end flow

```
Raw bytes / file
    -> parse() | parse_file()      (auto-detects format)
        -> Transcript               (segments with speaker + text + timestamps)
        -> Summarizer.summarize()
            -> extract_action_items()    (regex extractor)
            -> _extract_summary()         (first 2 substantive sentences)
            -> _extract_decisions()       (sentences with decision verbs)
            -> _extract_open_questions()  (?-ended sentences without answers)
        -> Recap (4 sections)
    -> recap.to_markdown()          (rendered output)
```

## Parser layer

Four formats, one shape. Each parser produces a list of `Segment`:

```python
Segment(
    speaker="Alice Chen",       # may be "" for formats without speaker tracking
    text="Let's start the meeting.",
    start_seconds=0.0,
    end_seconds=3.5,
)
```

Per-format quirks:

- **Text** — `Speaker: utterance` per line. Continuation lines (no
  `:` prefix) attach to the previous segment.
- **VTT** — Cue blocks separated by blank lines. Speaker pulled from
  `<v Name>` tag if present, else empty.
- **SRT** — Numbered cue blocks. Some exports embed `Speaker:` inside
  the cue text; parser extracts it the same way the text parser does.
- **Otter JSON** — supports both `{"segments": [...]}` and
  `{"transcript": [...]}` shapes; field names normalized
  (`speaker`/`speaker_name`, `text`, `start`/`start_time`).

Format auto-detection from first 500 chars. Override with the
`source_format=` arg if detection picks wrong.

## Extractor (the first-person trick)

Most action items in transcripts follow one of three patterns:

| Pattern | Example | Owner |
|---|---|---|
| First-person commitment | "I'll draft the spec by Friday" | **speaker of segment** |
| Third-person commitment | "Bob will draft the spec" | "Bob" |
| Direct request | "Carol, can you review?" | "Carol" |

The first-person case is what naive regex misses. The extractor
takes `current_speaker=seg.speaker` for every sentence so it knows
who to attribute "I'll" to. Without this, you get garbage like
`[I] draft the spec` in the recap.

For each match the extractor:

1. **Checks for an assignment verb** in the description (`send`,
   `draft`, `schedule`, `follow up`, `review`, etc.). Without a verb,
   it's not an action item even if structurally matched.
2. **Extracts a due date** if a temporal phrase is present
   (`by Friday`, `before EOW`, `tomorrow`, ISO dates).
3. **Strips the due phrase from the description** so it doesn't
   appear twice in the output.
4. **Dedupes** by description (a topic discussed twice doesn't
   produce two action items).

## Summarizer (4-section recap)

Sections + extraction logic:

| Section | How it's extracted |
|---|---|
| **Summary** | First 2 substantive sentences (passes a stopword filter, has ≥4 non-filler words) |
| **Decisions** | Sentences containing a decision verb (`agreed`, `decided`, `approved`, `resolved`, etc.) |
| **Action items** | Delegated to `extract_action_items()` |
| **Open questions** | `?`-ending sentences where the next segment is short or also a question (heuristic for "didn't get answered") |

The template summarizer is intentionally simple. The LLM swap
(`_summarize_claude`) gives much better prose summaries while
preserving the structured pieces (decisions, action items, open
questions) the regex extractor already gets right.

## Why the LLM swap is one method

```python
def summarize(self, transcript):
    if self.backend == "claude":
        return self._summarize_claude(transcript)
    return self._summarize_template(transcript)
```

Both return a `Recap` with the same shape. The CLI, the eval harness,
the `to_markdown()` renderer — none of them know which backend
produced the recap.

The production hybrid pattern most teams want:

```python
def hybrid_summarize(self, transcript):
    # Use the regex extractor for structured pieces (reliable + free)
    action_items = extract_action_items(transcript)
    decisions = _extract_decisions(transcript)

    # Use the LLM for the prose summary only (writes better English)
    summary_text = self._llm_summarize_only(transcript)

    return Recap(
        summary=summary_text,
        decisions=decisions,
        action_items=action_items,
        open_questions=_extract_open_questions(transcript),
        backend="hybrid",
    )
```

About 5 lines of glue once `_llm_summarize_only` is wired. The kit
doesn't ship this as a default because the template backend is
deterministic and works in CI.

## Why structured action items matter

A meeting recap is only useful if the action items have:

1. **An owner** — "someone should do X" gets ignored
2. **A description with a verb** — "X is important" isn't an action
3. **A due date** — "soon" doesn't compel action

The regex extractor catches all three when they're spoken. The
common failure modes it doesn't catch (and where the LLM would help):

- **Implied verbs**: "I'll handle it" needs context from previous
  segments to know what "it" is
- **Pronouns**: "Alice will look at it" — without the prior context,
  "it" is opaque
- **Multi-sentence actions**: "I'll send the deck. Probably tomorrow,
  maybe Friday." — two sentences, one action

For these, a hybrid extractor (regex first, LLM fallback for
low-context cases) wins on both cost and quality.

## What's deliberately NOT in the kit

- **Real-time / streaming** — the parser handles complete transcripts.
  For live meetings, buffer chunks and re-summarize incrementally
  (call `Summarizer.summarize` per chunk; merge recaps).
- **Speaker diarization** — the parser uses whatever speaker labels
  the transcript already has. For unattributed transcripts, run a
  diarizer (pyannote, AssemblyAI) upstream.
- **Audio → transcript** — out of scope. Use Whisper / AssemblyAI /
  Deepgram, then feed the output to this kit.
- **CRM integration** — the kit produces structured action items.
  Your downstream system pushes them to Linear / Asana / Salesforce.
