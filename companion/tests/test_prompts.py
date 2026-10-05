import time
from pathlib import Path

import pytest

from wowwrapped import pages, prompts
from wowwrapped.archive import Archive
from wowwrapped.luaparse import parse, to_python
from wowwrapped.normalize import sessions_from_db
from wowwrapped.publish import export_html, write_html_index
from wowwrapped.writer import available_voices, load_voice

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("WOWWRAPPED_HOME", str(home))
    return home


def session() -> dict:
    return sessions_from_db(to_python(parse((FIXTURES / "WoWwrapped_simulated.lua").read_bytes()))["WoWwrappedDB"])[0]


def test_bundled_voices():
    assert available_voices() == ["field-journal", "golden"] and "Christie Golden" in load_voice("golden")


def test_your_own_voice(home, tmp_path):
    (home / "prompts" / "voices").mkdir(parents=True)
    (home / "prompts" / "voices" / "saga.md").write_text("Write it like an old saga.\n")
    (home / "prompts" / "voices" / "golden.md").write_text("My own golden.\n")           # yours wins over the bundled one
    assert available_voices() == ["field-journal", "golden", "saga"]
    assert load_voice("saga") == "Write it like an old saga." and load_voice(None) == "My own golden."
    assert prompts.is_yours(prompts.available("voices")["golden"]) and not prompts.is_yours(prompts.available("voices")["field-journal"])
    elsewhere = tmp_path / "terse.md"
    elsewhere.write_text("Three sentences. No more.\n")
    assert load_voice(str(elsewhere)) == "Three sentences. No more."                      # a path works wherever a name does
    with pytest.raises(ValueError, match="unknown voice 'nope'; available: field-journal, golden, saga"):
        load_voice("nope")


def test_your_own_theme_is_added_to_every_page(home, tmp_path):
    s = session()
    archive = Archive(tmp_path / "archive")
    archive.upsert_session(s, {"capturedAt": int(time.time()), "rawSnapshot": "x", "sourceHash": "h"})
    archive.rebuild_index()
    plain = export_html(s, archive, tmp_path / "exports").read_text()
    assert "theme.css" not in plain and pages.css().startswith("\n:root{")
    (home / "prompts").mkdir(parents=True)
    (home / "prompts" / "theme.css").write_text(":root{--paper:#101418;--ink:#e8e2d0}\n")
    themed = export_html(s, archive, tmp_path / "exports").read_text()
    index = write_html_index(archive, tmp_path / "exports").read_text()
    for text in (themed, index):
        assert text.index("--paper:#f5ecd8") < text.index("/* prompts/theme.css */") < text.index("--paper:#101418") < text.index("</style>")
