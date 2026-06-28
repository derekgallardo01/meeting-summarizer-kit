"""Tests for the action item extractor."""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from meeting_summarizer.extractor import extract_action_items  # noqa: E402
from meeting_summarizer.transcript import parse, parse_file  # noqa: E402


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_extracts_third_person_will():
    t = parse("Alice: Bob will draft the spec by Friday.")
    items = extract_action_items(t)
    assert len(items) == 1
    assert items[0].owner == "Bob"
    assert "draft the spec" in items[0].description
    assert items[0].due == "Friday"


def test_extracts_first_person_will_attributes_to_speaker():
    t = parse("Bob: I will draft the spec by Friday.")
    items = extract_action_items(t)
    assert len(items) == 1
    assert items[0].owner == "Bob"  # speaker, not "I"
    assert items[0].due == "Friday"


def test_extracts_first_person_contraction_ill():
    t = parse("Bob: I'll send the deck tomorrow.")
    items = extract_action_items(t)
    assert len(items) == 1
    assert items[0].owner == "Bob"
    assert items[0].due == "tomorrow"


def test_extracts_request_pattern():
    t = parse("Alice: Carol, can you review the doc by Monday?")
    items = extract_action_items(t)
    assert len(items) == 1
    assert items[0].owner == "Carol"
    assert "review" in items[0].description
    assert items[0].due == "Monday"


def test_extracts_im_going_to_pattern():
    t = parse("Bob: I'm going to send the contract today.")
    items = extract_action_items(t)
    assert len(items) == 1
    assert items[0].owner == "Bob"


def test_skips_sentences_without_assignment_verbs():
    """No assignment verb = not an action item, even if structurally it matches."""
    t = parse("Alice: Bob will think about it.")
    items = extract_action_items(t)
    assert items == []


def test_skips_owner_in_blocklist():
    t = parse("Alice: We will discuss this later.")
    items = extract_action_items(t)
    assert items == []


def test_strips_due_phrase_from_description():
    t = parse("Bob: I will send the report by tomorrow.")
    items = extract_action_items(t)
    assert items[0].due == "tomorrow"
    assert "tomorrow" not in items[0].description.lower()


def test_extracts_due_with_eod_eow_etc():
    t = parse("Alice: I will publish the post by EOD.")
    items = extract_action_items(t)
    assert items[0].due == "EOD"


def test_dedupes_repeated_items():
    """Same action item appearing twice should only be returned once."""
    t = parse(
        "Alice: I will send the report tomorrow.\n"
        "Alice: Yes, I will send the report tomorrow."
    )
    items = extract_action_items(t)
    assert len(items) == 1


# ---------- End-to-end on bundled fixtures ---------------------------------

def test_product_sync_extracts_5_items():
    """Fixture 01 has 5 action items across Alice/Bob/Carol."""
    t = parse_file(FIXTURES / "01-product-sync.txt")
    items = extract_action_items(t)
    assert len(items) == 5
    owners = [i.owner for i in items]
    assert "Bob" in owners
    assert "Carol" in owners
    assert "Alice" in owners  # via first-person


def test_zoom_recording_extracts_actions_from_vtt():
    t = parse_file(FIXTURES / "02-zoom-recording.vtt")
    items = extract_action_items(t)
    assert len(items) >= 2
    # David should have an action (first-person "I'll")
    owners = [i.owner for i in items]
    assert "David Park" in owners


def test_customer_call_extracts_actions_from_srt():
    t = parse_file(FIXTURES / "03-customer-call.srt")
    items = extract_action_items(t)
    # Account manager has actions: schedule a tech call, send pricing
    assert len(items) >= 1
    descriptions = " ".join(i.description.lower() for i in items)
    assert "loop in" in descriptions or "schedule" in descriptions or "send" in descriptions


def test_otter_transcript_extracts_actions_from_json():
    t = parse_file(FIXTURES / "04-otter-transcript.json")
    items = extract_action_items(t)
    assert len(items) >= 2
    owners = [i.owner for i in items]
    assert "Diego" in owners
