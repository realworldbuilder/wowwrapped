"""The Wrapped: everything one character did, summed across nights, as a page of cards.

`build_wrapped` is pure: nights in, numbers out. `cards` turns the numbers into what the page shows, each card
with a caption made from the facts alone. The writer (optional) adds one line per card and a closing paragraph;
without it the page is complete. `write_wrapped` does all of it and writes exports/html/wrapped-<slug>.html."""
from __future__ import annotations

import html
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import prompts, writer
from .archive import Archive, atomic_write_bytes, atomic_write_json, load_json
from .config import character_overrides, people_notes, writer_model, writer_voice
from .events import place
from .export import clock, duration
from .nights import nights as list_nights
from .pages import page_name, shell, top_nav, wrapped_page_name
from .publish import _web_copy, character_line
from .screenshots import shot_source
from .writer import DEFAULT_MODEL, DEFAULT_VOICE, load_voice

Log = Callable[[str], None]
MAX_GAP = 30 * 60        # a longer silence between two events is a break, not time spent in the zone
TOP = 5
MAX_PICTURES = 6
MAX_NOTES = 5
CLOSING_MARKER = "---CLOSING---"
WEEKDAYS = ("Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays")


# ---------------------------------------------------------------------------------------------------
# Which nights

@dataclass(frozen=True)
class Span:
    since: str | None = None     # night dates, YYYY-MM-DD, both inclusive
    until: str | None = None
    key: str | None = None       # in the page's file name; None is the whole story so far
    label: str = "So far"


def span(month: str | None = None, year: str | None = None, since: str | None = None, until: str | None = None) -> Span:
    """One of: a month (YYYY-MM), a year (YYYY), a range of night dates, or nothing for everything so far."""
    if sum(bool(x) for x in (month, year, since or until)) > 1:
        raise ValueError("choose one of --month, --year, or --since/--until")
    try:
        if month:
            first = datetime.strptime(month, "%Y-%m")
            return Span(f"{month}-01", f"{month}-31", month, first.strftime("%B %Y"))
        if year:
            datetime.strptime(year, "%Y")
            return Span(f"{year}-01-01", f"{year}-12-31", year, year)
        for d in (since, until):
            if d:
                datetime.strptime(d, "%Y-%m-%d")
    except ValueError:
        raise ValueError("dates look like 2026-09-21, months like 2026-09, years like 2026") from None
    if since or until:
        label = " to ".join(_day(d) if d else "…" for d in (since, until))
        return Span(since, until, f"{since or 'start'}_{until or 'now'}", label)
    return Span()


def _day(night_date: str, year: bool = False) -> str:
    return datetime.strptime(night_date, "%Y-%m-%d").strftime("%B %-d, %Y" if year else "%B %-d")


# ---------------------------------------------------------------------------------------------------
# The numbers

def zone_seconds(night: dict[str, Any]) -> dict[str, float]:
    """The night's play time, shared out over its zones by the time between events there. Kills are not
    events, so the gaps undercount; scaling to the played time keeps the zones adding up to the night."""
    raw: Counter[str] = Counter()
    zone, prev = None, None
    for ev in night.get("events", []):
        t = ev.get("t") or 0
        if prev is not None and zone:
            raw[zone] += min(max(t - prev, 0), MAX_GAP)
        zone = ev.get("zone") or zone
        prev = t
    total = sum(raw.values())
    if not total:
        return {}
    played = night.get("playedSeconds") or 0
    return {z: played * s / total for z, s in raw.items()}


def _persona(t: dict[str, Any], together: float, own_words: int) -> dict[str, str]:
    """One of six, by which habit stands out most against a plain yardstick. Rules, not a model: the same
    nights always give the same answer."""
    hours = max((t["playedSeconds"] or 0) / 3600, 0.01)
    scores = [
        (t["places"] / hours / 6, "The Wanderer", f"{t['places']} places in {duration(t['playedSeconds'])}: rarely in one spot for long."),
        (t["kills"] / hours / 40, "The Slayer", f"{t['kills']:,} enemies slain, about {t['kills'] / hours:.0f} an hour."),
        (t["quests"] / hours / 4, "The Errand Runner", f"{t['quests']} quests turned in, about {t['quests'] / hours:.1f} an hour."),
        (together / max(t["playedSeconds"], 1) / 0.5, "The Good Company", f"{together / max(t['playedSeconds'], 1):.0%} of the time with someone at your side."),
        (t["deaths"] / hours / 1.0, "The Daredevil", f"{t['deaths']} deaths, and back up every time."),
        (own_words / hours / 1.5, "The Chronicler", f"{own_words} moments marked or written down in your own words."),
    ]
    _, title, why = max(scores, key=lambda s: s[0])
    return {"title": title, "why": why}


