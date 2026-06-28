"""End-to-end pipeline: transcript -> recap -> Linear issues + Notion doc.

Demonstrates the production loop:

1. Pull a transcript (path or stdin)
2. Parse + summarize -> Recap
3. For each action item:
   - Map owner name -> Linear user ID via a directory lookup
   - Create a Linear issue (dry-run by default; set LINEAR_API_KEY to actually create)
4. For the summary + decisions:
   - Build a Notion-flavored markdown doc
   - Print or POST to a Notion page (dry-run by default)

Run as a webhook handler after Zoom drops a recording, or as a manual
post-meeting trigger.

Usage:
    python examples/zoom_to_linear.py fixtures/01-product-sync.txt
    LINEAR_API_KEY=lin_... python examples/zoom_to_linear.py meeting.vtt --team eng
    python examples/zoom_to_linear.py meeting.txt --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from meeting_summarizer.summarizer import Summarizer  # noqa: E402
from meeting_summarizer.transcript import parse_file  # noqa: E402
from meeting_summarizer.extractor import ActionItem  # noqa: E402


# Hardcoded directory for the demo. Real production reads from your HR/IDP system.
# Format: speaker-name-as-it-appears-in-transcript -> Linear user id.
DIRECTORY = {
    "Alice": "user-uuid-alice",
    "Bob": "user-uuid-bob",
    "Carol": "user-uuid-carol",
    "Maya": "user-uuid-maya",
    "Diego": "user-uuid-diego",
    "Priya": "user-uuid-priya",
    "Sarah Chen": "user-uuid-sarah",
    "David Park": "user-uuid-david",
    "Maria Rodriguez": "user-uuid-maria",
}


def owner_to_linear_id(owner: str) -> str | None:
    """Map a speaker name from the transcript to a Linear user UUID."""
    # Direct match first
    if owner in DIRECTORY:
        return DIRECTORY[owner]
    # Try first-name match (the recap might give first names only)
    first = owner.split()[0] if owner else ""
    return DIRECTORY.get(first)


def create_linear_issue(api_key: str, team_id: str, title: str, description: str,
                         assignee_id: str | None = None, due_date: str | None = None) -> dict:
    """POST a new issue to the Linear GraphQL API."""
    mutation = """
    mutation IssueCreate($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue { id identifier title url }
      }
    }
    """
    variables = {
        "input": {
            "teamId": team_id, "title": title, "description": description,
        }
    }
    if assignee_id:
        variables["input"]["assigneeId"] = assignee_id
    # due_date is intentionally NOT mapped to Linear's dueDate here because the
    # transcript phrases ("Friday", "tomorrow") need real date resolution first.
    # See process_action_item below.

    req = urllib.request.Request(
        "https://api.linear.app/graphql",
        data=json.dumps({"query": mutation, "variables": variables}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def post_to_notion(api_key: str, page_id: str, markdown: str) -> dict:
    """Append a meeting recap as a child block of an existing Notion page.

    Real production would use Notion's full block API. This sketch uses a
    single rich-text paragraph for brevity.
    """
    # Sketch only - Notion's block schema is much richer; see notion-py SDK for a
    # complete implementation.
    raise NotImplementedError(
        "Notion integration is left as a documented sketch. See notion-py "
        "or the official Notion API docs to wire the full block schema."
    )


def process_action_item(item: ActionItem, api_key: str, team_id: str,
                         dry_run: bool) -> dict:
    """Map one extracted ActionItem to a Linear issue creation."""
    assignee_id = owner_to_linear_id(item.owner)
    title = item.description
    description_lines = [
        f"**From meeting recap.**",
        "",
        f"_Owner from transcript:_ {item.owner}",
    ]
    if item.due:
        description_lines.append(f"_Due (from transcript):_ {item.due}")
    if item.evidence:
        description_lines.append("")
        description_lines.append("_Source:_ " + item.evidence)
    description = "\n".join(description_lines)

    if dry_run:
        return {
            "dry_run": True,
            "title": title, "assignee_id": assignee_id,
            "description_preview": description[:120],
        }
    if not assignee_id:
        return {"skipped": "no_assignee_match", "owner": item.owner, "title": title}
    return create_linear_issue(api_key, team_id, title, description, assignee_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Meeting transcript -> Linear issues pipeline.")
    parser.add_argument("transcript", help="Path to the transcript file (.txt/.vtt/.srt/.json).")
    parser.add_argument("--format", default=None,
                        choices=["text", "vtt", "srt", "otter_json"])
    parser.add_argument("--team", default="ENG", help="Linear team key (e.g., ENG, OPS).")
    parser.add_argument("--api-key", default=os.environ.get("LINEAR_API_KEY", ""),
                        help="Linear API key (or LINEAR_API_KEY env var).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print would-be issues instead of creating them.")
    args = parser.parse_args(argv)

    transcript = parse_file(args.transcript, source_format=args.format)
    recap = Summarizer().summarize(transcript)

    print(f"\nParsed {len(transcript.segments)} segments "
          f"({transcript.source_format}, speakers: {transcript.speakers()})")
    print(f"\nRecap:\n  Summary:       {recap.summary[:120]}...")
    print(f"  Decisions:     {len(recap.decisions)}")
    print(f"  Action items:  {len(recap.action_items)}")
    print(f"  Open questions:{len(recap.open_questions)}")

    dry_run = args.dry_run or not args.api_key
    if dry_run and not args.dry_run:
        print("\n  (No LINEAR_API_KEY set — running in dry-run mode)")

    print(f"\n\nProcessing {len(recap.action_items)} action items "
          f"({'DRY RUN' if dry_run else 'LIVE'}):\n")

    results = []
    for item in recap.action_items:
        result = process_action_item(item, args.api_key, args.team, dry_run=dry_run)
        results.append(result)
        if "dry_run" in result:
            assignee = result["assignee_id"] or "(no Linear match)"
            print(f"  [WOULD CREATE] {item.owner} -> {assignee}")
            print(f"      title: {item.description}")
            if item.due:
                print(f"      due:   {item.due}")
        elif "skipped" in result:
            print(f"  [SKIP] {result['title']} ({result['skipped']})")
        else:
            issue = result.get("data", {}).get("issueCreate", {}).get("issue", {})
            print(f"  [CREATED] {issue.get('identifier')}: {issue.get('title')}  {issue.get('url')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
