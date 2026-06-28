"""Tests for the multi-format transcript parser."""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from meeting_summarizer.transcript import (  # noqa: E402
    Transcript, detect_format, parse, parse_file,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


# ---------- Format detection ------------------------------------------------

def test_detect_text_format():
    content = "Alice: Hello.\nBob: Hi."
    assert detect_format(content) == "text"


def test_detect_vtt_format():
    content = "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nHello"
    assert detect_format(content) == "vtt"


def test_detect_srt_format():
    content = "1\n00:00:00,000 --> 00:00:05,000\nHello"
    assert detect_format(content) == "srt"


def test_detect_otter_json_format():
    content = '{"segments": [{"speaker": "A", "text": "hi"}]}'
    assert detect_format(content) == "otter_json"


# ---------- Plain text parser -----------------------------------------------

def test_text_parser_extracts_speaker_lines():
    t = parse("Alice: Hello.\nBob: Hi.\nAlice: How are you?")
    assert len(t.segments) == 3
    assert t.segments[0].speaker == "Alice"
    assert t.segments[0].text == "Hello."
    assert t.segments[1].speaker == "Bob"


def test_text_parser_attaches_continuation_lines():
    t = parse("Alice: This is line one.\nThis is a continuation.")
    assert len(t.segments) == 1
    assert "continuation" in t.segments[0].text


def test_text_parser_handles_blank_lines_as_breaks():
    t = parse("Alice: Hello.\n\nBob: Hi.")
    assert len(t.segments) == 2


# ---------- VTT parser ------------------------------------------------------

def test_vtt_parser_handles_bundled_fixture():
    t = parse_file(FIXTURES / "02-zoom-recording.vtt")
    assert t.source_format == "vtt"
    assert len(t.segments) > 0
    # Sarah Chen should be a speaker via the <v ...> tag
    speakers = t.speakers()
    assert "Sarah Chen" in speakers
    assert "David Park" in speakers


def test_vtt_parser_captures_timestamps():
    t = parse_file(FIXTURES / "02-zoom-recording.vtt")
    first = t.segments[0]
    assert first.start_seconds == 0.0
    assert first.end_seconds > 0.0
    assert first.end_seconds < 10.0


# ---------- SRT parser ------------------------------------------------------

def test_srt_parser_handles_bundled_fixture():
    t = parse_file(FIXTURES / "03-customer-call.srt")
    assert t.source_format == "srt"
    assert len(t.segments) > 0
    # SRT in fixture embeds "Speaker: text" - parser should extract speaker
    speakers = t.speakers()
    assert "Account Manager" in speakers
    assert "Jordan Park" in speakers


# ---------- Otter JSON parser -----------------------------------------------

def test_otter_json_parser_handles_bundled_fixture():
    t = parse_file(FIXTURES / "04-otter-transcript.json")
    assert t.source_format == "otter_json"
    assert len(t.segments) == 11
    assert t.segments[0].speaker == "Maya"


def test_otter_json_alternate_shape():
    content = (
        '{"transcript": ['
        '{"speaker_name": "X", "text": "hi", "start_time": 0, "end_time": 1}'
        ']}'
    )
    t = parse(content)
    assert t.source_format == "otter_json"
    assert len(t.segments) == 1
    assert t.segments[0].speaker == "X"


# ---------- Transcript convenience methods ----------------------------------

def test_speakers_dedupes_and_preserves_order():
    t = parse("Alice: a\nBob: b\nAlice: c\nCarol: d")
    assert t.speakers() == ["Alice", "Bob", "Carol"]


def test_duration_seconds_uses_max_end():
    t = parse_file(FIXTURES / "02-zoom-recording.vtt")
    assert t.duration_seconds() > 60  # zoom recording is ~2 min


def test_full_text_renders_speaker_prefixed():
    t = parse("Alice: Hi.\nBob: Hello.")
    full = t.full_text()
    assert "Alice: Hi." in full
    assert "Bob: Hello." in full
