# Contributing to WoWwrapped

WoWwrapped is a personal memory layer for World of Warcraft: you play, it records, and it hands you a Wrapped page
per character, with a facts page per night underneath. It is free and open, and small on purpose.

## The one question

Before adding a feature or recording an event: **will this help the player remember their adventure?** If it would
not be interesting to read six months later, it does not belong. WoWwrapped is not a damage meter, a quest helper,
a database or automation of any kind.

## Getting set up (macOS)

```bash
git clone https://github.com/realworldbuilder/wowwrapped && cd wowwrapped
scripts/bootstrap        # uv, the companion environment, `wrapped` on PATH (editable)
scripts/test             # Lua syntax, a scripted evening under a WoW API stub, pytest
```

You do not need World of Warcraft to run the tests. To try the AddOn in game, `wrapped install` links
`addon/WoWwrapped/` into your WoW folder; `/reload` picks up changes.

`scripts/test -k nights` passes extra arguments to pytest. The tests never touch your own archive, settings
or Claude login.

## Where things are

- `addon/WoWwrapped/` is the AddOn (Lua). `EventTypes.lua` lists everything it can remember.
- `companion/src/wowwrapped/` is the Mac side (Python, `wrapped`). `events.py` is the twin of `EventTypes.lua`;
  `pipeline.py` is what happens after a night; `wrapped.py` sums a character's nights into the Wrapped.
- [docs/extending.md](docs/extending.md) shows how to add an event type, an output, or a voice.
- [docs/data-model.md](docs/data-model.md) describes every file WoWwrapped writes.
- [CLAUDE.md](CLAUDE.md) has the rules in full; the short version follows.

## Rules that are not negotiable

**AddOn**
- Passive only: no combat log, no protected APIs, no automation, nothing sent anywhere.
- Game events are registered through `ns.SafeRegister`; client functions are called through `ns.SafeCall`.
- Everything stored goes through `ns.Clean` / `ns.CleanString`: strings, numbers and booleans, never a secret value.
- Chat stays quiet: one line at login. Anything else is behind `/wrapped debug on`.

**Companion**
- SavedVariables are parsed, never executed. The raw file is saved before it is read.
- The archive is the source of truth: sessions are merged by id and never shrink. Everything under `exports/`
  can be rebuilt from it.
- AI is optional. Every command that can use it must do its job without it (the prompt file is always written).
- Nothing leaves the player's Mac unless they ran the command that sends it, or opted in to it in
  `wowwrapped.local.toml`.

**Writing** (prompts): only what was recorded. Names of people and places only from the evidence. Feelings only
as reactions to recorded events. The player's own notes outrank anything the API says.

## Sending a change

- One change per pull request, with a test. A new event type comes with a line in the scripted evening
  (`addon/tests/run.lua`); the tests tell you if the two sides disagree.
- Add a line to `CHANGELOG.md` under "Unreleased" for anything a player would notice.
- If it could only be checked in game, say so in the pull request and in `docs/progress.md` under
  "To verify in game".
