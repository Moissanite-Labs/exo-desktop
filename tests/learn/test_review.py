import asyncio

from exo.core.types import ContentPart, Message
from exo.learn.review import needs_review, run_review
from helpers import scripted_model


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


def test_turn_triggered_review_runs_without_signals(learner):
    # End-to-end: a turn/periodic-triggered review with no correction signals must
    # actually run (status "done", a learn_review note recorded), not early-return
    # "nothing_new". This is the gap the trigger fix alone left (issue 3).
    rt = learner.runtime
    learner._complete = scripted_model()
    info = learner.engine.store.create_session(title="chat", model="fake:x", cwd=".")
    learner.engine.store.append_message(
        info.id, Message(role="user", content=[ContentPart.of_text("hello there")]), "t1")
    out = asyncio.run(run_review(learner, info.id, "turns"))
    assert out["status"] == "done"
    assert any((e.get("body") or {}).get("type") == "learn_review"
               for e in rt.ledger.iter(kind="note"))


def test_manual_review_without_signals_is_still_nothing_new(learner):
    # A manual review with nothing to learn keeps its historical behaviour.
    learner._complete = scripted_model()
    info = learner.engine.store.create_session(title="chat", model="fake:x", cwd=".")
    learner.engine.store.append_message(
        info.id, Message(role="user", content=[ContentPart.of_text("hi")]), "t1")
    out = asyncio.run(run_review(learner, info.id, "manual"))
    assert out["status"] == "nothing_new"

