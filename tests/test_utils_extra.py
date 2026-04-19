from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from skill_auditor.utils import (
    atomic_write_json, atomic_write_text, dataclass_to_dict,
    make_run_id, utc_now,
)


def test_atomic_write_json_creates_file(tmp_path):
    path = tmp_path / "out.json"
    atomic_write_json(path, {"key": "value"})
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["key"] == "value"


def test_atomic_write_json_creates_parent_dirs(tmp_path):
    path = tmp_path / "a" / "b" / "c" / "out.json"
    atomic_write_json(path, {"nested": True})
    assert path.exists()


def test_atomic_write_json_overwrites(tmp_path):
    path = tmp_path / "out.json"
    atomic_write_json(path, {"v": 1})
    atomic_write_json(path, {"v": 2})
    data = json.loads(path.read_text())
    assert data["v"] == 2


def test_atomic_write_text_creates_file(tmp_path):
    path = tmp_path / "out.txt"
    atomic_write_text(path, "hello world\n")
    assert path.read_text() == "hello world\n"


def test_atomic_write_text_creates_parent_dirs(tmp_path):
    path = tmp_path / "x" / "y" / "out.txt"
    atomic_write_text(path, "content")
    assert path.exists()


def test_make_run_id_format():
    rid = make_run_id()
    assert len(rid) > 0
    assert "T" in rid
    assert "Z" in rid


def test_make_run_id_unique():
    ids = {make_run_id() for _ in range(10)}
    assert len(ids) == 10


def test_utc_now_format():
    now = utc_now()
    assert "+" in now or "Z" in now
    assert "T" in now


@dataclass
class Inner:
    x: int
    y: str


@dataclass
class Outer:
    items: list
    inner: Inner


def test_dataclass_to_dict_nested():
    obj = Outer(items=[Inner(1, "a"), Inner(2, "b")], inner=Inner(3, "c"))
    result = dataclass_to_dict(obj)
    assert result["inner"]["x"] == 3
    assert len(result["items"]) == 2
    assert result["items"][0]["y"] == "a"


def test_dataclass_to_dict_plain():
    assert dataclass_to_dict(42) == 42
    assert dataclass_to_dict("hello") == "hello"


def test_dataclass_to_dict_list():
    result = dataclass_to_dict([Inner(1, "a")])
    assert result == [{"x": 1, "y": "a"}]


def test_dataclass_to_dict_dict():
    result = dataclass_to_dict({"key": Inner(5, "z")})
    assert result == {"key": {"x": 5, "y": "z"}}
