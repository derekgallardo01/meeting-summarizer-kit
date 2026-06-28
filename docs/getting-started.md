# Getting started

Five minutes to summarizing a meeting on your machine, zero API keys.

## Install

```bash
git clone https://github.com/derekgallardo01/meeting-summarizer-kit.git
cd meeting-summarizer-kit
pip install -e .
```

Stdlib-only on the default path. `pip install -e ".[llm]"` adds the
optional `anthropic` dependency for the LLM-backed summarizer.

## Run the demo

```bash
meeting-summarizer demo
```

Four bundled transcripts (one per supported format), each parsed +
summarized + action-items extracted.

## Summarize one transcript

```bash
meeting-summarizer summarize fixtures/01-product-sync.txt
```

Human-readable output: speakers, segment count, the 4-section recap.

```bash
meeting-summarizer summarize fixtures/01-product-sync.txt --markdown
```

Rendered as standard meeting-recap markdown (ready to paste into a
Notion / Confluence / shared doc).

```bash
meeting-summarizer summarize fixtures/01-product-sync.txt --json
```

Machine-readable JSON with full structured detail (for piping into
another tool).

## List supported formats

```bash
meeting-summarizer list-formats
```

## Run the tests

```bash
python -m pytest -q
```

39 tests across the parser, extractor, and summarizer.

## Run the evals

```bash
python evals/run.py
```

Two suites:

1. **Recap-quality** — assertions on the rendered markdown (required
   section headers, expected topic mentions).
2. **Action items** — recall of expected (owner, description) pairs.

CI gates on both.

## Use your own transcript

```bash
# Auto-detect format
meeting-summarizer summarize path/to/your-transcript.vtt

# Force format if auto-detect picks wrong
meeting-summarizer summarize path/to/notes.txt --format text
```

If action items aren't being extracted correctly:

1. **Look at the speaker attribution** — is the transcript using
   "Speaker: text" format consistently? If not, the parser falls
   back to no speaker, which breaks the first-person extractor.
2. **Add an assignment verb** — if your team says "I'll handle it"
   (no specific verb), extend `_ASSIGNMENT_VERBS` in
   `src/meeting_summarizer/extractor.py`.

## Wire to your meeting platform

The parser is the integration point:

```python
from meeting_summarizer.transcript import parse_eml_bytes  # for raw bytes
from meeting_summarizer.transcript import parse_file       # for files
from meeting_summarizer.transcript import parse            # for strings

# Zoom Cloud Recording (.vtt downloaded automatically)
transcript = parse_file("zoom-recording.vtt")

# Microsoft Teams (via Graph API):
mime_bytes = graph_client.me.online_meetings[id].transcripts[tid].content
transcript = parse(mime_bytes.decode("utf-8"))

# Otter.ai JSON export:
transcript = parse_file("otter-export.json")
```

Everything downstream works the same regardless of source.

## Wire the Claude summarizer

1. `pip install -e ".[llm]"`
2. `export ANTHROPIC_API_KEY=sk-...`
3. `export MEETING_SUMMARIZER_LLM=claude`
4. Implement `_summarize_claude` in
   [src/meeting_summarizer/summarizer.py](../src/meeting_summarizer/summarizer.py)
   per the docstring sketch.

The template summarizer keeps the structure correct; the LLM writes
better prose summaries. Pair them: template for the structured pieces
(decisions, action items), LLM for the freeform summary.

## Next steps

- [Architecture](architecture.md) — parser/summarizer/extractor design
- [Customization](customization.md) — add formats, patterns, backends
- [Evaluation](evaluation.md) — the two eval suites in detail
