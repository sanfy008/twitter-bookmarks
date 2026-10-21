import json

import pytest

from x_local_archive.cli import main
from x_local_archive.db import import_json, stats


def test_cli_version(capsys):
    from x_local_archive import __version__

    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_cli_rejects_mismatched_payload_type(write_json, database, capsys):
    source = write_json(
        "export.json",
        {"type": "like", "tweets": [{"id": "1", "text": "x"}]},
    )
    code = main(
        [
            "--database",
            str(database),
            "import",
            str(source),
            "--account",
            "owner",
            "--type",
            "bookmark",
        ]
    )
    assert code == 2
    assert "does not match" in capsys.readouterr().out


def test_cli_stats_prune_and_forget(write_json, database, capsys):
    source = write_json(
        "export.json",
        {
            "tweets": [
                {"id": "1", "text": "real", "username": "alice"},
                {"id": "2", "text": "", "author_username": "unknown"},
            ]
        },
    )
    import_json(database, source, "alice", "bookmark")

    assert main(["--database", str(database), "stats"]) == 0
    assert '"tweets": 2' in capsys.readouterr().out

    assert main(["--database", str(database), "prune", "--dry-run"]) == 0
    assert '"empty_text": 1' in capsys.readouterr().out
    assert stats(database)["tweets"] == 2

    assert main(["--database", str(database), "prune"]) == 0
    assert stats(database)["tweets"] == 1

    assert main(["--database", str(database), "forget", "--account", "ALICE"]) == 0
    assert '"removed": true' in capsys.readouterr().out
    assert stats(database)["tweets"] == 0


def test_cli_search_filters(write_json, database, capsys):
    source = write_json(
        "export.json", {"tweets": [{"id": "1", "text": "投资", "username": "alice"}]}
    )
    import_json(database, source, "alice", "bookmark")
    assert main(["--database", str(database), "search", "投资", "--type", "bookmark"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output[0]["id"] == "1"
