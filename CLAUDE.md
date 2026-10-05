# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## WoWwrapped

WoWwrapped is **Spotify Wrapped for your World of Warcraft characters**. You play; it quietly records; it hands you
a Wrapped: one page of cards per character with the hours, the levels, the enemies, the zones, the company you
kept, the deaths, your own notes and your pictures, told in a few lines. Every night also keeps a plain facts page.

Owner: William Hussey. First character: **Rambleon Birdsong**, Night Elf Hunter (male), World of Warcraft: Forever beta.
Goal: something to *offer* other players (free, open), not primarily something to sell.

It grew out of Rambleon 0.4.0 (https://github.com/realworldbuilder/rambleon), a per-night adventure journal.
"Rambleon" in this repo is the character's name, not the product: never rename it. Archives recorded by Rambleon
(`RambleonDB`) still load.

## What WoWwrapped is NOT

- not a DPS meter, not a combat assistant, not a rotation helper
- not a leveling guide or quest helper: no advice, no optimal route, no help in game
- not a ranking against other players: a Wrapped is about one character, for the person who played them
- not a general WoW database
- not automation of any kind (no movement, no ability use, no interaction with other players)

## The one question

Before adding a card or recording an event: **"Would the player smile, wince or nod at this six months later?"**
If not, it does not belong. Memories, not telemetry. The player's own words (`/wrapped note`) always outrank
anything the API can tell us.

## How it works (current, 2026-10-05, release 0.1.0)

```
WoW: Forever → WoWwrapped AddOn (Lua) → SavedVariables (written on logout and /reload)
             → wrapped watch (Mac, launchd service) → archive/ (immutable raw + normalized JSON)
             → nights (one evening) → Markdown log, the character's Wrapped, the night's story page, the index
```

- **The log just runs.** There is no "end" button. Logging out is the save. `/wrapped save` is an optional flush.
- **Pictures**: the AddOn calls `Screenshot()` at level ups, `/wrapped mark` and the first visit to a new zone (UI
  visible, `/wrapped shots on|off`). The `SCREENSHOT` event carries the reason; the companion pairs the file, captions
  it and copies it into `archive/screenshots/`. Archived paths are absolute, so `screenshots.shot_source` also looks
  under where the archive is now.
- **A night**: every session of one evening (5 a.m. cutoff) stitched together in `nights.py`. Reloads and relogs are
  continuity, not breaks (the AddOn resumes a session seen < 10 min ago). Pages still call a night a "chapter".
- **The Wrapped** (`wrapped.py`): `build_wrapped` sums one character's nights (pure: nights in, numbers out);
  `cards` turns the numbers into cards, each with a caption made from the facts alone, and leaves out a card with
  nothing to show; `write_wrapped` writes `exports/html/wrapped-<slug>.html`. A `Span` (`--month`, `--year`,
  `--since/--until`) gives a range its own page, `wrapped-<slug>-<key>.html`; only the whole-story page is linked from
  night pages and the index, kept current by the pipeline, and shared. Zone time is the night's played time shared
  out by the gaps between events (kills are not events). The persona is chosen by fixed rules in `_persona`.
- **Narration is optional.** With the Claude CLI logged in, the writer adds one line per card and a closing
  paragraph: rules in `prompts/wrapped.md`, voice in `prompts/voices/`. Sidecar `exports/wrapped/<slug>[-<key>].json`
  remembers which nights it covers, so the watcher only pays when a night is new. The prompt file is always written
  (`exports/prompts/wrapped-<slug>-prompt.md`); without the CLI the page is complete.
- **Finalization**: the watcher finishes a night the moment the player leaves (WoW quit, or `Logs/Client.log` shows a
  logout after the last save), ten minutes after the last write as fallback, or at once after `/wrapped save`. Then
  the steps of `pipeline.STEPS`, each guarded so one failure never skips the rest: late screenshots → Markdown log →
  Wrapped → story page → index → share (only with `[share] auto`) → macOS notification. A marker in
  `exports/finished/` says a night is done; a watcher that was down finishes what it owes when it starts (nights of
  the last two days), and `wrapped finish [tonight|date]` does the same by hand.
- **Sharing is manual by default**: `wrapped share tonight` copies the night's page, the Wrapped and web-sized
  pictures into `site/example`, commits and pushes after asking. `[share] auto = true` in the gitignored
  `wowwrapped.local.toml` lets the watcher do it. Nothing else publishes.
- **Voices**: `companion/src/wowwrapped/prompts/voices/*.md`. Default `golden`; `field-journal` (dry). `--voice`
  (a name or a path to a .md), `WOWWRAPPED_VOICE`, `[wrapped] voice`, `wrapped voices`.
- **The player's own prompts**: `<home>/prompts/` (`~/WoWwrapped/prompts/`, or the checkout's gitignored `prompts/`):
  `voices/*.md`, `wrapped.md` (replaces the narration rules), `theme.css` (added to every page). Theirs win over
  bundled files of the same name. `prompts.py`.
