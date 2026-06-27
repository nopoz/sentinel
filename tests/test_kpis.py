from app.graph.executor import estimate_cost


def test_sonnet_cost():
    # 1M input + 1M output on sonnet = 3 + 15 = 18.0
    assert round(estimate_cost("claude-sonnet-4-6", 1_000_000, 1_000_000), 2) == 18.0


def test_opus_cost():
    assert round(estimate_cost("claude-opus-4-8", 1_000_000, 1_000_000), 2) == 30.0
