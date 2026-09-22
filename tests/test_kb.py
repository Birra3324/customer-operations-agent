from app.tools import clear_fixture_cache, lookup_kb
from app.tools import LookupKbArgs, ToolContext


def test_kb_ranks_expected_article():
    clear_fixture_cache()
    billing = lookup_kb(
        ToolContext(db=None),
        LookupKbArgs(query="Duplicate TraceLight invoice charged twice"),
    )
    password = lookup_kb(
        ToolContext(db=None),
        LookupKbArgs(query="Cannot sign in forgot password reset email"),
    )
    escalated = lookup_kb(
        ToolContext(db=None),
        LookupKbArgs(query="Need a human outage escalate ops queue"),
    )
    assert billing["articles"][0]["id"] == "kb-billing-invoices"
    assert password["articles"][0]["id"] == "kb-password-reset"
    assert escalated["articles"][0]["id"] == "kb-escalate-human"
