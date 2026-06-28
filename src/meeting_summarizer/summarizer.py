"""Recap generator - four-section structured summary.

Default backend is a deterministic template-driven summarizer that
walks the transcript and extracts:
  - Summary: first 1-2 declarative sentences with substantive verbs
  - Decisions: lines containing "agreed", "decided", "approved", etc.
  - Action items: lines extracted by extractor.py (delegated)
  - Open questions: lines ending in '?' that didn't get clearly answered

The structure (4 sections) is the same regardless of backend; the LLM
backend just fills in better text per section. This means both the
Pages demo and the eval harness work without an LLM, while the LLM
swap gives real production quality.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from .extractor import ActionItem, extract_action_items
from .transcript import Transcript


@dataclass
class Recap:
    """The four-section structured recap."""
    summary: str
    decisions: list[str]
    action_items: list[ActionItem]
    open_questions: list[str]
    backend: str

    def to_markdown(self) -> str:
        """Render as a typical meeting-recap markdown doc."""
        lines = ["# Meeting recap", "", "## Summary", "", self.summary, ""]
        lines.append("## Decisions")
        lines.append("")
        if self.decisions:
            for d in self.decisions:
                lines.append(f"- {d}")
        else:
            lines.append("_None recorded._")
        lines.append("")
        lines.append("## Action items")
        lines.append("")
        if self.action_items:
            for a in self.action_items:
                due = f" (due {a.due})" if a.due else ""
                owner = a.owner or "UNASSIGNED"
                lines.append(f"- [{owner}] {a.description}{due}")
        else:
            lines.append("_None recorded._")
        lines.append("")
        lines.append("## Open questions")
        lines.append("")
        if self.open_questions:
            for q in self.open_questions:
                lines.append(f"- {q}")
        else:
            lines.append("_None recorded._")
        return "\n".join(lines)


class Summarizer:
    """Generates Recap from Transcript."""

    def __init__(self, backend: str | None = None):
        self.backend = backend or os.environ.get("MEETING_SUMMARIZER_LLM", "template")

    def summarize(self, transcript: Transcript) -> Recap:
        if self.backend == "claude":
            return self._summarize_claude(transcript)
        return self._summarize_template(transcript)

    # ----- The backend seam -----------------------------------------------

    def _summarize_template(self, transcript: Transcript) -> Recap:
        return Recap(
            summary=_extract_summary(transcript),
            decisions=_extract_decisions(transcript),
            action_items=extract_action_items(transcript),
            open_questions=_extract_open_questions(transcript),
            backend="template",
        )

    def _summarize_claude(self, transcript: Transcript) -> Recap:
        """Production swap point.

        Implementation sketch:

            from anthropic import Anthropic
            client = Anthropic()
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                system=("You are a meeting recap writer. Return JSON with keys: "
                        "summary (string), decisions (list of strings), "
                        "action_items (list of {description, owner, due}), "
                        "open_questions (list of strings)."),
                messages=[{"role": "user", "content": transcript.full_text()}],
            )
            data = json.loads(response.content[0].text)
            return Recap(
                summary=data["summary"],
                decisions=data["decisions"],
                action_items=[ActionItem(**a) for a in data["action_items"]],
                open_questions=data["open_questions"],
                backend="claude",
            )

        Until wired, fall back to the template summarizer so the kit still runs.
        """
        return self._summarize_template(transcript)


# ----- Per-section extractors -----------------------------------------------

_DECISION_VERBS = [
    "agreed", "decided", "approved", "resolved", "settled on", "will go with",
    "going with", "chose to", "concluded", "ratified",
]

_SUMMARY_STOPWORDS = {"um", "uh", "okay", "yeah", "alright", "right",
                       "thanks", "thank you", "hello", "hi", "bye"}


def _extract_summary(transcript: Transcript) -> str:
    """Pick the first 2 substantive sentences as a quick recap.

    Substantive = has a verb beyond the stopword list. The template
    summarizer is intentionally simple - the LLM backend writes proper
    summaries when wired.
    """
    sentences = []
    for seg in transcript.segments:
        for sentence in _split_sentences(seg.text):
            if _is_substantive(sentence):
                sentences.append(sentence)
                if len(sentences) >= 2:
                    break
        if len(sentences) >= 2:
            break
    if not sentences:
        return "Meeting transcript contained no substantive discussion."
    return " ".join(sentences)


def _extract_decisions(transcript: Transcript) -> list[str]:
    """Lines containing a decision verb get captured as decisions."""
    decisions = []
    for seg in transcript.segments:
        text = seg.text
        lower = text.lower()
        for verb in _DECISION_VERBS:
            if verb in lower:
                # Pull the sentence that contains the decision verb
                for sentence in _split_sentences(text):
                    if verb in sentence.lower():
                        decisions.append(sentence.strip())
                        break
                break
    return _dedupe_preserving_order(decisions)


def _extract_open_questions(transcript: Transcript) -> list[str]:
    """Sentences ending in '?' that weren't followed by a substantive answer
    (heuristic: next segment is short or also a question)."""
    questions = []
    segments = transcript.segments
    for i, seg in enumerate(segments):
        for sentence in _split_sentences(seg.text):
            if not sentence.strip().endswith("?"):
                continue
            # Look at next segment - if it's substantive, consider the question
            # answered (don't include). If short or also a question, include.
            next_text = segments[i + 1].text if i + 1 < len(segments) else ""
            if not next_text or len(next_text.split()) < 5 or next_text.strip().endswith("?"):
                questions.append(sentence.strip())
    return _dedupe_preserving_order(questions)


def _split_sentences(text: str) -> list[str]:
    """Crude sentence splitter. Real production should use a proper NLP lib."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _is_substantive(sentence: str) -> bool:
    words = sentence.lower().split()
    if len(words) < 4:
        return False
    non_filler = [w for w in words if w not in _SUMMARY_STOPWORDS]
    return len(non_filler) >= 4


def _dedupe_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out
