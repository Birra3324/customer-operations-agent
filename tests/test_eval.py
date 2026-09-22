from app.agent.classify import classify
from app.agent.eval_harness import evaluate_all, load_scenarios


def test_classify_examples():
    billing = classify(
        "Duplicate TraceLight invoice",
        "We were charged twice for the September invoice.",
    )
    assert billing.intent == "billing"
    assert billing.priority == "medium"
    assert billing.status == "resolved"

    password = classify(
        "Cannot sign in to AlertMesh",
        "I forgot my password and the reset email never arrived.",
    )
    assert password.intent == "password_reset"
    assert password.priority == "high"

    escalated = classify(
        "Need a human",
        "This looks like an outage. Please escalate to a person on the ops queue.",
    )
    assert escalated.intent == "escalation"
    assert escalated.priority == "urgent"
    assert escalated.status == "escalated"

    general = classify("Question about TraceLight", "What does the product do?")
    assert general.intent == "general"
    assert general.priority == "low"
    assert general.status == "waiting_customer"


def test_golden_scenarios(db_session):
    results = evaluate_all(db_session)
    assert [row["id"] for row in results] == [scenario["id"] for scenario in load_scenarios()]
    failed = [row for row in results if not row["ok"]]
    assert failed == []
