"""Eval harness - two suites: recap quality + action-item accuracy.

Recap-quality suite:
  - Per-fixture rubric on the rendered markdown recap (contains_all,
    contains_any).
  - Catches "we changed the template and lost a section."

Action-item suite:
  - Per-fixture list of expected (owner, description_contains) pairs.
  - Catches "we tweaked the regex and now we miss first-person commitments."
  - Computes recall (% of expected items found).

CI gates on both suites at 100%.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from meeting_summarizer.extractor import extract_action_items  # noqa: E402
from meeting_summarizer.summarizer import Summarizer  # noqa: E402
from meeting_summarizer.transcript import parse_file  # noqa: E402


FIXTURES = ROOT / "fixtures"


def load(name: str) -> list[dict]:
    with open(Path(__file__).parent / name) as f:
        return json.load(f)["cases"]


def run_recap_quality() -> bool:
    cases = load("recap-quality.json")
    print(f"\n=== Recap-quality eval ({len(cases)} cases) ===\n")

    all_passed = True
    for case in cases:
        transcript = parse_file(FIXTURES / case["fixture"])
        recap = Summarizer().summarize(transcript)
        md = recap.to_markdown()
        rubric = case["rubric"]

        if "contains_all" in rubric:
            missing = [s for s in rubric["contains_all"] if s.lower() not in md.lower()]
            if missing:
                print(f"  FAIL  {case['id']:50s}  missing: {missing}")
                all_passed = False
                continue
        if "contains_any" in rubric:
            options = rubric["contains_any"]
            if not any(s.lower() in md.lower() for s in options):
                print(f"  FAIL  {case['id']:50s}  none of {options} present")
                all_passed = False
                continue

        print(f"  PASS  {case['id']}")
    return all_passed


def run_action_items() -> bool:
    cases = load("action-items.json")
    print(f"\n=== Action-item eval ({len(cases)} cases) ===\n")

    total_expected = 0
    total_found = 0
    all_passed = True

    for case in cases:
        transcript = parse_file(FIXTURES / case["fixture"])
        extracted = extract_action_items(transcript)
        expected = case["expected_items"]

        missing_per_case = []
        for exp in expected:
            owner_needed = exp["owner"]
            desc_substr = exp["description_contains"].lower()
            match = any(
                a.owner == owner_needed and desc_substr in a.description.lower()
                for a in extracted
            )
            total_expected += 1
            if match:
                total_found += 1
            else:
                missing_per_case.append(f"[{owner_needed}] {exp['description_contains']!r}")

        if missing_per_case:
            print(f"  FAIL  {case['id']:50s}  missing {len(missing_per_case)} expected: {missing_per_case}")
            all_passed = False
        else:
            print(f"  PASS  {case['id']:50s}  all {len(expected)} expected items found")

    recall = total_found / total_expected if total_expected else 0.0
    print(f"\n  Overall action-item recall: {total_found}/{total_expected} ({recall:.0%})")
    return all_passed


def main() -> int:
    recap_ok = run_recap_quality()
    actions_ok = run_action_items()
    print(f"\nOverall: recap-quality {'OK' if recap_ok else 'FAIL'}, "
          f"action-items {'OK' if actions_ok else 'FAIL'}")
    return 0 if recap_ok and actions_ok else 1


if __name__ == "__main__":
    sys.exit(main())
