import json

import pytest

from exo.ingest.common import load_export_json


def test_malformed_export_raises_value_error(tmp_path):
    bad = tmp_path / "conversations.json"
    bad.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_export_json(bad, (".json",))


def test_deeply_nested_export_raises_value_error(tmp_path):
    # A pathologically nested (but structurally valid) document makes json.loads
    # hit Python's recursion limit; it must surface as a clean ValueError, not a
    # raw RecursionError traceback. Braces-only input fails fast as JSONDecodeError,
    # so use nested brackets (valid JSON) to actually reach the recursion limit.
    deep = tmp_path / "conversations.json"
    deep.write_text("[" * 50000 + "]" * 50000, encoding="utf-8")
    with pytest.raises(ValueError):
        load_export_json(deep, (".json",))


def test_valid_export_loads(tmp_path):
    good = tmp_path / "conversations.json"
    good.write_text(json.dumps([{"id": 1}]), encoding="utf-8")
    data, member = load_export_json(good, (".json",))
    assert data == [{"id": 1}]
    assert member is None