def build_wrapped(nights_: list[dict[str, Any]], since: str | None = None, until: str | None = None) -> dict[str, Any]:
    """The nights of one character, oldest first, summed. Pure."""
    chosen = [n for n in nights_ if (not since or n["nightDate"] >= since) and (not until or n["nightDate"] <= until)]
    if not chosen:
        raise ValueError("no nights in that range (try `wrapped nights`)")
    c = dict(chosen[-1].get("character", {}))
    cnt = lambda key: sum((n.get("counters", {}).get(key) or 0) for n in chosen)   # noqa: E731
    zones: Counter[str] = Counter()
    places: set[str] = set()
    kills: dict[str, dict[str, int]] = {}
    people: dict[str, dict[str, Any]] = {}
    death_zones: Counter[str] = Counter()
    loot: dict[Any, dict[str, Any]] = {}
    bosses: Counter[str] = Counter()
    instances: list[str] = []
    levels, notes, pictures = [], [], []
    weekdays: Counter[int] = Counter()
    hours: Counter[int] = Counter()
    rows = []
    for n in chosen:
        date = n["nightDate"]
        for z, s in zone_seconds(n).items():
            zones[z] += s
        places |= {f"{z.get('zone')}|{z.get('subzone') or ''}" for z in n.get("zones", [])}
        for name, info in (n.get("kills") or {}).items():
            k = kills.setdefault(name, {"count": 0, "xp": 0})
            k["count"] += info.get("count") or 0
            k["xp"] += info.get("xp") or 0
        for p in n.get("people", []):
            who = people.setdefault(p.get("name") or "?", {"name": p.get("name") or "?", "class": p.get("class"), "seconds": 0, "nights": 0})
            who["seconds"] += p.get("seconds") or 0
            who["nights"] += 1
            who["class"] = who["class"] or p.get("class")
        weekdays[datetime.strptime(date, "%Y-%m-%d").weekday()] += n.get("playedSeconds") or 0
        for ev in n.get("events", []):
            t, kind = ev.get("t") or 0, ev.get("type")
            hours[datetime.fromtimestamp(t).hour] += 1
            if kind == "DEATH":
                death_zones[ev.get("zone") or "the wilds"] += 1
            elif kind in ("LOOT", "EQUIP") and ev.get("name"):
                loot[ev.get("itemID") if ev.get("itemID") is not None else ev["name"]] = {
                    "name": ev["name"], "quality": ev.get("quality") or 0, "qualityName": ev.get("qualityName"), "t": t}
            elif kind == "BOSS_KILL" and ev.get("name"):
                bosses[ev["name"]] += 1
            elif kind == "INSTANCE_ENTER" and ev.get("name") and ev["name"] not in instances:
                instances.append(ev["name"])
            elif kind == "LEVEL_UP" and ev.get("level"):
                levels.append({"level": int(ev["level"]), "t": t, "place": place(ev), "nightDate": date})
            elif kind == "NOTE" and ev.get("text"):
                notes.append({"text": str(ev["text"]), "t": t, "place": place(ev), "nightDate": date})
        for shot in n.get("screenshots", []):
            pictures.append(dict(shot, nightDate=date))
        st = n.get("counters", {})
        rows.append({"id": n["id"], "nightDate": date, "page": page_name(n), "playedSeconds": n.get("playedSeconds") or 0,
                     "endedAt": n.get("endedAt") or 0, "quests": st.get("questsCompleted") or 0, "kills": st.get("kills") or 0,
                     "deaths": st.get("deaths") or 0})
    start = chosen[0].get("character", {}).get("startLevel")
    end = max((n.get("character", {}).get("endLevel") or 0) for n in chosen) or None
    totals = {
        "nights": len(chosen), "playedSeconds": sum(r["playedSeconds"] for r in rows), "startLevel": start, "endLevel": end,
        "levels": end - start if start and end else cnt("levelsGained"), "quests": cnt("questsCompleted"), "kills": cnt("kills"), "deaths": cnt("deaths"),
        "xp": cnt("xpGained"), "loot": len(loot), "zones": len(zones) or len({p.split("|")[0] for p in places}),
        "places": len(places), "people": len(people), "enemyKinds": len(kills), "pictures": len(pictures), "notes": len(notes),
    }
    midnight = lambda r: datetime.strptime(r["nightDate"], "%Y-%m-%d").timestamp()   # noqa: E731
    by_time = sorted(people.values(), key=lambda p: -p["seconds"])
    together = min(sum(p["seconds"] for p in by_time), totals["playedSeconds"])
    return {
        "slug": c.get("slug") or "unknown", "displayName": c.get("displayName") or c.get("slug") or "Unknown", "character": c,
        "nightIds": [n["id"] for n in chosen], "firstDate": chosen[0]["nightDate"], "lastDate": chosen[-1]["nightDate"],
        "open": any(n.get("state") != "ended" for n in chosen),
        "totals": totals, "nights": rows,
        "topEnemies": [dict(v, name=k) for k, v in sorted(kills.items(), key=lambda kv: -kv[1]["count"])[:TOP]],
        "topZones": [{"zone": z, "seconds": int(s)} for z, s in zones.most_common(TOP)],
        "topPeople": by_time[:TOP],
        "deathZones": [{"zone": z, "deaths": k} for z, k in death_zones.most_common(TOP)],
        "loot": sorted(loot.values(), key=lambda item: (-item["quality"], -item["t"]))[:TOP],
        "bosses": [{"name": b, "count": k} for b, k in bosses.most_common(TOP)], "instances": instances,
        "levels": levels, "notes": notes, "pictures": sorted(pictures, key=lambda s: s.get("takenAt") or 0),
        "longestNight": max(rows, key=lambda r: r["playedSeconds"]),
        "biggestNight": max(rows, key=lambda r: r["quests"]),
        "latestNight": max(rows, key=lambda r: r["endedAt"] - midnight(r)),
        "weekday": WEEKDAYS[weekdays.most_common(1)[0][0]],
        "hour": datetime(2000, 1, 1, hours.most_common(1)[0][0]).strftime("%-I %p") if hours else None,
        "persona": _persona(totals, together, cnt("notes") + cnt("marks")),
    }


