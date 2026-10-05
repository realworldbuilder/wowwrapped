import time
from pathlib import Path

from wowwrapped.archive import Archive
from wowwrapped.luaparse import parse, to_python
from wowwrapped.normalize import sessions_from_db
from wowwrapped.nights import chapter_numbers, nights
from wowwrapped.publish import export_html
from wowwrapped.export import carried_over, quest_summary, render_recap

FIXTURES = Path(__file__).parent / "fixtures"


def test_publish_roundtrip(tmp_path):
    archive = Archive(tmp_path / "archive")
    db = to_python(parse((FIXTURES / "WoWwrapped_simulated.lua").read_bytes()))["WoWwrappedDB"]
    s = sessions_from_db(db)[0]
    archive.upsert_session(s, {"capturedAt": int(time.time()), "rawSnapshot": "x", "sourceHash": "h"})
    archive.rebuild_index()
    page = export_html(s, archive, tmp_path / "exports")
    text = page.read_text()
    assert "<h1>Chapter 1" in text and "Travelled with Moonhoof" in text and "s a wrap." in text


def test_two_nights_of_one_character_are_numbered_in_order(tmp_path):
    """The client changed how it spells the name between builds; the same GUID must stay one character."""
    import copy
    archive = Archive(tmp_path / "archive")
    db = to_python(parse((FIXTURES / "WoWwrapped_simulated.lua").read_bytes()))["WoWwrappedDB"]
    first = sessions_from_db(db)[0]
    raw_second = copy.deepcopy(db["sessions"][0])
    raw_second["id"] = raw_second["id"].replace("_rambleon-birdsong", "_rambleon")
    raw_second["character"].update({"name": "Rambleon", "fullName": "Rambleon", "realmFromFullName": "Birdsong"})
    raw_second["character"].pop("displayName", None)
    raw_second["character"].pop("surname", None)
    day = 86400
    raw_second["startedAt"] += day; raw_second["endedAt"] += day; raw_second["lastSeen"] += day
    for ev in raw_second["events"]:
        ev["t"] += day
    second = sessions_from_db({"sessions": [raw_second]})[0]
    assert second["character"]["slug"] == "rambleon-birdsong"
    cap = {"capturedAt": int(time.time()), "rawSnapshot": "x", "sourceHash": "h"}
    archive.upsert_session(first, cap); archive.upsert_session(second, cap)
    archive.rebuild_index()
    both = nights(archive)
    assert [chapter_numbers(both)[n["id"]] for n in both] == [1, 2]
    assert {n["character"]["slug"] for n in both} == {"rambleon-birdsong"}
    assert {n["character"]["guid"] for n in both} == {first["character"]["guid"]}
    assert both[0]["id"] != both[1]["id"] and all(n["id"].endswith("-rambleon-birdsong") for n in both)


def test_recap_wording():
    db = to_python(parse((FIXTURES / "WoWwrapped_simulated.lua").read_bytes()))["WoWwrappedDB"]
    s = sessions_from_db(db)[0]
    recap = render_recap(s)
    assert recap.startswith("6m in Azeroth tonight.") and recap.rstrip().endswith("That's a wrap.")


# --- screenshots on the story page ---------------------------------------------------------------

import base64
import os
import shutil

from wowwrapped import publish as pub
from wowwrapped.screenshots import attach_screenshots

PNG_1x1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


def session_with_shots(tmp_path):
    db = to_python(parse((FIXTURES / "WoWwrapped_simulated.lua").read_bytes()))["WoWwrappedDB"]
    s = sessions_from_db(db)[0]
    wow_shots = tmp_path / "Screenshots"; wow_shots.mkdir()
    shots = [ev for ev in s["events"] if ev["type"] == "SCREENSHOT"]
    for n, ev in enumerate(shots):
        p = wow_shots / f"WoWScrnShot_092226_2000{n:02d}.png"
        p.write_bytes(PNG_1x1)
        os.utime(p, (ev["t"], ev["t"]))
    attach_screenshots(s, wow_shots, tmp_path / "archive" / "screenshots")
    return s