- **Local settings**: `wowwrapped.local.toml` (gitignored; `~/WoWwrapped/` for a package install). `config.py` reads
  it into a typed `Config`; unknown keys and bad values are warnings, broken TOML is said out loud, `wrapped config`
  prints what is in effect. `[share] auto`, `[wrapped] voice / model`, `[characters."slug"]` (overrides character
  fields, e.g. gender), `[people."Name"] note = "..."` (your own words about a companion, given to the writer).

## Layout

- `addon/WoWwrapped/` — the AddOn. `WoWwrapped_Camelot.toc` (Forever, Interface 16001) + `WoWwrapped.toc` fallback.
  `EventTypes.lua` (every event type: its line in the log, its counter), `Session.lua` (DB, settings, the session,
  recorders, screenshots), `Events.lua` (game event → handler), `Journal.lua`, `UI.lua` (the session panel),
  `Commands.lua` (`ns.COMMANDS`). `Bindings.xml` is loaded by name; never list it in a TOC.
- `addon/tests/` — Lua 5.5 stub + `run.lua`: a scripted session that also emits the parser fixture
  (`companion/tests/fixtures/WoWwrapped_simulated.lua`).
- `companion/` — Python ≥ 3.11, uv, typer. `src/wowwrapped/`: `paths` (find WoW/WTF), `luaparse` (safe SV parser),
  `normalize`, `archive`, `watch` (+ `Finalizer`), `wowstate` (logout detection), `nights`, `export` (Markdown log,
  night numbers, quests), `wrapped` (the Wrapped: numbers, cards, prompt, page), `writer` (voices, the Claude CLI),
  `publish` (a night's story page, the index), `pages` (the HTML shell, top bar, CSS from `assets/*.css`),
  `pipeline` (the after-night steps, the finish marker, what is unfinished), `share` (GitHub Pages), `screenshots`,
  `events` (every event type; twin of `EventTypes.lua`), `model` (schema constants), `prompts`, `config`, `service`
  (launchd), `notify`, `doctor`, `install`, `cli`.
- The companion wheel **bundles the AddOn** via an explicit per-file `force-include` list in `companion/pyproject.toml`.
  Adding a file to `addon/WoWwrapped/` means adding it there too, or `uv tool install` users get a broken AddOn.
  Without a checkout, `install.py` seeds `~/WoWwrapped/addon/WoWwrapped` from the bundled copy.
- `archive/` — **source of truth**, gitignored. Raw snapshots never edited; normalized sessions never shrink.
- `exports/` — regenerable, gitignored: `markdown/`, `prompts/`, `wrapped/` (narration sidecars), `html/`, `finished/`.
- `site/` — GitHub Pages (`.github/workflows/pages.yml`): landing page + `example/`. `site/example` still holds
  Rambleon-era pages until the first `wrapped share`; pushing makes the pages public.
- `docs/` — `extending.md`, `environment.md` (this Mac), `addon-api.md` (Forever facts + the SV bug),
  `data-model.md`, `progress.md` (running log; read "To verify in game" at the top first), `roadmap.md`.

## What we know about the Forever client (verified in game, with the AddOn under its old name)

- Mainline 12.x UI codebase, version 1.60.1, builds 69913 → 70009. `WOW_PROJECT_ID` = 1. Surnames, no realms;
  realm `"Classic Beta PvE"`, WTF folder `70/Rambleon-Birdsong`. **The name API changed with build 70009** (2026-09-24):
  before, `UnitName("player")` → `"Rambleon Birdsong"` and `UnitFullName` → `"Rambleon Birdsong", "ClassicBetaPvE"`;
  now `UnitName` → `"Rambleon"` and `UnitFullName` → `"Rambleon", "Birdsong"`. Both sides derive one `displayName`
  (`ns.ComposeDisplayName` / `normalize.display_name`); characters are matched by GUID, never by name alone.
- `C_UI.Reload()` works from a popup button. `QUEST_TURNED_IN` fires with questID. No event registration failed.
- The SavedVariables bug: files are written but not restored on **cold start**; on this Mac they *were* restored
  across `/reload`. Design assumes nothing: the Mac owns history. One consequence: `ns.IsFirstRun` can be true again
  after a cold start, so the welcome line and popup may repeat.
- `UnitLevel` at logout can be stale; end level is derived from event levels on both sides.
- Kills come from the "X dies, you gain N experience." chat line (no combat log). Loot from the chat loot line
  (uncommon+ only; the link uses the named colour `|cnIQ2:`). `Screenshot()` and file pairing work.
- Unverified in game: the AddOn under its new name (folder, `/wrapped`, `/ww`, keybindings, `WoWwrappedDB`), and from
  Rambleon 0.4.0 `QUEST_REMOVED` → abandoned quests, `HEARTHSTONE_BOUND`, `ENCOUNTER_END` → boss kills,
  `INSTANCE_EXIT` through a loading screen, the welcome popup, the Pictures row. `EQUIP` has never appeared in the
  archive. The list is at the top of `docs/progress.md`.

## Coding rules

**AddOn (Lua 5.1 syntax, retail 12.x-style API):**
- Register events only via `ns.SafeRegister` (pcall). Unknown events throw on this client.
- Everything under `WoWwrappedDB` must be a string, number, boolean or table of those. Route values through
  `ns.Clean` / `ns.CleanString`; never store Secret Values.
- No combat log, no protected APIs, no automation. If Blizzard hides something, accept it.
- Store view state in `ns`/`UI` tables, never as ad-hoc fields on frames.
- Chat stays quiet: one login line. Debug output only behind `/wrapped debug on`.
- Never call `ReloadUI` without the user confirming via the `/wrapped save` popup.
- Lists of client globals (`COMBATLOG_XPGAIN_*`, `LOOT_ITEM_*`) can contain nils: never `ipairs` over them directly.
- A new event type is one entry in `EventTypes.lua`, one `ns.AddEvent` call, one line in `addon/tests/run.lua` and its
  twin in the companion's `events.py`; tests fail if the two sides disagree. A new slash command is one entry in
  `ns.COMMANDS`; a new setting one line in `DEFAULTS` (`Session.lua`), read with `ns.GetSetting`.
- Tests that need more clock time, marks or sessions go after the fixture is written in `run.lua`: the companion's
  tests count on that evening (two sessions, six minutes).

**Companion:**
- Never execute SavedVariables as Lua; use `luaparse.py`. Raw snapshot first, parse second. Atomic writes.
- Merge by session id; never shrink or delete. `wrapped reprocess` rebuilds normalized data from raw after upgrades.
- AI is optional: the Wrapped must always be complete from the facts, and its prompt file always written. The Claude
  CLI runs with `--tools ""`, no session persistence, an empty cwd and a writer's system prompt; never `--bare` (it
  bypasses the keychain login). Code calls it as `writer.run_claude` / `writer.claude_available` (through the
  module), so the tests' patch in `conftest.py` holds and no test reaches the real CLI.