# ---------------------------------------------------------------------------------------------------
# The cards: what the page shows, from the numbers alone

def _n(count: int, noun: str) -> str:
    return f"{count:,} {noun}{'' if count == 1 else 's'}"


def pick_pictures(pictures: list[dict[str, Any]], keep: int = MAX_PICTURES) -> list[dict[str, Any]]:
    """A few pictures spread over the whole stretch: level ups and marked moments before arrivals."""
    chosen = [s for s in pictures if s.get("reason") in ("LEVEL_UP", "MARK")] or pictures
    if len(chosen) <= keep:
        return chosen
    step = (len(chosen) - 1) / (keep - 1)
    return [chosen[round(i * step)] for i in range(keep)]


def cards(w: dict[str, Any], label: str = "So far", linked: set[str] | None = None) -> list[dict[str, Any]]:
    """`linked`: the night pages that will sit beside this one (None: all of them); only those are linked."""
    t = w["totals"]
    link = lambda r, text: (text, r["page"]) if linked is None or r["page"] in linked else None   # noqa: E731
    out: list[dict[str, Any]] = []

    def card(key: str, kicker: str, big: str, caption: str = "", **more: Any) -> None:
        out.append({"key": key, "kicker": kicker, "big": big, "caption": caption, **more})

    dates = _day(w["firstDate"]) if w["firstDate"] == w["lastDate"] else f"{_day(w['firstDate'])} to {_day(w['lastDate'], year=True)}"
    card("intro", f"WoWwrapped · {label}", w["displayName"], f"{character_line(w['character'])}. {_n(t['nights'], 'night')}, {dates}.")
    longest = w["longestNight"]
    card("time", "Time in Azeroth", duration(t["playedSeconds"]),
         f"Across {_n(t['nights'], 'night')}." + (f" The longest was {_day(longest['nightDate'])}: {duration(longest['playedSeconds'])}." if t["nights"] > 1 else ""),
         link=link(longest, "That night") if t["nights"] > 1 else None)
    if t["startLevel"] and t["endLevel"]:
        last = w["levels"][-1] if w["levels"] else None
        card("levels", "Levels", f"{t['startLevel']} → {t['endLevel']}" if t["startLevel"] != t["endLevel"] else f"Level {t['endLevel']}",
             f"{_n(t['levels'], 'level')} gained." + (f" Level {last['level']} came in {last['place']}." if last and last.get("place") else ""),
             spark=[lv["level"] for lv in w["levels"]])
    biggest = w["biggestNight"]
    if t["quests"]:
        card("quests", "Quests turned in", f"{t['quests']:,}",
             f"The biggest night was {_day(biggest['nightDate'])}: {_n(biggest['quests'], 'quest')}." if t["nights"] > 1 else "",
             link=link(biggest, "That night") if t["nights"] > 1 else None)
    if w["topEnemies"]:
        top = w["topEnemies"][0]
        card("enemies", "Enemies slain", f"{t['kills']:,}",
             f"{_n(t['enemyKinds'], 'kind')} of enemy. {top['name']} fell most often.",
             rows=[(e["name"], f"×{e['count']:,}", e["count"] / top["count"]) for e in w["topEnemies"]])
    if w["topZones"]:
        top = w["topZones"][0]
        card("zones", "Where you were", top["zone"], f"{_n(t['zones'], 'zone')}, {_n(t['places'], 'place')}.",
             rows=[(z["zone"], duration(z["seconds"]), z["seconds"] / max(top["seconds"], 1)) for z in w["topZones"]])
    if w["topPeople"]:
        top = w["topPeople"][0]
        card("people", "Good company", top["name"],
             f"{_n(t['people'], 'companion')} along the way. {top['name']} was there on {_n(top['nights'], 'night')}.",
             rows=[(p["name"] + (f" · {p['class']}" if p.get("class") else ""), duration(p["seconds"]), p["seconds"] / max(top["seconds"], 1))
                   for p in w["topPeople"]])
    if w["deathZones"]:
        worst = w["deathZones"][0]
        card("deaths", "Deaths", f"{t['deaths']:,}", f"{worst['zone']} claimed {worst['deaths']} of them.",
             rows=[(z["zone"], f"×{z['deaths']}", z["deaths"] / worst["deaths"]) for z in w["deathZones"]])
    else:
        card("deaths", "Deaths", "0", "Not one.")
    if w["loot"]:
        card("loot", "Loot worth keeping", f"{t['loot']:,}", "",
             rows=[(item["name"], item.get("qualityName") or "", 0) for item in w["loot"]])
    if w["bosses"] or w["instances"]:
        card("dungeons", "Into the dungeons", f"{len(w['instances']) or len(w['bosses'])}",
             ", ".join(w["instances"]) + ("." if w["instances"] else ""),
             rows=[(b["name"], f"×{b['count']}", 0) for b in w["bosses"]])
    late = w["latestNight"]
    card("rhythm", "Your rhythm", w["weekday"],
         "Most of your hours fell on " + w["weekday"] + (f"; the busiest hour was {w['hour']}" if w["hour"] else "")
         + f". The latest night out ended at {clock(late['endedAt'])}, {_day(late['nightDate'])}.",
         bars=[{"height": r["playedSeconds"], "title": f"{_day(r['nightDate'])}: {duration(r['playedSeconds'])}",
                "href": (link(r, "") or (None, None))[1]} for r in w["nights"]] if t["nights"] > 1 else None)
    if w["notes"]:
        card("notes", "In your own words", "", "", quotes=[(n["text"], " · ".join(x for x in (n.get("place"), _day(n["nightDate"])) if x))
                                                           for n in w["notes"][-MAX_NOTES:]])
    if w["pictures"]:
        card("pictures", "The pictures", f"{t['pictures']:,}", "", pictures=pick_pictures(w["pictures"]))
    card("persona", "Your Wrapped persona", w["persona"]["title"], w["persona"]["why"])
    return out


