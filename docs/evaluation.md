# Evaluation

Two eval suites gate CI. They move on different cadences (recap
format vs extractor accuracy), so keeping them separate makes failure
attribution clean.

## Recap-quality suite

Per `evals/recap-quality.json`, each case asserts the rendered
markdown contains required phrases.

```json
{
  "id": "product-sync-has-all-sections",
  "fixture": "01-product-sync.txt",
  "rubric": {"contains_all": ["## Summary", "## Decisions",
                              "## Action items", "## Open questions"]}
}
```

Two rubric types supported: `contains_all` and `contains_any`.

**What this catches:** Someone refactors `to_markdown()` and
accidentally drops a section header. Or the decision-verb list got
narrowed and a fixture's known decision stopped being captured.

## Action-item suite

Per `evals/action-items.json`, each case lists expected (owner,
description_contains) pairs:

```json
{
  "id": "product-sync-extracts-five-items",
  "fixture": "01-product-sync.txt",
  "expected_items": [
    {"owner": "Bob",   "description_contains": "draft the dashboard spec"},
    {"owner": "Carol", "description_contains": "customer panel"},
    ...
  ]
}
```

The harness:
1. Runs the extractor against the fixture
2. For each expected item, checks if any extracted item matches
   (`owner == owner_needed` AND `description_contains` substring is in
   description)
3. Counts how many of the expected items were found = **recall**

**What this catches:** Most extractor regressions. The first-person
trick — where "I'll draft" maps owner to current speaker — is the
fragile bit; this suite directly verifies it stays correct.

## Running

```bash
python evals/run.py
```

Output:

```
=== Recap-quality eval (5 cases) ===
  PASS  product-sync-has-all-sections
  PASS  product-sync-mentions-dashboard-decision
  PASS  zoom-recording-mentions-mfa-or-conditional-access
  PASS  customer-call-has-action-item-section
  PASS  otter-standup-mentions-deploy-or-migration

=== Action-item eval (4 cases) ===
  PASS  product-sync-extracts-five-items                all 5 expected items found
  PASS  zoom-recording-davids-actions                   all 2 expected items found
  PASS  customer-call-account-manager-actions           all 1 expected items found
  PASS  otter-standup-diego-actions                     all 2 expected items found

  Overall action-item recall: 10/10 (100%)

Overall: recap-quality OK, action-items OK
```

Exit non-zero if either suite has failures. CI gates on both.

## Why two suites instead of one

| Aspect | Recap-quality | Action items |
|---|---|---|
| What changes trigger it | Template, summarizer, markdown renderer | Extractor patterns, assignment verbs, blocklist |
| Failure mode | Wrong section / missing topic in summary | Missed action item, wrong owner attribution |
| Iteration cadence | When you change the recap shape | When you find a new pattern in real transcripts |

Mixing them would force every template tweak to re-run every
extractor assertion (noisy CI) and vice versa.

## Adding cases

For recap quality: drop the fixture + a `contains_all` / `contains_any`
rubric:

```json
{"id": "your-new-case", "fixture": "your-fixture.txt",
 "rubric": {"contains_any": ["specific phrase from the meeting"]}}
```

For action items: list every action item you expect, with
recall-friendly substring matching:

```json
{
  "id": "your-new-case",
  "fixture": "your-fixture.txt",
  "expected_items": [
    {"owner": "PersonName", "description_contains": "key verb phrase"}
  ]
}
```

## Recall vs precision

The action-item suite reports **recall** (% of expected items found).
It doesn't report **precision** (% of extracted items that should
have been extracted) because the bundled extractor is conservative
enough that precision is consistently 100% — every extracted item
matches the structural patterns + has an assignment verb.

For LLM-backed extraction, precision matters more (the LLM may
hallucinate action items). Add a precision check:

```python
# In evals/run.py, run_action_items()
# After computing recall, also compute precision:
expected_descriptions = set()
for case in cases:
    for exp in case["expected_items"]:
        expected_descriptions.add(exp["description_contains"].lower())

precision_hits = sum(
    1 for item in all_extracted_items
    if any(exp in item.description.lower() for exp in expected_descriptions)
)
precision = precision_hits / len(all_extracted_items)
```

## Running the eval suites against the LLM backend

Once `_summarize_claude` is wired:

```bash
pip install -e ".[llm]"
export ANTHROPIC_API_KEY=sk-...
MEETING_SUMMARIZER_LLM=claude python evals/run.py
```

Expect:

- **Recap-quality suite**: stays mostly green (the LLM should still
  produce all 4 sections). Occasional flips if it phrases things
  differently than the rubric expects — loosen rubrics or update
  expectations.
- **Action-item suite**: should improve recall (LLM catches actions
  the regex misses) at the cost of occasional precision (LLM may
  hallucinate). The first-person trick is in the prompt, so the
  owner attribution should stay correct.

## Performance

Bundled suite runs in ~50ms on the template backend. Adding 50+
fixtures keeps it under a second. LLM backend is ~1-3s per case;
budget accordingly for CI run times.

## CI cost

Free for the template backend (no API calls). For LLM-backed CI:
~10 cases × 2K tokens average = 20K input + ~3K output tokens per
PR run. At Haiku rates ≈ $0.005 per PR. At Opus ≈ $0.30 per PR.
Run on every PR; the cost is negligible.