- A new card is a few lines in `wrapped.cards` from a number `build_wrapped` already has (or a new one there); it
  gets a caption from the facts and is skipped when empty. Card styles are `.slide` in `assets/wrapped.css`
  (`.card` belongs to the index).
- Printed WTF paths go through `Paths.redact()`.
- Restart the watcher after changing companion code (`wrapped service install` again); a running process keeps old modules.
- A new output after a night is a `Step` in `pipeline.STEPS`, never another line in `cli.py`. Anything that leaves the
  Mac runs unattended only when `wowwrapped.local.toml` opted in. A new setting is a dataclass field and a rule in
  `config.SECTIONS`. A new page is a body inside `pages.shell`.
- Commands are declared with `@command(app)`: expected failures become one red line and exit 1 (`WOWWRAPPED_DEBUG=1`
  for the traceback). Tests run with their own `WOWWRAPPED_HOME`, in UTC, with no notification and no Claude CLI
  (`tests/conftest.py`); never point a manual test at a home whose config has `auto = true`.

**Narration:** only what the cards say. Names of people, places and enemies exactly as recorded. Feelings only as
reactions to recorded events. Pronouns from the recorded gender, else name/they. Never repeat or correct the
player's notes. Rules in `prompts/wrapped.md`; voice in `prompts/voices/`.