def facts(c: dict[str, Any]) -> str:
    """A card as one line of evidence for the writer."""
    parts = [f"{c['kicker']}: {c['big']}".rstrip(": "), c["caption"]]
    parts += [f"{name} ({value})" if value else name for name, value, _ in c.get("rows") or []]
    parts += [f"\"{text}\" ({where})" for text, where in c.get("quotes") or []]
    parts += [str(p.get("caption")) for p in c.get("pictures") or [] if p.get("caption")]
    return " · ".join(p for p in parts if p)


# ---------------------------------------------------------------------------------------------------
# The writer's part

def _pronouns(gender: str | None) -> str:
    return {"male": "he/him", "female": "she/her"}.get((gender or "").lower(), "they/them (gender not recorded: never guess)")


def build_prompt(w: dict[str, Any], deck: list[dict[str, Any]], voice: str | None = None) -> str:
    c = w["character"]
    rules = (prompts.wrapped_rules()[0].replace("{voice}", load_voice(voice)).replace("{name}", w["displayName"])
             .replace("{pronouns}", _pronouns(c.get("gender"))))
    lines = [rules, "", "=" * 72, "", "## Character", "", f"- {w['displayName']}: {character_line(c)}",
             "- Game: World of Warcraft: Forever", "", "## The cards (key: the only facts you may use)", ""]
    lines += [f"- {card['key']}: {facts(card)}" for card in deck]
    notes_about = people_notes()
    known = [f"- {p['name']}: {notes_about[p['name']]}" for p in w["topPeople"] if notes_about.get(p["name"])]
    if known:
        lines += ["", "## The player's own words about their companions", ""] + known
    return "\n".join(lines) + "\n"


