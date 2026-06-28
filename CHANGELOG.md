# Changelog

Notable changes to the meeting summarizer kit. Dates are when the
change landed on `main`.

## 2026-06-28 — Initial public release (v1.0.0)
- `transcript.py` — 4-format parser (text / VTT / SRT / Otter-style
  JSON) with auto-detection; speaker-attributed `Segment` shape;
  duration + speaker list convenience methods
- `extractor.py` — structured action-item extractor with three
  pattern families: first-person (owner = current speaker, the trick
  naive regex misses), third-person, and direct requests; assignment-
  verb gate; due-date extraction including bare "tomorrow"/"today"
- `summarizer.py` — 4-section recap (Summary / Decisions /
  Action items / Open questions); template backend deterministic by
  default; Claude swap point documented; `Recap.to_markdown()` for
  ready-to-paste output
- `cli.py` — `summarize / demo / list-formats` with `--json` and
  `--markdown` output modes
- 4 bundled fixtures (one per supported format) covering common
  meeting types (product sync, security review, customer call,
  engineering standup)
- 39 pytest tests (parser + extractor + summarizer)
- Two-suite eval harness: 5 recap-quality cases (`contains_all` /
  `contains_any` rubric on rendered markdown) + 4 action-item cases
  (10 expected items, 100% recall on bundled fixtures)
- CI gates on 100% recap-quality + 100% action-item recall
- CI on Python 3.10/3.11/3.12 (tests + evals + CLI smoke)
- `pyproject.toml` with `[llm]` optional extra for `anthropic`
- Docs trio: `getting-started`, `architecture`, `customization`,
  `evaluation`, `diagrams`, `faq`
- OSS niceties: `CONTRIBUTING`, `CODE_OF_CONDUCT`, `SECURITY`,
  `CITATION.cff`, `.editorconfig`, `.devcontainer/devcontainer.json`,
  `.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE.md`,
  `.github/dependabot.yml`
- `Dockerfile`, `pages.yml` (live demo with per-meeting cards showing
  format + summary + decisions + action items with owner badges +
  open questions), `screenshots.yml`, `portfolio.yml` — workflows
  include `git pull --rebase` before push (race-condition fix)
- README badges: CI + License (MIT) + Python (3.10+) + Open in
  Codespaces
- Theme: violet (meeting / collaboration)
