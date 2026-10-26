"""Compare two evaluation runs, for example a baseline prompt against a refined one.

    python -m evaluation.compare text-v1 text-v2
"""

import json
import sys

from .run_eval import RESULTS_DIR, _pct

ROWS = [
    ("Intent accuracy", "intent_accuracy"),
    ("Urgency accuracy", "urgency_accuracy"),
    ("Name extraction accuracy", "name_extraction_accuracy"),
    ("Phone extraction accuracy", "phone_extraction_accuracy"),
    ("Valid JSON on first attempt", "first_attempt_json_rate"),
    ("Valid schema on first attempt", "first_attempt_schema_rate"),
    ("Pipeline success", "pipeline_success_rate"),
]


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    before, after = sys.argv[1], sys.argv[2]
    summaries = [json.loads((RESULTS_DIR / f"{n}.json").read_text(encoding="utf-8"))["summary"] for n in (before, after)]
    print(f"| Metric | {before} | {after} |\n|---|---|---|")
    for label, key in ROWS:
        print(f"| {label} | {_pct(summaries[0][key])} | {_pct(summaries[1][key])} |")


if __name__ == "__main__":
    main()