def split_output(text: str, keys: set[str]) -> tuple[dict[str, str], str]:
    """(one line per card key, the closing paragraph). Lines for cards that do not exist are dropped."""
    body, _, closing = text.partition(CLOSING_MARKER)
    lines = {}
    for m in re.finditer(r"^\W*([a-z]+)\W*:\s*(.+)$", body, re.M):
        if m.group(1) in keys:
            lines[m.group(1)] = m.group(2).strip()
    return lines, " ".join(closing.split())


def sidecar_path(exports_dir: Path, slug: str, key: str | None = None) -> Path:
    return exports_dir / "wrapped" / f"{slug}{'-' + key if key else ''}.json"


def load_narration(exports_dir: Path, slug: str, key: str | None = None) -> dict[str, Any] | None:
    try:
        return load_json(sidecar_path(exports_dir, slug, key))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------------------------------
# The page

def _spark(values: list[int]) -> str:
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    pts = " ".join(f"{i * 100 / (len(values) - 1):.1f},{38 - (v - lo) * 36 / max(hi - lo, 1):.1f}" for i, v in enumerate(values))
    return f"<svg class='spark' viewBox='0 0 100 40' preserveAspectRatio='none' aria-hidden='true'><polyline points='{pts}'/></svg>"


def _card_html(i: int, c: dict[str, Any], line: str | None, images: dict[str, str]) -> str:
    e = html.escape
    parts = [f"<section class='slide t{i % 5 + 1}' id='{e(c['key'])}'><div class='in'><div class='kicker'>{e(c['kicker'])}</div>"]
    if c["big"]:
        parts.append(f"<div class='big{' long' if len(c['big']) > 12 else ' mid' if len(c['big']) > 7 else ''}'>{e(c['big'])}</div>")
    parts.append(_spark(c.get("spark") or []))
    if c["caption"]:
        parts.append(f"<p class='caption'>{e(c['caption'])}</p>")
    if c.get("rows"):
        parts.append("<ol class='rows'>" + "".join(
            f"<li style='--share:{share:.2f}'><span>{e(name)}</span><b>{e(value)}</b></li>" for name, value, share in c["rows"]) + "</ol>")
    if c.get("bars"):
        tallest = max(b["height"] for b in c["bars"]) or 1
        parts.append("<div class='bars'>" + "".join(
            (f"<a href='{e(b['href'])}'" if b.get("href") else "<span") + f" title='{e(b['title'])}' style='--h:{b['height'] / tallest:.2f}'>"
            + ("</a>" if b.get("href") else "</span>") for b in c["bars"]) + "</div>")
    for text, where in c.get("quotes") or []:
        parts.append(f"<blockquote>{e(text)}<cite>{e(where)}</cite></blockquote>")
    shown = [(images[p["file"]], p) for p in c.get("pictures") or [] if p.get("file") in images]
    if shown:
        parts.append("<div class='gallery'>" + "".join(
            f"<figure><img src='{e(src)}' alt='{e(p.get('caption') or '')}' loading='lazy'><figcaption>{e(p.get('caption') or '')}</figcaption></figure>"
            for src, p in shown) + "</div>")
    if line:
        parts.append(f"<p class='line'>{e(line)}</p>")
    if c.get("link"):
        parts.append(f"<a class='more' href='{e(c['link'][1])}'>{e(c['link'][0])} →</a>")
    parts.append("</div></section>")
    return "".join(p for p in parts if p)


