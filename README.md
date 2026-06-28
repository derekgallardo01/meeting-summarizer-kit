# Meeting summarizer kit

[![CI](https://github.com/derekgallardo01/meeting-summarizer-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/derekgallardo01/meeting-summarizer-kit/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#) [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/derekgallardo01/meeting-summarizer-kit)

**Docs:** [Getting started](docs/getting-started.md) · [Architecture](docs/architecture.md) · [Customization](docs/customization.md) · [Evaluation](docs/evaluation.md) · [Diagrams](docs/diagrams.md) · [FAQ](docs/faq.md)

**Live demo:** [derekgallardo01.github.io/meeting-summarizer-kit](https://derekgallardo01.github.io/meeting-summarizer-kit/) — four bundled transcripts in four different formats, with full four-section recaps including structured action items, regenerated on every push.

Parse meeting transcripts in **four common formats** (plain text,
WebVTT, SubRip, Otter-style JSON), generate a **four-section recap**
(Summary / Decisions / Action items / Open questions), extract
**structured action items** with owners + due dates.

Default backend is deterministic — template summarizer + regex-based
action extraction. No API keys, no network. The seam is one method
(`Summarizer._summarize_claude`); set `MEETING_SUMMARIZER_LLM=claude`
to route through Claude for better summaries while keeping the
structured-extraction guarantees.

```bash
pip install -e .
meeting-summarizer demo                                    # all 4 fixtures
meeting-summarizer summarize fixtures/01-product-sync.txt  # human-readable
meeting-summarizer summarize fixtures/01-product-sync.txt --markdown
meeting-summarizer summarize fixtures/01-product-sync.txt --json
meeting-summarizer list-formats
```

```bash
python -m pytest -q     # 39 unit tests
python evals/run.py     # 5 recap-quality cases + 4 action-item cases (10 expected items, 100% recall)
```

Stdlib-only Python on the default path (uses `email.parser`-style
stdlib techniques). `anthropic` is an optional extra.

## Run in Docker

```bash
docker build -t meeting-summarizer .
docker run --rm meeting-summarizer                                # `meeting-summarizer demo`
docker run --rm meeting-summarizer pytest -q                      # tests
docker run --rm -v $(pwd)/transcripts:/in meeting-summarizer \
    meeting-summarizer summarize /in/my-recording.vtt --markdown
```

## What it's for

Every team has the same problem: someone takes notes (badly), the AI
summarizer hallucinates action items that nobody actually agreed to,
the action items don't say who owns them or when they're due, and
two weeks later no one can remember what the meeting decided.

This kit solves the right pieces:

- **Multi-format parser** — Zoom (.vtt), Otter (.json), bare typed
  minutes (.txt), and most desktop transcription tools (.srt). One
  shape out (`Transcript` with speaker-attributed segments).
- **Structured action items** — owner + description + due date,
  extracted via patterns that catch first-person commitments
  ("I'll draft the spec by Friday" → owner = current speaker, not
  the literal "I"). This is the bit most LLM-only summarizers get
  wrong.
- **Four-section recap** — Summary, Decisions, Action items, Open
  questions. Sections are mechanical so a stakeholder can quickly
  find what they care about.
- **Two eval suites** — recap quality (rendered markdown has required
  sections + content) and action-item recall (every expected item
  appears in the extracted list). CI gates on both.

## Supported transcript formats

| Format | Source | Detection |
|---|---|---|
| `text` | Human-typed minutes | "Speaker Name: utterance" per line |
| `vtt` | Zoom / Teams / Google Meet recordings | starts with `WEBVTT` |
| `srt` | Most desktop transcription tools | starts with digit + timestamp |
| `otter_json` | Otter.ai, Fireflies.ai, Grain exports | JSON with `segments` or `transcript` key |

Format is auto-detected from the content. Force a format with
`--format <name>` if detection picks the wrong one.

## What `meeting-summarizer demo` looks like

```
01-product-sync.txt           format=text         18 segments  1 decisions  5 actions  1 questions
02-zoom-recording.vtt         format=vtt          13 segments  2 decisions  4 actions  3 questions
03-customer-call.srt          format=srt          12 segments  0 decisions  3 actions  2 questions
04-otter-transcript.json      format=otter_json   11 segments  1 decisions  4 actions  2 questions
```

For the full per-meeting recap, run `meeting-summarizer summarize <path> --markdown`:

```
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

## The first-person trick

The extractor treats `I'll <verb>` and `I will <verb>` specially:
the owner is the **current speaker** of the segment, not the literal
word "I". So when Bob says "I'll draft the spec by Friday", the
extracted action item is `[Bob] draft the spec (due Friday)` — not
`[I] draft the spec (due Friday)` which is what naïve regex would
produce.

This is where naive LLM-only summarizers fail too: they often
correctly identify the action but lose the owner attribution because
the prompt didn't pin "current speaker" → "owner" mapping.

## Architecture

```mermaid
flowchart LR
    F[Transcript file<br/>.txt / .vtt / .srt / .json] --> P["transcript.parse_file()"]
    P --> T["Transcript<br/>(segments with speaker + text + timestamps)"]
    T --> S["Summarizer.summarize(transcript)"]
    S --> SUM[Summary<br/>first 2 substantive sentences]
    S --> DEC["Decisions<br/>(lines with 'agreed' / 'decided' / ...)"]
    S --> AC["extract_action_items(transcript)"]
    AC --> AI["Action items<br/>(owner + description + due)"]
    S --> OQ[Open questions<br/>(unanswered ?-ended sentences)]
    SUM --> R[Recap]
    DEC --> R
    AI --> R
    OQ --> R
    R --> MD["recap.to_markdown()"]
```

## What's inside

| Path | Purpose |
|---|---|
| `src/meeting_summarizer/transcript.py` | 4-format parser (text/vtt/srt/otter_json) |
| `src/meeting_summarizer/extractor.py` | Action item extractor (first-person + third-person + request patterns) |
| `src/meeting_summarizer/summarizer.py` | Four-section recap generator + Claude swap point |
| `src/meeting_summarizer/cli.py` | `summarize / demo / list-formats` |
| `fixtures/*.{txt,vtt,srt,json}` | 4 bundled transcripts (one per format) |
| `tests/` | 39 pytest tests across parser + extractor + summarizer |
| `evals/recap-quality.json` | 5 recap rubric cases |
| `evals/action-items.json` | 4 cases, 10 expected items total |
| `evals/run.py` | Eval harness with recall reporting |
| `pyproject.toml` | Package + `meeting-summarizer` script entry |

## Wire to your real meeting platform

The parser layer is the integration point. Each platform exports the
same transcript shape; you just point the parser at it:

- **Zoom Cloud Recording** — `.vtt` is downloaded automatically; just
  `parse_file("recording.vtt")`.
- **Microsoft Teams** — `Get-Transcript` cmdlet (or Graph API
  `/me/onlineMeetings/{id}/transcripts`) returns VTT; same parser.
- **Google Meet** — Workspace Premium exports `.vtt`; same parser.
- **Otter.ai / Fireflies.ai / Grain** — export JSON; pass to
  `parse(content)` (autodetects).

Everything downstream (summarizer, extractor, eval harness) doesn't
change regardless of source.

## Wire the Claude backend for better summaries

The template summarizer is deterministic and CI-friendly but it's
not as good at writing prose summaries as a real LLM. Wire Claude
for the prose, keep the regex extractor for the structured pieces:

1. `pip install -e ".[llm]"`
2. `export ANTHROPIC_API_KEY=sk-...`
3. `export MEETING_SUMMARIZER_LLM=claude`
4. Implement `_summarize_claude` in
   [src/meeting_summarizer/summarizer.py](src/meeting_summarizer/summarizer.py)
   per the docstring sketch (~20 lines).

Tests pin the backend to `template` so they stay green while you
wire the LLM path.

## Companion repos

- [prompt-registry-kit](https://github.com/derekgallardo01/prompt-registry-kit) — use this kit's recap templates as registered prompts with eval-gated promotion. Lock in template changes; A/B-test summary styles.
- [email-triage-automation](https://github.com/derekgallardo01/email-triage-automation) — pair with this kit: triage an inbox, draft replies, and summarize meetings - the two most common SMB "automate my comms" asks.
- [document-classifier-kit](https://github.com/derekgallardo01/document-classifier-kit) — once you have meeting recaps, classify them (sales call, support escalation, internal sync, etc.) and route to the right queue.
- [rag-over-docs-kit](https://github.com/derekgallardo01/rag-over-docs-kit) — index your meeting recaps; ask "what did we decide about X" across the last 6 months of meetings.
