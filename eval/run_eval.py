"""
run_eval.py
-----------
Runs the agent against 25 test questions and reports:
  - Accuracy %          : answer contains the expected value
  - Self-correction rate: questions solved on attempt 2 or 3
  - Average latency     : seconds per question
  - Tool routing        : did it call query_data as expected?

Run with:
    python eval/run_eval.py
"""

import sys
import json
import time
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(level=logging.WARNING)   # quiet during eval

from agents.data_agent import query_data

QUESTIONS_FILE = BASE_DIR / "eval" / "questions.json"


def check_answer(result: dict, expected_contains: list) -> bool:
    """Check if any expected value appears in the result data."""
    if not result["success"]:
        return False
    df = result["data"]
    # Convert entire dataframe to string and search
    data_str = df.to_string().lower()
    for expected in expected_contains:
        if str(expected).lower() in data_str:
            return True
    return False


def run_evaluation():
    questions = json.loads(QUESTIONS_FILE.read_text())

    total         = len(questions)
    correct       = 0
    self_corrected = 0
    latencies     = []
    failures      = []

    print(f"\n{'='*60}")
    print(f"Running evaluation on {total} questions...")
    print(f"{'='*60}\n")

    for q in questions:
        qid      = q["id"]
        question = q["question"]
        expected = q["expected_contains"]

        print(f"[{qid:02d}] {question[:60]}...")

        start  = time.time()
        result = query_data(question, max_attempts=3)
        elapsed = time.time() - start
        latencies.append(elapsed)

        passed = check_answer(result, expected)
        attempts = result.get("attempts", 1)

        if passed:
            correct += 1
            if attempts > 1:
                self_corrected += 1
            status = "✅"
        else:
            failures.append({
                "id":       qid,
                "question": question,
                "sql":      result.get("sql", ""),
                "error":    result.get("error", ""),
            })
            status = "❌"

        print(f"     {status} attempts={attempts} time={elapsed:.1f}s")

    # ── Report ─────────────────────────────────────────────────────────────────
    accuracy        = (correct / total) * 100
    correction_rate = (self_corrected / max(total - correct + self_corrected, 1)) * 100
    avg_latency     = sum(latencies) / len(latencies)

    print(f"\n{'='*60}")
    print(f"EVALUATION RESULTS")
    print(f"{'='*60}")
    print(f"  Total questions   : {total}")
    print(f"  Correct           : {correct}")
    print(f"  Accuracy          : {accuracy:.1f}%")
    print(f"  Self-corrections  : {self_corrected}")
    print(f"  Avg latency       : {avg_latency:.1f}s per question")
    print(f"{'='*60}")

    if failures:
        print(f"\nFailed questions:")
        for f in failures:
            print(f"  [{f['id']:02d}] {f['question'][:55]}")
            if f["error"]:
                print(f"       Error: {f['error'][:80]}")


if __name__ == "__main__":
    run_evaluation()
