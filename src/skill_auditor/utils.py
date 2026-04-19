from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid4().hex[:8]}"


def make_instance_id(ecosystem: str, path: Path) -> str:
    digest = hashlib.sha256(f"{ecosystem}:{path.resolve()}".encode("utf-8")).hexdigest()
    return digest[:16]


def compute_directory_fingerprint(skill_dir: Path) -> str:
    hasher = hashlib.sha256()
    for file_path in sorted(path for path in skill_dir.rglob("*") if path.is_file()):
        hasher.update(file_path.relative_to(skill_dir).as_posix().encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(file_path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def read_text_file(path: Path) -> str | None:
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".{path.name}.tmp-{os.getpid()}-{uuid4().hex[:6]}"
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    temp_path.replace(path)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".{path.name}.tmp-{os.getpid()}-{uuid4().hex[:6]}"
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def dataclass_to_dict(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [dataclass_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: dataclass_to_dict(item) for key, item in value.items()}
    return value


def tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    tokens = []
    current = []
    for char in text.lower():
        if char.isalnum():
            current.append(char)
            continue
        if current:
            token = "".join(current)
            if token not in STOPWORDS:
                tokens.append(token)
            current = []
    if current:
        token = "".join(current)
        if token not in STOPWORDS:
            tokens.append(token)
    return set(tokens)
