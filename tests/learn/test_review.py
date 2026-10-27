from exo.learn.review import needs_review


def test_turn_count_triggers_review_without_signals():
    # The documented "review after N turns" path must fire even when no
    # correction/ruling signal is pending. It was previously gated behind
    # `events and`, so ordinary conversation never reached a review.
    assert needs_review([], turns=5, every=3) == "turns"


def test_signal_always_wins_over_turn_count():
    ruling = {"kind": "ruling", "body": {}, "author": "principal"}
    assert needs_review([ruling], turns=1, every=100) == "signal"


def test_below_threshold_returns_none():
    assert needs_review([], turns=2, every=3) is None