## Dev loop

```
edit addon/WoWwrapped/*.lua or companion/src/wowwrapped/*.py
scripts/test                    # luac -p, simulated session, pytest (same as CI, macos-latest)
scripts/test -k wrapped         # extra args go to pytest (single test: -k name, or tests/test_x.py::test_y)
cd companion && uv run wrapped make latest --no-ai --open     # the Wrapped from this checkout's archive
/reload in WoW                  # AddOn is symlinked; new files need a restart of WoW only when added to the TOC
wrapped service install         # restart the background watcher after companion changes
/wrapped debug                  # paste output + any Lua errors back here
```

`/console scriptErrors 1` shows Lua errors in game. `scripts/bootstrap` sets up uv and `wrapped` from scratch.
Only one recorder at a time: disable the old Rambleon AddOn and stop its watcher (`ramble service uninstall`) before
running this one. CI (`.github/workflows/ci.yml`) runs `scripts/test`, builds the wheel and zips the AddOn (not for
pushes that only touch `site/`); a `v*` tag makes a GitHub release with both. Record user-facing changes in
`CHANGELOG.md`. A release bumps the version in four places that tests keep equal (`companion/pyproject.toml`,
`wowwrapped/__init__.py`, both TOCs), gives the CHANGELOG a `## <version>` heading and updates the pinned
`@v<version>` install lines (README, companion README, `docs/invite-prompt.md`, `site/index.html`); push, wait for
green CI, then tag.

## Command cheat sheet

In game: `/wrapped` (or `/ww`) · `status` · `note <text>` · `mark` · `shots [on|off]` · `save` · `debug [on|off]` · `dump` · `help`.
Keybindings under AddOns: Open Adventure Log, Mark Moment.

Mac: `wrapped setup [--no-ai]` · `doctor [--fix] [--check-ai]` · `config` · `version` · `uninstall` · `install [--copy]`
· `service install|uninstall|status` · `watch [--no-ai] [--no-auto] [--voice] [--model]` · `ingest` · `reprocess`
· `status` · `sessions` · `nights` · `show latest` · `export tonight|YYYY-MM-DD|--all`
· `make [slug|latest] [--month YYYY-MM] [--year YYYY] [--since D] [--until D] [--no-ai] [--voice] [--model] [--open]`
· `finish [tonight|date] [--no-ai] [--voice] [--model] [--share]` · `page tonight`
· `share [tonight|date|--all] [--yes] [--dry-run]` · `voices`.

## Where this is going

See `docs/roadmap.md`. Short version: 0.1.0 is the fork, the cuts and the first Wrapped. Next: verify the renamed
AddOn in game, check the name against Blizzard's and Spotify's policies, publish the repo and a real example; then
make the Wrapped something people pass around (picture cards, more than one character). Free and open; the player's
data never leaves the Mac unless they share a page or run the AI step, and even then only the prompt does.
