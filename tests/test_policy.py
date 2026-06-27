from app.graph.policy import classify, requires_approval


def test_known_write_requires_approval():
    assert classify("quarantine_host") == "write"
    assert requires_approval("quarantine_host") is True


def test_read_no_approval():
    assert classify("navigate") == "read"
    assert requires_approval("navigate") is False


def test_unknown_action_fails_closed():
    assert classify("frobnicate") == "write"
    assert requires_approval("frobnicate") is True


def test_escalate_is_not_a_write():
    assert classify("escalate") == "escalate"
    assert requires_approval("escalate") is False
