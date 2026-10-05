"""Nights to test with: the fixture evening, shifted by days and to other characters."""
import copy
import time
from pathlib import Path

from wowwrapped.archive import Archive
from wowwrapped.luaparse import parse, to_python
from wowwrapped.nights import nights
from wowwrapped.normalize import sessions_from_db

FIXTURES = Path(__file__).parent / "fixtures"
DAY = 86400


def _shifted(raw: dict, days: int, slug_suffix: str | None = None) -> dict:
    s = copy.deepcopy(raw)
    s["id"] = f"{s['id']}-d{days}"
    for k in ("startedAt", "endedAt", "lastSeen"):
        s[k] += days * DAY
    for ev in s["events"]:
        ev["t"] += days * DAY
    for p in s.get("people", []):
        for k in ("firstSeen", "lastSeen"):
            if p.get(k):
                p[k] += days * DAY
    if slug_suffix:
        for k in ("name", "fullName", "displayName"):
            if s["character"].get(k):
                s["character"][k] = s["character"][k] + slug_suffix
        s["character"]["guid"] = s["character"]["guid"] + slug_suffix
        s["id"] = s["id"] + slug_suffix
    return s


def three_nights(tmp_path):
    """Three nights of the fixture character a day apart, plus an earlier night of another character."""
    archive = Archive(tmp_path / "archive")
    db = to_python(parse((FIXTURES / "WoWwrapped_simulated.lua").read_bytes()))["WoWwrappedDB"]
    raw = db["sessions"][0]
    raws = [_shifted(raw, 0), _shifted(raw, 1), _shifted(raw, 2), _shifted(raw, -1, "Other")]
    cap = {"capturedAt": int(time.time()), "rawSnapshot": "x", "sourceHash": "h"}
    for s in sessions_from_db({"sessions": raws}):
        archive.upsert_session(s, cap)
    archive.rebuild_index()
    slug = sessions_from_db({"sessions": [raws[0]]})[0]["character"]["slug"]
    n1, n2, n3 = nights(archive, slug)
    assert nights(archive)[0]["character"]["slug"] != slug   # the other character's night comes first overall
    return archive, tmp_path / "exports", n1, n2, n3
