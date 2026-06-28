"""Tests for the Summarizer + Recap rendering."""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from meeting_summarizer.summarizer import Summarizer  # noqa: E402
from meeting_summarizer.transcript import parse, parse_file  # noqa: E402


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_summarizer_produces_four_section_recap():
    t = parse_file(FIXTURES / "01-product-sync.txt")
    recap = Summarizer().summarize(t)
    assert recap.summary
    assert isinstance(recap.decisions, list)
    assert isinstance(recap.action_items, list)
    assert isinstance(recap.open_questions, list)


def test_recap_to_markdown_has_all_section_headers():
    t = parse_file(FIXTURES / "01-product-sync.txt")
    recap = Summarizer().summarize(t)
    md = recap.to_markdown()
    assert "## Summary" in md
    assert "## Decisions" in md
    assert "## Action items" in md
    assert "## Open questions" in md


def test_recap_to_markdown_renders_action_items_with_owners():
    t = parse_file(FIXTURES / "01-product-sync.txt")
    md = Summarizer().summarize(t).to_markdown()
    # Every action item line should start with "- [OWNER]"
    action_lines = [l for l in md.splitlines() if l.startswith("- [")]
    assert len(action_lines) >= 1
    for line in action_lines:
        # Owner shouldn't be UNASSIGNED for the bundled fixture
        assert "UNASSIGNED" not in line


def test_recap_to_markdown_handles_empty_sections():
    t = parse("Alice: Hi.\nBob: Hello.")
    md = Summarizer().summarize(t).to_markdown()
    assert "_None recorded._" in md  # at least one empty section


def test_decisions_extracted_from_agreed_verb():
    t = parse(
        "Alice: We agreed to ship the dashboard in Q3.\n"
        "Bob: Sounds right."
    )
    recap = Summarizer().summarize(t)
    assert len(recap.decisions) >= 1
    assert "agreed" in recap.decisions[0].lower()


def test_decisions_extracted_from_decided_verb():
    t = parse("Alice: We decided to use Postgres.")
    recap = Summarizer().summarize(t)
    assert len(recap.decisions) >= 1


def test_open_questions_includes_unanswered_question():
    t = parse(
        "Bob: What's our pricing for the EU?\n"
        "Alice: Hmm.\n"  # short response = not answered
    )
    recap = Summarizer().summarize(t)
    assert any("EU" in q or "pricing" in q for q in recap.open_questions)


def test_summary_skips_pure_pleasantries():
    """A transcript of just greetings shouldn't produce a substantive summary."""
    t = parse("Alice: Hi.\nBob: Hello.\nAlice: Bye.")
    recap = Summarizer().summarize(t)
    assert "no substantive" in recap.summary.lower()


def test_summarizer_default_backend_is_template():
    saved = os.environ.pop("MEETING_SUMMARIZER_LLM", None)
    try:
        assert Summarizer().backend == "template"
    finally:
        if saved is not None:
            os.environ["MEETING_SUMMARIZER_LLM"] = saved


def test_recap_carries_backend_name():
    t = parse("Alice: We agreed to do X.")
    recap = Summarizer().summarize(t)
    assert recap.backend == "template"