def test_story_page_places_pictures_on_the_timeline(tmp_path, monkeypatch):
    monkeypatch.setattr(pub, "RESIZER", None)
    s = session_with_shots(tmp_path)
    archive = Archive(tmp_path / "archive")
    archive.upsert_session(s, {"capturedAt": int(time.time()), "rawSnapshot": "x", "sourceHash": "h"})
    archive.rebuild_index()
    page = export_html(s, archive, tmp_path / "exports")
    text = page.read_text()
    assert "<figure class='hero'>" in text and "Marked moment in Dolanaar" in text
    assert text.count("<li class='shot'>") == 4               # five pictures: one hero, four on the timeline
    assert f"<figure class='hero'><img src='{page.stem}/{page.stem}-02.png' alt='Reached Level 11 in Dolanaar'" in text
    zone_shot = f"<li class='shot'><figure><img src='{page.stem}/{page.stem}-01.png' alt='Entered Darkshore'"
    assert text.index("Entered Auberdine (Darkshore)") < text.index(zone_shot) < text.index("Reached Level 11</li>")
    assert "Screenshots</h2>" not in text and "Took a screenshot" not in text
    assert str(tmp_path) not in text and "WoWScrnShot_" not in text
    assert sorted(p.name for p in page.with_suffix("").iterdir()) == [f"{page.stem}-0{n}.png" for n in range(1, 6)]
    index = pub.write_html_index(archive, tmp_path / "exports")
    assert "class='thumb'" in index.read_text()
    assert "class='thumb'" not in pub.write_html_index(archive, tmp_path / "exports", only=set()).read_text()


def test_web_copies_are_jpeg_when_sips_is_available(tmp_path):
    if not shutil.which("sips"):
        import pytest
        pytest.skip("sips is macOS only")
    s = session_with_shots(tmp_path)
    images = pub.prepare_images(s, tmp_path / "web" / "2026-09-22-x")
    assert [i["src"] for i in images] == [f"2026-09-22-x/2026-09-22-x-0{n}.jpg" for n in range(1, 6)]
    first = tmp_path / "web" / "2026-09-22-x" / "2026-09-22-x-01.jpg"
    assert first.read_bytes()[:2] == b"\xff\xd8"
    stamp = first.stat().st_mtime_ns
    pub.prepare_images(s, tmp_path / "web" / "2026-09-22-x")
    assert first.stat().st_mtime_ns == stamp                     # unchanged source → no rewrite


def test_tga_without_sips_is_skipped_not_broken(tmp_path, monkeypatch):
    monkeypatch.setattr(pub, "RESIZER", None)
    src = tmp_path / "WoWScrnShot_092226_200000.tga"; src.write_bytes(b"\x00" * 18)
    s = {"events": [], "screenshots": [{"path": str(src), "file": src.name, "takenAt": 1}]}
    assert pub.prepare_images(s, tmp_path / "web" / "p") == []
    assert not (tmp_path / "web" / "p").exists() or not list((tmp_path / "web" / "p").iterdir())


def two_nights(tmp_path):
    import copy
    archive = Archive(tmp_path / "archive")
    db = to_python(parse((FIXTURES / "WoWwrapped_simulated.lua").read_bytes()))["WoWwrappedDB"]
    first = sessions_from_db(db)[0]
    raw_second = copy.deepcopy(db["sessions"][0])
    raw_second["id"] += "_2"
    day = 86400
    raw_second["startedAt"] += day; raw_second["endedAt"] += day; raw_second["lastSeen"] += day
    for ev in raw_second["events"]:
        ev["t"] += day
    second = sessions_from_db({"sessions": [raw_second]})[0]
    cap = {"capturedAt": int(time.time()), "rawSnapshot": "x", "sourceHash": "h"}
    archive.upsert_session(first, cap); archive.upsert_session(second, cap)
    archive.rebuild_index()
    return archive


def test_story_pages_link_to_neighbouring_chapters(tmp_path):
    archive = two_nights(tmp_path)
    n1, n2 = nights(archive)
    p1 = export_html(n1, archive, tmp_path / "exports")
    p2 = export_html(n2, archive, tmp_path / "exports")
    t1, t2 = p1.read_text(), p2.read_text()
    assert "<nav class='top'>" in t1 and "href='index.html#rambleon-birdsong'>All chapters" in t1
    assert "<div class='jump'>" in t1 and "href='#journey'" in t1 and "<details class='journey' open>" in t1
    assert t1.count("<div class='pager") == 2 and f"class='next' href='{p2.name}'" in t1 and "class='prev'" not in t1
    assert f"class='prev' href='{p1.name}'" in t2 and "class='next'" not in t2
    # Only pages that will sit next to it on the site are linked.
    alone = export_html(n1, archive, tmp_path / "exports", siblings={p1.name}).read_text()
    assert "class='pager" not in alone and "class='next'" not in alone


