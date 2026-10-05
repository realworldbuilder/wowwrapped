"""The Wrapped: nights summed, cards from the numbers alone, narration only when the writer is there."""
import pytest

from helpers import three_nights
from wowwrapped import wrapped as wr
from wowwrapped.nights import nights
from wowwrapped.publish import export_html, write_html_index
from wowwrapped.wrapped import build_wrapped, cards, span, split_output, write_wrapped, zone_seconds

SLUG = "rambleon-birdsong"


def test_nights_are_summed(tmp_path):
    archive, exports, n1, n2, n3 = three_nights(tmp_path)
    one, all_ = build_wrapped([n1]), build_wrapped(nights(archive, SLUG))
    assert all_["totals"]["nights"] == 3 and all_["nightIds"] == [n1["id"], n2["id"], n3["id"]]
    for key in ("playedSeconds", "quests", "kills", "deaths", "xp"):
        assert all_["totals"][key] == 3 * one["totals"][key], key
    assert all_["totals"]["places"] == one["totals"]["places"] and all_["totals"]["people"] == one["totals"]["people"]   # the same ones
    assert all_["topPeople"][0]["name"] == "Moonhoof" and all_["topPeople"][0]["nights"] == 3
    assert all_["topEnemies"][0]["count"] == 3 * one["topEnemies"][0]["count"]
    assert (all_["totals"]["startLevel"], all_["totals"]["endLevel"], all_["totals"]["levels"]) == (10, 12, 2)
    assert sum(z["seconds"] for z in all_["topZones"]) == pytest.approx(all_["totals"]["playedSeconds"], abs=5)
    assert sum(zone_seconds(n1).values()) == pytest.approx(n1["playedSeconds"])        # the zones add up to the night


def test_a_range_takes_only_its_nights(tmp_path):
    archive, exports, n1, n2, n3 = three_nights(tmp_path)
    own = nights(archive, SLUG)
    assert build_wrapped(own, since=n2["nightDate"])["nightIds"] == [n2["id"], n3["id"]]
    assert build_wrapped(own, until=n1["nightDate"])["nightIds"] == [n1["id"]]
    with pytest.raises(ValueError, match="no nights in that range"):
        build_wrapped(own, since="2030-01-01")
    assert span(month="2026-09") == wr.Span("2026-09-01", "2026-09-31", "2026-09", "September 2026")
    assert span(year="2026").key == "2026" and span().key is None and span(since="2026-09-21").key == "2026-09-21_now"
    for bad in ({"month": "sept"}, {"since": "yesterday"}, {"month": "2026-09", "year": "2026"}):
        with pytest.raises(ValueError):
            span(**bad)


def test_a_card_with_nothing_to_show_is_left_out(tmp_path):
    archive, exports, n1, n2, n3 = three_nights(tmp_path)
    full = {c["key"] for c in cards(build_wrapped([n1]))}
    assert {"intro", "time", "levels", "quests", "enemies", "zones", "people", "deaths", "rhythm", "notes", "persona"} <= full
    quiet = dict(n1, people=[], kills={}, screenshots=[], counters=dict(n1["counters"], deaths=0, kills=0),
                 events=[e for e in n1["events"] if e["type"] not in ("DEATH", "NOTE", "LOOT", "EQUIP", "BOSS_KILL", "INSTANCE_ENTER")])
    deck = {c["key"]: c for c in cards(build_wrapped([quiet]))}
    assert not {"people", "enemies", "notes", "loot", "dungeons", "pictures"} & set(deck)
    assert deck["deaths"]["big"] == "0" and deck["deaths"]["caption"] == "Not one."
    # only night pages that will sit beside the Wrapped are linked
    linked = cards(build_wrapped([n1, n2]), linked=set())
    assert all(not c.get("link") for c in linked)


def test_the_page_is_complete_without_the_writer(tmp_path):
    archive, exports, n1, n2, n3 = three_nights(tmp_path)
    logs: list[str] = []
    result = write_wrapped(archive, exports, SLUG, log=logs.append)            # no claude CLI in tests
    text = result["html"].read_text()
    assert result["html"].name == "wrapped-rambleon-birdsong.html" and result["nights"] == 3 and not result["narrated"]
    assert any("built from the facts" in m for m in logs)
    assert "<body class='wrapped'>" in text and ".slide{" in text and text.count("<section class='slide") >= 10
    assert "Moonhoof" in text and "class='line'" not in text and "That's a wrap." in text
    prompt = result["prompt"].read_text()
    assert "{voice}" not in prompt and "{name}" not in prompt and "- time: Time in Azeroth:" in prompt and "Pronouns for Rambleon Birdsong: " in prompt
    # the night pages and the index link to it once it is there
    assert "wrapped-rambleon-birdsong.html'>Wrapped</a>" in export_html(n3, archive, exports).read_text()
    assert "wrapped-rambleon-birdsong.html'>Wrapped</a>" in write_html_index(archive, exports).read_text()
    month = write_wrapped(archive, exports, SLUG, span(month=n1["nightDate"][:7]), use_ai=False, log=logs.append)
    assert month["html"].name == f"wrapped-rambleon-birdsong-{n1['nightDate'][:7]}.html"


def test_the_writer_adds_a_line_per_card_and_is_not_asked_twice(tmp_path, monkeypatch):
    archive, exports, n1, n2, n3 = three_nights(tmp_path)
    asked: list[str] = []
    reply = "time: Six minutes at a time, it added up.\nbogus: never shown\n- **zones**: Teldrassil kept him.\n---CLOSING---\nA short road,\nwalked well."
    monkeypatch.setattr("wowwrapped.writer.claude_available", lambda: "/bin/claude")
    monkeypatch.setattr("wowwrapped.writer.run_claude", lambda prompt, model: (asked.append(model) or reply, "ok"))
    result = write_wrapped(archive, exports, SLUG, log=lambda m: None, only_if_new=True)
    text = result["html"].read_text()
    assert result["narrated"] and asked == ["sonnet"]
    assert "<p class='line'>Six minutes at a time, it added up.</p>" in text and "Teldrassil kept him." in text
    assert "never shown" not in text and "<p class='closing'>A short road, walked well.</p>" in text
    write_wrapped(archive, exports, SLUG, log=lambda m: None, only_if_new=True)      # the same nights: the watcher does not pay again
    assert len(asked) == 1
    write_wrapped(archive, exports, SLUG, log=lambda m: None)                        # asked for by hand: written again
    assert len(asked) == 2
    assert "Six minutes" in write_wrapped(archive, exports, SLUG, use_ai=False, log=lambda m: None)["html"].read_text()   # kept
    assert split_output("no marker here", {"time"}) == ({}, "")
