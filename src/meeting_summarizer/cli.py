"""CLI - summarize transcripts in 4 formats.

Usage:
    meeting-summarizer summarize <transcript-path>          # auto-detect format
    meeting-summarizer summarize <path> --format vtt        # force format
    meeting-summarizer summarize <path> --json              # JSON output
    meeting-summarizer summarize <path> --markdown          # rendered recap
    meeting-summarizer demo                                 # all bundled fixtures
    meeting-summarizer list-formats
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .summarizer import Summarizer
from .transcript import detect_format, parse_file


def cmd_list_formats(_args) -> int:
    print("Supported transcript formats:\n")
    formats = [
        ("text", "Plain text. 'Speaker Name: utterance' per line."),
        ("vtt", "WebVTT format. Zoom / Teams / Google Meet cloud recordings."),
        ("srt", "SubRip subtitle format. Most desktop transcription tools."),
        ("otter_json", "Otter.ai / Fireflies.ai / Grain JSON exports."),
    ]
    for name, desc in formats:
        print(f"  {name:12s} {desc}")
    print("\nFormat is auto-detected; --format flag overrides.")
    return 0


def cmd_summarize(args) -> int:
    transcript = parse_file(args.path, source_format=args.format)
    summarizer = Summarizer()
    recap = summarizer.summarize(transcript)

    if args.json:
        out = {
            "transcript": {
                "source_format": transcript.source_format,
                "meeting_title": transcript.meeting_title,
                "duration_seconds": transcript.duration_seconds(),
                "speakers": transcript.speakers(),
                "segment_count": len(transcript.segments),
            },
            "recap": {
                "summary": recap.summary,
                "decisions": recap.decisions,
                "action_items": [asdict(a) for a in recap.action_items],
                "open_questions": recap.open_questions,
                "backend": recap.backend,
            },
        }
        print(json.dumps(out, indent=2))
        return 0

    if args.markdown:
        print(recap.to_markdown())
        return 0

    # Default human-readable output
    print(f"\n  {Path(args.path).name}")
    print(f"    format:    {transcript.source_format}")
    print(f"    speakers:  {transcript.speakers()}")
    print(f"    segments:  {len(transcript.segments)}")
    print(f"\n  SUMMARY:")
    print(f"    {recap.summary}")
    print(f"\n  DECISIONS ({len(recap.decisions)}):")
    for d in recap.decisions:
        print(f"    - {d}")
    print(f"\n  ACTION ITEMS ({len(recap.action_items)}):")
    for a in recap.action_items:
        due = f" (due {a.due})" if a.due else ""
        print(f"    - [{a.owner}] {a.description}{due}")
    print(f"\n  OPEN QUESTIONS ({len(recap.open_questions)}):")
    for q in recap.open_questions:
        print(f"    - {q}")
    print(f"\n  Backend: {recap.backend}")
    return 0


def cmd_demo(args) -> int:
    fixtures = Path(__file__).resolve().parents[2] / "fixtures"
    files = sorted(fixtures.iterdir())
    results = []
    for fixture in files:
        if fixture.suffix.lower() not in (".txt", ".vtt", ".srt", ".json"):
            continue
        transcript = parse_file(fixture)
        recap = Summarizer().summarize(transcript)
        results.append({
            "file": fixture.name,
            "format": transcript.source_format,
            "speakers": transcript.speakers(),
            "decisions": len(recap.decisions),
            "actions": len(recap.action_items),
            "questions": len(recap.open_questions),
        })
        if not args.json:
            print(f"  {fixture.name:35s}  format={transcript.source_format:11s}  "
                  f"{len(transcript.segments):3d} segments  "
                  f"{len(recap.decisions)} decisions  "
                  f"{len(recap.action_items)} actions  "
                  f"{len(recap.open_questions)} questions")

    if args.json:
        print(json.dumps({"backend": Summarizer().backend, "runs": results}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Meeting summarizer CLI.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-formats")

    p_sum = sub.add_parser("summarize")
    p_sum.add_argument("path")
    p_sum.add_argument("--format", default=None,
                       choices=["text", "vtt", "srt", "otter_json"])
    p_sum.add_argument("--json", action="store_true")
    p_sum.add_argument("--markdown", action="store_true")

    p_demo = sub.add_parser("demo")
    p_demo.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    handlers = {"list-formats": cmd_list_formats,
                "summarize": cmd_summarize, "demo": cmd_demo}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
