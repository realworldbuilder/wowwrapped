import os
import sys
import time
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """No test reads this Mac's wowwrapped.local.toml, depends on its timezone, or reaches a real service."""
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    for name in list(os.environ):
        if name.startswith("WOWWRAPPED_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("WOWWRAPPED_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("WOWWRAPPED_WOW_DIR", str(tmp_path / "no-wow"))      # never this Mac's World of Warcraft
    for target in ("wowwrapped.notify.notify", "wowwrapped.cli.notify", "wowwrapped.pipeline.notify"):
        monkeypatch.setattr(target, lambda *a, **k: None)
    monkeypatch.setattr("wowwrapped.writer.claude_available", lambda: None)
    yield
    monkeypatch.undo()
    time.tzset()
