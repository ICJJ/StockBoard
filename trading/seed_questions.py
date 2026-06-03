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


MMLU_PRO_CATEGORIES = ["economics", "business"]


def _mmlu_pro_default_loader():
    from datasets import load_dataset
    return load_dataset("TIGER-Lab/MMLU-Pro", split="test")


def seed_mmlu_pro(force: bool = False, loader=None) -> int:
    loader = loader or _mmlu_pro_default_loader
    quiz_db.init_db()
    con = quiz_db.connect()
    try:
        existing = con.execute("SELECT COUNT(*) AS c FROM questions WHERE source='mmlu_pro'").fetchone()["c"]
    finally:
        con.close()
    if existing and not force:
        print(f"mmlu_pro already seeded ({existing}); pass force=True to re-seed.")
        return 0
    if force:
        con = quiz_db.connect()
        try:
            con.execute("DELETE FROM questions WHERE source='mmlu_pro'"); con.commit()
        finally:
            con.close()
    n = 0
    for ex in loader():
        cat = ex.get("category")
        if cat not in MMLU_PRO_CATEGORIES:
            continue
        options = ex.get("options"); ai = ex.get("answer_index")
        if not (isinstance(options, list) and len(options) >= 2
                and isinstance(ai, int) and 0 <= ai < len(options)):
            continue
        quiz.add_question(ex["question"], options, ai,
                          explanation=f"正确答案:{options[ai]}",
                          subject=f"mmlu_pro:{cat}", source="mmlu_pro")
        n += 1
    print(f"seeded {n} MMLU-Pro questions")
    return n


def _normalize_financeiq(ex: dict, subject: str):
    q = ex.get("Question") or ex.get("question") or ex.get("question_text")
    if not q:
        return None
    options = ex.get("options")
    if not isinstance(options, list):
        options = []
        for key in ("A", "B", "C", "D", "E", "F"):
            v = ex.get(key)
            if v not in (None, ""):
                options.append(v)
    ans = ex.get("Answer") if ex.get("Answer") is not None else ex.get("answer")
    if isinstance(ans, str) and ans and ans[0].upper() in "ABCDEF":
        idx = "ABCDEF".index(ans[0].upper())
    elif isinstance(ans, int):
        idx = ans
    else:
        return None
    if not (len(options) >= 2 and 0 <= idx < len(options)):
        return None
    return {"question": q, "options": options, "answer_index": idx, "subject": subject}


def _financeiq_default_loader():
    from datasets import get_dataset_config_names, load_dataset
    for cfg in get_dataset_config_names("Duxiaoman-DI/FinanceIQ"):
        try:
            ds = load_dataset("Duxiaoman-DI/FinanceIQ", cfg, split="test")
        except Exception:
            continue
        for ex in ds:
            norm = _normalize_financeiq(ex, "financeiq")
            if norm:
                yield norm


def seed_financeiq(force: bool = False, loader=None) -> int:
    loader = loader or _financeiq_default_loader
    quiz_db.init_db()
    con = quiz_db.connect()
    try:
        existing = con.execute("SELECT COUNT(*) AS c FROM questions WHERE source='financeiq'").fetchone()["c"]
    finally:
        con.close()
    if existing and not force:
        print(f"financeiq already seeded ({existing}); pass force=True to re-seed.")
        return 0
    if force:
        con = quiz_db.connect()
        try:
            con.execute("DELETE FROM questions WHERE source='financeiq'"); con.commit()
        finally:
            con.close()
    n = 0
    for ex in loader():
        options = ex.get("options"); ai = ex.get("answer_index")
        if not (isinstance(options, list) and len(options) >= 2
                and isinstance(ai, int) and 0 <= ai < len(options)):
            continue
        quiz.add_question(ex["question"], options, ai,
                          explanation=f"正确答案:{options[ai]}",
                          subject=ex.get("subject", "financeiq"), source="financeiq")
        n += 1
    print(f"seeded {n} FinanceIQ questions")
    return n
