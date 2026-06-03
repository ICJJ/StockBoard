def test_maintain_reports(quiz_db):
    from trading import quiz, maintain_bank
    keep_q = quiz.add_question("keep", ["a", "b", "c", "d"], 0)
    drop_q = quiz.add_question("drop", ["a", "b", "c", "d"], 0)
    for u in (1, 2, 3):
        quiz.record_feedback(u, drop_q, "remove")
    report = maintain_bank.maintain()
    assert report["retired"] == 1
    assert report["active_remaining"] == 1
    assert drop_q in report["retired_ids"]
    assert keep_q not in report["retired_ids"]


def test_prune_flagged_retires_only_clear_removes(quiz_db):
    from trading import quiz
    q_remove = quiz.add_question("retire me", ["a", "b", "c", "d"], 0)
    q_split = quiz.add_question("contested", ["a", "b", "c", "d"], 0)
    q_few = quiz.add_question("barely", ["a", "b", "c", "d"], 0)
    for u in (1, 2, 3):
        quiz.record_feedback(u, q_remove, "remove")
    for u in (1, 2, 3):
        quiz.record_feedback(u, q_split, "remove")
    for u in (4, 5, 6):
        quiz.record_feedback(u, q_split, "keep")
    for u in (1, 2):
        quiz.record_feedback(u, q_few, "remove")
    assert quiz.count_active() == 3
    retired = quiz.prune_flagged()
    assert retired == [q_remove]
    assert quiz.count_active() == 2
    assert quiz.get_question(q_remove)["status"] == "retired"
