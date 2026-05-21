from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from backend.storage.json_store import JsonStore


def test_round_trip(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    data = store.read()
    data["ledger"].append({"id": "01", "date": "2026-01-01", "desc": "Test", "category": "Food", "amount": -10.0})
    store.write(data)
    reloaded = store.read()
    assert reloaded["ledger"][0]["desc"] == "Test"


def test_fresh_document_has_defaults(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    doc = store.read()
    assert "ledger" in doc
    assert "auth" in doc
    assert doc["auth"]["username"] == "admin"
    assert doc["auth"]["password_hash"] is not None and doc["auth"]["password_hash"].startswith("$argon2")


def test_backup_created_on_write(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    doc = store.read()
    store.write(doc)
    assert not (tmp_path / "hearth.json.bak").exists()  # no bak on first write (no prior file)
    store.write(doc)
    assert (tmp_path / "hearth.json.bak").exists()


def test_concurrent_writes(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    doc = store.read()
    store.write(doc)

    errors: list[Exception] = []

    def writer(n: int) -> None:
        try:
            def _apply(d: dict) -> None:
                d["ledger"].append({"id": str(n), "date": "2026-01-01", "desc": f"tx{n}", "category": "X", "amount": float(-n)})
            store.mutate(_apply)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    final = store.read()
    assert len(final["ledger"]) == 10


def test_recover_from_malformed(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    good_doc = store.read()
    good_doc["ledger"].append({"id": "bak1", "date": "2026-01-01", "desc": "backed up", "category": "X", "amount": 0.0})
    store.write(good_doc)
    store.write(good_doc)  # second write creates the .bak

    # Corrupt the main file
    (tmp_path / "hearth.json").write_text("not json!!!")

    recovered = store.read()
    assert recovered["ledger"][0]["id"] == "bak1"