def test_index_is_a_list_of_cards(tmp_path):
    import wowwrapped.publish as pub
    archive = two_nights(tmp_path)
    text = pub.write_html_index(archive, tmp_path / "exports").read_text()
    assert text.count("<a class='card'") == 2 and "<span class='n'>Chapter 2</span>" in text
    assert text.index("Chapter 2</span>") < text.index("Chapter 1</span>")      # newest first
    assert "<nav class='top'>" in text and "1 companion<" in text and "companions" not in text.split("Chapter 2")[1].split("</li>")[0]


def test_index_gives_each_character_their_own_section(tmp_path):
    """Two characters: a roster on top, then one section each (latest played first), never one mixed list."""
    import wowwrapped.publish as pub
    from helpers import _shifted
    archive, exports = Archive(tmp_path / "archive"), tmp_path / "exports"
    raw = to_python(parse((FIXTURES / "WoWwrapped_simulated.lua").read_bytes()))["WoWwrappedDB"]["sessions"][0]
    raws = [_shifted(raw, d) for d in (0, 1, 3)] + [_shifted(raw, 2, "Other")]
    cap = {"capturedAt": int(time.time()), "rawSnapshot": "x", "sourceHash": "h"}
    for s in sessions_from_db({"sessions": raws}):
        archive.upsert_session(s, cap)
    archive.rebuild_index()
    text = pub.write_html_index(archive, exports).read_text()
    assert "<h1>Adventure Journal</h1>" in text and "2 characters · 4 chapters" in text
    assert "<a class='char' href='#rambleon-birdsong'>" in text and "<a class='char' href='#rambleon-birdsongother'>" in text
    mine, other = text.index("<section class='who' id='rambleon-birdsong'>"), text.index("<section class='who' id='rambleon-birdsongother'>")
    assert mine < other                                               # the character played last comes first
    assert text[mine:other].count("<a class='card'") == 3 and text[other:].count("<a class='card'") == 1
    assert "Chapter 1</span>" in text[other:] and "Chapter 3</span>" in text[mine:other]
    assert "Night Elf Druid · Alliance" in text[mine:other] and "3 chapters" in text[mine:other] and "1 chapter ·" in text[:mine]
    # A shared subset with one character left falls back to that character's own page, whoever played last overall.
    theirs = {pub._page_name(n) for n in nights(archive, "rambleon-birdsongother")}
    alone = pub.write_html_index(archive, exports, only=theirs, out=tmp_path / "i.html").read_text()
    assert "<h1 id='rambleon-birdsongother'>" in alone and "class='roster'" not in alone and alone.count("<a class='card'") == 1


def _fixture_session():
    db = to_python(parse((FIXTURES / "WoWwrapped_simulated.lua").read_bytes()))["WoWwrappedDB"]
    return sessions_from_db(db)[0]


def test_quests_dedupe_across_sessions():
    from wowwrapped.nights import build_night
    a = _fixture_session()
    b = dict(a, id=a["id"] + "-later", startedAt=a["startedAt"] + 3600, endedAt=a["endedAt"] + 3600,
             events=[dict(e, t=e["t"] + 3600) for e in a["events"]])
    night = build_night([a, b])
    q = quest_summary(night)
    assert [e["questID"] for e in q["completed"]] == [123]
    assert [e["questID"] for e in q["open"]] == [124]


def _quest_ev(kind, qid, title, t, zone="Darkshore", subzone="Auberdine"):
    return {"type": kind, "questID": qid, "title": title, "t": t, "level": 14, "zone": zone, "subzone": subzone}


def _night_with(base, events, offset):
    from wowwrapped.nights import build_night
    s = dict(base, id=f"{base['id']}-{offset}", startedAt=base["startedAt"] + offset, endedAt=base["endedAt"] + offset,
             events=[dict(e, t=e["t"] + offset) for e in events])
    return build_night([s])