def render_html(w: dict[str, Any], deck: list[dict[str, Any]], narration: dict[str, Any] | None, images: dict[str, str],
                label: str = "So far") -> str:
    lines = (narration or {}).get("lines") or {}
    body = [_card_html(i, c, lines.get(c["key"]), images) for i, c in enumerate(deck)]
    closing = (narration or {}).get("closing")
    body.append(f"<section class='slide t{len(deck) % 5 + 1}' id='closing'><div class='in'><div class='kicker'>{html.escape(label)}</div>"
                + (f"<p class='closing'>{html.escape(closing)}</p>" if closing else "")
                + "<div class='big'>That's a wrap.</div>"
                + ("<p class='caption'>The latest night is still open; this page grows when it ends.</p>" if w["open"] else "")
                + "</div></section>")
    title = f"{html.escape(w['displayName'])} — Wrapped" + (f" · {html.escape(label)}" if label != "So far" else "")
    nav = top_nav(("All nights", "index.html" + (f"#{w['slug']}" if w["slug"] else "")), ("About WoWwrapped", "../"))
    return shell(title, nav, "\n".join(body), f"Recorded by WoWwrapped · {len(w['nightIds'])} nights", body_attrs=" class='wrapped'",
                 wrapped=True)


def _images(w: dict[str, Any], deck: list[dict[str, Any]], image_dir: Path) -> dict[str, str]:
    """Web copies of the pictures the page shows, beside it: screenshot file name -> src."""
    out = {}
    for c in deck:
        for n, shot in enumerate(c.get("pictures") or [], 1):
            src = shot_source(shot)
            copy = _web_copy(src, image_dir, f"{image_dir.name}-{n:02d}") if src else None
            if copy is not None:
                out[shot["file"]] = f"{image_dir.name}/{copy.name}"
    return out


def write_wrapped(archive: Archive, exports_dir: Path, slug: str, span_: Span | None = None, use_ai: bool = True,
                  model: str | None = None, voice: str | None = None, log: Log = print, only_if_new: bool = False,
                  siblings: set[str] | None = None) -> dict[str, Any]:
    """Build the Wrapped of one character and write its page. The prompt is always written; the writer is asked
    when `use_ai` and the Claude CLI is there (`only_if_new`: not when the narration already covers these
    nights). `siblings`: the pages that will sit beside it, for links."""
    span_ = span_ or Span()
    nights_ = list_nights(archive, slug)
    if not nights_:
        raise ValueError(f"no nights archived for {slug!r} (try `wrapped nights`)")
    w = build_wrapped(nights_, span_.since, span_.until)
    for k, v in character_overrides(slug).items():        # wowwrapped.local.toml wins over old sessions
        if isinstance(v, (str, int, float, bool)) and k not in ("name", "slug"):
            w["character"][k] = v
    deck = cards(w, span_.label, linked=siblings)
    voice = writer_voice(voice)
    model = writer_model(model) or DEFAULT_MODEL
    prompt = build_prompt(w, deck, voice)
    rules_text, rules_path = prompts.wrapped_rules()
    if prompts.is_yours(rules_path):
        for name in prompts.stray_placeholders(rules_text, "wrapped"):
            log(f"{rules_path.name}: {{{name}}} is not something WoWwrapped fills in; it goes to the writer as written")
    stem = wrapped_page_name(slug, span_.key).removesuffix(".html")
    prompt_path = exports_dir / "prompts" / f"{stem}-prompt.md"
    atomic_write_bytes(prompt_path, prompt.encode("utf-8"))
    narration = load_narration(exports_dir, slug, span_.key)
    current = bool(narration) and narration.get("nightIds") == w["nightIds"]
    if use_ai and not (only_if_new and current):
        if not writer.claude_available():
            log(f"no `claude` CLI found; the Wrapped is built from the facts (the prompt is at {prompt_path})")
        else:
            log(f"asking claude ({model}) to narrate {w['displayName']}'s Wrapped…")
            text, diag = writer.run_claude(prompt, model=model)
            if text is None:
                log(f"narration skipped: {diag}. The prompt is at {prompt_path}.")
            else:
                lines, closing = split_output(text, {c["key"] for c in deck})
                narration = {"formatVersion": 1, "slug": slug, "key": span_.key, "nightIds": w["nightIds"], "lines": lines,
                             "closing": closing, "model": model, "voice": voice or DEFAULT_VOICE, "createdAt": int(time.time())}
                atomic_write_json(sidecar_path(exports_dir, slug, span_.key), narration)
    out = exports_dir / "html" / f"{stem}.html"
    page = render_html(w, deck, narration, _images(w, deck, out.with_suffix("")), span_.label)
    atomic_write_bytes(out, page.encode("utf-8"))
    return {"html": out, "prompt": prompt_path, "narrated": bool(narration), "nights": len(w["nightIds"])}
