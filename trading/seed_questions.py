"""One-time seed: import MMLU professional/finance subsets (verified answers, MIT)
into the questions table.

Run for real:  PYTHONPATH=. ./.venv-trading/bin/python -m trading.seed_questions [--force]
(`datasets` is imported lazily so the test suite needs neither the dep nor network.)
"""
from __future__ import annotations

import sys

from . import quiz, quiz_db

SUBJECTS = [
    "professional_accounting",
    "high_school_macroeconomics",
    "high_school_microeconomics",
    "econometrics",
]


def _default_loader(subject: str):
    from datasets import load_dataset
    return load_dataset("cais/mmlu", subject, split="test")


def seed(force: bool = False, loader=None) -> int:
    loader = loader or _default_loader
    quiz_db.init_db()
    if quiz.count_active() > 0 and not force:
        print(f"already seeded ({quiz.count_active()} active questions); use --force to re-seed.")
        return 0
    if force:
        con = quiz_db.connect()
        try:
            con.execute("DELETE FROM questions WHERE source='mmlu'")
            con.commit()
        finally:
            con.close()
    n = 0
    for subject in SUBJECTS:
        for ex in loader(subject):
            choices = ex.get("choices")
            answer = ex.get("answer")
            if not (isinstance(choices, list) and len(choices) == 4
                    and isinstance(answer, int) and 0 <= answer < 4):
                continue
            quiz.add_question(
                ex["question"], choices, answer,
                explanation=f"正确答案:{choices[answer]}",
                subject=subject, source="mmlu", status="active",
            )
            n += 1
    print(f"seeded {n} questions; active total = {quiz.count_active()}")
    return n


if __name__ == "__main__":
    seed(force="--force" in sys.argv)
