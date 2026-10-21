import json

import pytest


@pytest.fixture
def database(tmp_path):
    return tmp_path / "archive.sqlite3"


@pytest.fixture
def write_json(tmp_path):
    def _write(name: str, payload):
        path = tmp_path / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    return _write