def test_carried_over_quests():
    base = _fixture_session()
    day, t0 = 86400, base["startedAt"]
    quiet = [e for e in base["events"] if not e["type"].startswith("QUEST_")]
    n1 = _night_with(base, quiet + [_quest_ev("QUEST_ACCEPTED", 200, "Fruit of the Sea", t0 + 10),
                                    _quest_ev("QUEST_ACCEPTED", 201, "WANTED: Murkdeep!", t0 + 20),
                                    _quest_ev("QUEST_COMPLETED", 201, "WANTED: Murkdeep!", t0 + 30)], 0)
    n2 = _night_with(base, quiet, day)
    assert [(ev["questID"], k) for ev, k in carried_over([n1], n2)] == [(200, 1)]
    done = _night_with(base, quiet + [_quest_ev("QUEST_COMPLETED", 200, "Fruit of the Sea", t0 + 5)], day)
    assert carried_over([n1], done) == []
    again = _night_with(base, quiet + [_quest_ev("QUEST_ACCEPTED", 200, "Fruit of the Sea", t0 + 5)], day)
    assert carried_over([n1], again) == []      # tonight's own "picked up" covers it
    n3 = _night_with(base, quiet, 2 * day)
    assert [(ev["questID"], k) for ev, k in carried_over([n1, n2], n3)] == [(200, 1)]
    assert carried_over([], n1) == []


def _page(tmp_path, *nights_):
    archive = Archive(tmp_path / "archive")
    cap = {"capturedAt": int(time.time()), "rawSnapshot": "x", "sourceHash": "h"}
    for n in nights_:
        archive.upsert_session(n, cap)
    archive.rebuild_index()
    return archive, nights(archive)


def test_story_page_lists_quests_turned_in_and_still_open(tmp_path):
    s = _fixture_session()
    text = export_html(s, Archive(tmp_path / "a"), tmp_path / "exports").read_text()
    assert "href='#quests'>Quests</a>" in text and "<h2 id='quests'>Quests</h2>" in text
    assert text.index("href='#recap'") < text.index("href='#quests'") < text.index("href='#journey'")
    assert text.index("<div class='stats'>") < text.index("<h2 id='quests'>") < text.index("<h2 id='journey'>")
    assert "<div class='quests'><div class='tabs' role='tablist'>" in text
    assert "<button role='tab' aria-selected='true' data-pane='done'>Turned in<span class='n'>1</span></button>" in text
    assert "<button role='tab' aria-selected='false' data-pane='open'>Still open<span class='n'>1</span></button>" in text
    assert ("<div class='pane on' id='qpane-done' role='tabpanel'><table><thead><tr><th>Quest</th><th>Turned in at</th><th>Lv</th></tr></thead>"
            "<tbody><tr class='zone'><th colspan='3'>Teldrassil</th></tr><tr><td class='quest'>The Emerald Dreamcatcher</td>"
            "<td class='where'>Dolanaar</td><td class='lv'>10</td></tr></tbody></table></div>") in text
    assert "<div class='pane' id='qpane-open' role='tabpanel'><table>" in text and "<td class='quest'>Precious Waters</td><td class='where'>Dolanaar</td>" in text
    assert "data-pane='carried'" not in text and "class='caveat'" not in text and "<script>" in text
    quiet = dict(s, events=[e for e in s["events"] if not e["type"].startswith("QUEST_")])
    text = export_html(quiet, Archive(tmp_path / "b"), tmp_path / "exports2").read_text()
    assert "#quests" not in text and "<h2 id='quests'>" not in text


def test_story_page_carries_open_quests_forward(tmp_path):
    base = _fixture_session()
    quiet = [e for e in base["events"] if not e["type"].startswith("QUEST_")]
    t0 = base["startedAt"]
    first = _night_with(base, quiet + [_quest_ev("QUEST_ACCEPTED", 200, "Fruit of the Sea", t0 + 10)], 0)
    second = _night_with(base, quiet + [_quest_ev("QUEST_ACCEPTED", 300, "The Tower of Althalaxx", t0 + 10),
                                        _quest_ev("QUEST_COMPLETED", 300, "The Tower of Althalaxx", t0 + 20)], 86400)
    archive, (n1, n2) = _page(tmp_path, first, second)
    t1 = export_html(n1, archive, tmp_path / "exports").read_text()
    t2 = export_html(n2, archive, tmp_path / "exports").read_text()
    assert "data-pane='carried'" not in t1 and "data-pane='open'>Still open<span class='n'>1</span>" in t1
    assert "<button role='tab' aria-selected='false' data-pane='carried'>Carrying<span class='n'>1</span></button>" in t2
    assert ("<tr><td class='quest'>Fruit of the Sea</td><td class='where'>Auberdine</td><td class='since'>Chapter 1</td></tr></tbody></table>"
            "<p class='caveat'>") in t2
    assert "data-pane='open'" not in t2 and "aria-selected='true' data-pane='done'>Turned in<span class='n'>1</span>" in t2
