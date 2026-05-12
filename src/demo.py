import argparse
import json
import sys

from .config import TEST_CASES
from .generate import run
from .mock_salesforce import post_activity


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AfterVisit end-to-end on one test case.")
    parser.add_argument("--case", default="tc_01", help="Test case id from data/test_cases.json")
    args = parser.parse_args()

    if not TEST_CASES.exists():
        print(f"Test cases file not found: {TEST_CASES}", file=sys.stderr)
        return 2

    cases = json.loads(TEST_CASES.read_text(encoding="utf-8"))
    case = next((c for c in cases if c["id"] == args.case), None)
    if case is None:
        print(f"Case not found: {args.case}", file=sys.stderr)
        return 2

    print(f"=== Case: {case['id']} ===")
    print(f"Donor:        {case['donor_name']}")
    print(f"Segment:      {case['donor_segment']}")
    print(f"Meeting type: {case['meeting_type']}")
    print("Bullets:")
    for b in case["bullets"]:
        print(f"  - {b}")

    result = run(
        bullets=case["bullets"],
        donor_name=case["donor_name"],
        donor_segment=case["donor_segment"],
        meeting_type=case["meeting_type"],
    )

    print("\n=== Note (JSON) ===")
    print(json.dumps(result["note"], indent=2))
    print("\n=== Email ===")
    print(result["email"])
    print(f"\nReferences used: {result['references_used'] or '(none)'}")

    sf = post_activity(result["note"])
    print(f"\nMock Salesforce: {sf}")
    return 0 if sf.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
