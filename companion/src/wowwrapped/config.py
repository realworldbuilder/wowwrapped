"""Optional local settings: <home>/wowwrapped.local.toml (gitignored; ~/WoWwrapped/ for a package install).

One loader, `load_config`, reads the file into a typed `Config`. It never raises: a key it does not know or a
value of the wrong kind becomes a warning and the default applies; a file that is not valid TOML sets `error`,
and everything falls back to the defaults (so auto-share is off until it is fixed).
`wrapped config` prints what is in effect; `wrapped doctor` reports warnings."""
from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from .paths import find_repo_root

FILENAME = "wowwrapped.local.toml"


@dataclass(frozen=True)
class ShareConfig:
    auto: bool = False          # push every finished chapter to GitHub Pages without asking


@dataclass(frozen=True)
class WrappedConfig:
    voice: str | None = None    # a voice profile (see `wrapped voices`) or a path to your own .md
    model: str | None = None    # the Claude model the Wrapped is narrated with


@dataclass(frozen=True)
class Config:
    path: Path
    exists: bool = False
    share: ShareConfig = field(default_factory=ShareConfig)
    wrapped: WrappedConfig = field(default_factory=WrappedConfig)
    characters: dict[str, dict[str, Any]] = field(default_factory=dict)   # slug -> character fields to override
    people: dict[str, str] = field(default_factory=dict)                  # roster name -> the player's note
    warnings: tuple[str, ...] = ()
    error: str | None = None


def _is_bool(v: Any) -> bool:
    return isinstance(v, bool)


def _is_text(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


# section -> key -> (accepts, what it should be). The dataclass above holds the default.
Rule = tuple[Callable[[Any], bool], str]
SECTIONS: dict[str, tuple[type, dict[str, Rule]]] = {
    "share": (ShareConfig, {"auto": (_is_bool, "true or false")}),
    "wrapped": (WrappedConfig, {"voice": (_is_text, "a voice name or a path to a .md file"),
                                "model": (_is_text, "a Claude model name")}),
}
FREE_SECTIONS = ("characters", "people")


def _section(name: str, raw: Any, warnings: list[str]) -> Any:
    cls, rules = SECTIONS[name]
    if raw is None:
        return cls()
    if not isinstance(raw, dict):
        warnings.append(f"[{name}] should be a table; ignored")
        return cls()
    values: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in rules:
            warnings.append(f"[{name}] {key}: not a setting WoWwrapped knows (known: {', '.join(rules)})")
            continue
        accepts, expected = rules[key]
        if not accepts(value):
            warnings.append(f"[{name}] {key} = {value!r}: should be {expected}; using the default")
            continue
        values[key] = tuple(value) if isinstance(value, list) else (value.strip() if isinstance(value, str) else value)
    return cls(**values)


def load_config(home: Path | None = None) -> Config:
    path = (home or find_repo_root()) / FILENAME
    if not path.exists():
        return Config(path=path)
    try:
        with open(path, "rb") as fh:
            raw = tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        return Config(path=path, exists=True, error=f"{path.name} is not valid TOML: {e}")
    except OSError as e:
        return Config(path=path, exists=True, error=f"{path.name} cannot be read: {e}")
    warnings: list[str] = []
    for name in raw:
        if name not in SECTIONS and name not in FREE_SECTIONS:
            warnings.append(f"[{name}]: not a section WoWwrapped knows (known: {', '.join([*SECTIONS, *FREE_SECTIONS])})")
    characters: dict[str, dict[str, Any]] = {}
    if isinstance(raw.get("characters"), dict):
        for slug, fields in raw["characters"].items():
            if isinstance(fields, dict):
                characters[str(slug)] = dict(fields)
            else:
                warnings.append(f'[characters."{slug}"] should be a table of character fields; ignored')
    elif "characters" in raw:
        warnings.append("[characters] should hold one table per character slug; ignored")
    people: dict[str, str] = {}
    if isinstance(raw.get("people"), dict):
        for name, entry in raw["people"].items():
            note = entry.get("note") if isinstance(entry, dict) else None
            if isinstance(note, str) and note.strip():
                people[str(name)] = note.strip()
            else:
                warnings.append(f'[people."{name}"] needs note = "your words about them"; ignored')
    elif "people" in raw:
        warnings.append("[people] should hold one table per name; ignored")
    return Config(path=path, exists=True,
                  share=_section("share", raw.get("share"), warnings), wrapped=_section("wrapped", raw.get("wrapped"), warnings),
                  characters=characters, people=people, warnings=tuple(warnings))


def effective(cfg: Config) -> dict[str, dict[str, Any]]:
    """The settings in effect, section by section, for `wrapped config`."""
    return {name: asdict(getattr(cfg, name)) for name in SECTIONS}


# -- what the rest of the companion asks ---------------------------------------

def character_overrides(slug: str, repo_root: Path | None = None) -> dict[str, Any]:
    return load_config(repo_root).characters.get(slug, {})


def share_auto(repo_root: Path | None = None) -> bool:
    """`[share] auto = true`: push every finished chapter to GitHub Pages without asking. Off unless this
    machine's wowwrapped.local.toml says so; the file is gitignored, so it never travels with the repo."""
    return load_config(repo_root).share.auto


def people_notes(repo_root: Path | None = None) -> dict[str, str]:
    """`[people."Cassidy"] note = "my friend from work"`: the player's own words about a companion, handed to
    the writer as evidence. Names match the roster name the game shows."""
    return dict(load_config(repo_root).people)


def writer_voice(asked: str | None = None, repo_root: Path | None = None) -> str | None:
    """The voice to write in: the one asked for, else WOWWRAPPED_VOICE, else `[wrapped] voice`. None means the default."""
    return asked or os.environ.get("WOWWRAPPED_VOICE") or load_config(repo_root).wrapped.voice


def writer_model(asked: str | None = None, repo_root: Path | None = None) -> str | None:
    """The model to write with: the one asked for, else WOWWRAPPED_MODEL, else `[wrapped] model`. None means the default."""
    return asked or os.environ.get("WOWWRAPPED_MODEL") or load_config(repo_root).wrapped.model
