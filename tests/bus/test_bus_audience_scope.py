"""Bus reads (relay /v1/messages and the store thread/search used by MCP) must be scoped to the
caller's audiences, so a seat cannot read messages not addressed to it (issue 9)."""
from .conftest import Bus  # noqa: F401  (bus fixture lives in conftest)


def test_relay_messages_scoped_to_caller(bus):
    st, _, _ = bus.post("alpha", ["seat:beta"], "secret for beta only")
    assert st == 201
    # The addressee can read it.
    st2, data2, raw2 = bus.get("beta", "/v1/messages")
    assert st2 == 200, raw2
    assert "secret for beta only" in [m["body"] for m in data2]
    # An unrelated seat cannot.
    st3, data3, raw3 = bus.get("gamma", "/v1/messages")
    assert st3 == 200, raw3
    assert "secret for beta only" not in [m["body"] for m in data3]


def test_store_messages_and_search_scoped(bus):
    bus.post("alpha", ["seat:beta"], "needle-beta")
    # Scoped store reads back the message for beta, hide it from gamma. This is the
    # same store path the MCP read_thread/search tools now use.
    beta_rows = bus.relay.store.messages(audiences=["seat:beta"])
    assert any(r["body"] == "needle-beta" for r in beta_rows)
    gamma_rows = bus.relay.store.messages(audiences=["seat:gamma"])
    assert not any(r["body"] == "needle-beta" for r in gamma_rows)

    beta_hits = bus.relay.store.search("needle-beta", audiences=["seat:beta"])
    assert any("needle-beta" in r["body"] for r in beta_hits)
    gamma_hits = bus.relay.store.search("needle-beta", audiences=["seat:gamma"])
    assert not any("needle-beta" in r["body"] for r in gamma_hits)
