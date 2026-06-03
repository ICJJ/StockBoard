"""Weekly quiz-bank maintenance.

Claude SELECTS / PRUNES from the already-verified pool only — it never authors
questions or answers. Pruning retires questions the community flagged
(remove >= 3 and remove > keep). Top-up is intentionally a no-op: the bank was
fully imported from the MMLU subsets, so there is nothing more to select from
the same verified source; if the active pool ever drops below MIN_ACTIVE we just
advise a manual re-seed.

Run:  PYTHONPATH=. ./.venv-trading/bin/python -m trading.maintain_bank
"""
from . import quiz, quiz_db

MIN_ACTIVE = 60


def maintain() -> dict:
    quiz_db.init_db()
    retired = quiz.prune_flagged()
    active = quiz.count_active()
    print(f"pruned {len(retired)} flagged question(s); active remaining = {active}")
    if active < MIN_ACTIVE:
        print(f"WARNING: active pool below {MIN_ACTIVE} — re-seed verified questions with: "
              f"PYTHONPATH=. ./.venv-trading/bin/python -m trading.seed_questions --force")
    return {"retired": len(retired), "retired_ids": retired, "active_remaining": active}


if __name__ == "__main__":
    maintain()
