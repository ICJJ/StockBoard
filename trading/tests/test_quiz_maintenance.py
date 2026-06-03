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
