"""Action item extractor - pulls owner + description + due date from transcript.

A meeting recap is only useful if the action items are real. The
extractor walks the transcript looking for action-item signal:
  - "I will <verb>" / "I'll <verb>" -> owner = current speaker
  - "X will <verb>" / "X is going to <verb>" -> owner = X
  - "X, can you <verb>" / "X, please <verb>" -> owner = X

For each match it extracts owner, description, and (if present) a
due-date phrase. Real production should layer a real NER + date parser
on top; the kit's regex approach is the deterministic baseline + the
LLM swap point.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .transcript import Transcript


@dataclass
class ActionItem:
    """One extracted action item with owner + description + optional due."""
    owner: str
    description: str
    due: str = ""
    evidence: str = ""  # the source sentence


# ----- Patterns --------------------------------------------------------------

# First-person commitments: speaker takes the action.
_FIRST_PERSON_PATTERNS = [
    re.compile(r"\bI\s+will\s+([a-z][^.!?]*)", re.M),
    re.compile(r"\bI'?ll\s+([a-z][^.!?]*)", re.M),
    re.compile(r"\bI'?m\s+going\s+to\s+([a-z][^.!?]*)", re.M),
]

# Third-person commitments: "Alice will draft the spec"
_THIRD_PERSON_PATTERNS = [
    re.compile(r"\b([A-Z][a-zA-Z\-']+)\s+will\s+([a-z][^.!?]*)", re.M),
    re.compile(r"\b([A-Z][a-zA-Z\-']+)\s+is\s+going\s+to\s+([a-z][^.!?]*)", re.M),
]

# Direct requests: "Alice, can you draft the spec?"
_REQUEST_PATTERNS = [
    re.compile(r"([A-Z][a-zA-Z\-']+),\s*(?:can\s+you|could\s+you|please|you'?ll)\s+([a-z][^.!?]*)", re.M),
]

# Assignment verbs.
_ASSIGNMENT_VERBS = {
    "send", "draft", "write", "review", "follow up", "schedule", "set up",
    "investigate", "look into", "ship", "deploy", "file", "create", "build",
    "test", "share", "publish", "post", "email", "ping", "loop in", "introduce",
    "prepare", "circulate", "submit", "deliver", "finish", "complete",
    "handle", "own", "reach out", "check", "confirm", "move", "rotate",
    "audit", "book", "put together", "write up",
}

# Due date patterns.
_DUE_PATTERNS = [
    re.compile(r"by\s+(end of\s+\w+(?:\s+\w+)?|\w+day|next\s+\w+|tomorrow|today|"
                r"\d{4}-\d{2}-\d{2}|"
                r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d+)", re.I),
    re.compile(r"by\s+(EOD|EOW|EOM|COB)\b", re.I),
    re.compile(r"before\s+(end of\s+\w+|\w+day|next\s+\w+|tomorrow)", re.I),
    # Bare temporal at end of sentence: "send the deck tomorrow"
    re.compile(r"\b(tomorrow|today|this\s+\w+day|next\s+\w+day)\s*[.!?]?\s*$", re.I),
]

# Owner blocklist - words that look like names but aren't.
# "I" is NOT here - handled separately by first-person pattern.
_NOT_NAMES = {
    "And", "But", "Or", "Now", "Then", "So", "If", "Because",
    "Let", "Let's", "We", "You", "They", "It", "This", "That",
    "Here", "There", "When", "Where", "Why", "How",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    "Saturday", "Sunday", "January", "February", "March",
}


def extract_action_items(transcript: Transcript) -> list[ActionItem]:
    """Extract all action items from the transcript."""
    items: list[ActionItem] = []
    seen_descriptions: set[str] = set()

    for seg in transcript.segments:
        for sentence in _split_sentences(seg.text):
            for item in _extract_from_sentence(sentence, current_speaker=seg.speaker):
                key = item.description.lower().strip()
                if key in seen_descriptions:
                    continue
                seen_descriptions.add(key)
                items.append(item)
    return items


def _extract_from_sentence(sentence: str, current_speaker: str = "") -> list[ActionItem]:
    """Pull every action item from one sentence (a sentence can have multiple)."""
    found: list[ActionItem] = []
    consumed_spans: list[tuple[int, int]] = []

    # First-person matches first (owner = current speaker).
    if current_speaker:
        for pattern in _FIRST_PERSON_PATTERNS:
            for m in pattern.finditer(sentence):
                description = _clean_description(m.group(1))
                if not _has_assignment_verb(description):
                    continue
                if _overlaps(m.span(), consumed_spans):
                    continue
                consumed_spans.append(m.span())
                due = _extract_due(sentence)
                found.append(ActionItem(
                    owner=current_speaker, description=description,
                    due=due, evidence=sentence.strip(),
                ))

    # Then third-person + request patterns.
    for pattern in _THIRD_PERSON_PATTERNS + _REQUEST_PATTERNS:
        for m in pattern.finditer(sentence):
            owner = m.group(1).strip()
            if owner in _NOT_NAMES:
                continue
            description = _clean_description(m.group(2))
            if not _has_assignment_verb(description):
                continue
            if _overlaps(m.span(), consumed_spans):
                continue
            consumed_spans.append(m.span())
            due = _extract_due(sentence)
            found.append(ActionItem(
                owner=owner, description=description,
                due=due, evidence=sentence.strip(),
            ))
    return found


def _overlaps(span: tuple[int, int], consumed: list[tuple[int, int]]) -> bool:
    for s, e in consumed:
        if span[0] < e and span[1] > s:
            return True
    return False


def _clean_description(description: str) -> str:
    desc = description.strip().rstrip(".,;!?")
    for pat in _DUE_PATTERNS:
        desc = pat.sub("", desc).strip().rstrip(".,;!?")
    return desc


def _has_assignment_verb(description: str) -> bool:
    lower = description.lower()
    return any(verb in lower for verb in _ASSIGNMENT_VERBS)


def _extract_due(sentence: str) -> str:
    for pattern in _DUE_PATTERNS:
        m = pattern.search(sentence)
        if m:
            return m.group(1).strip()
    return ""


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]
