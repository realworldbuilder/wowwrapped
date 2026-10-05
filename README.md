# WoWwrapped

**Spotify Wrapped for your WoW characters.** Play World of Warcraft normally. WoWwrapped quietly records the night.
When you log out, it updates your character's Wrapped: one page of cards that sums up everything so far, or one
month, one year, or any range of nights. Underneath is a facts page for every night you played.

WoWwrapped is a **memory layer**, not a meter. It never automates anything, never reads protected combat data, and
never needs the network in game. It is not a guide either: it tells you what you did, never what to do.

**Status:** early. Forked from Rambleon, which its author used nightly on the **World of Warcraft: Forever** beta,
on **macOS**. Other WoW flavours and Windows are not supported yet. Free and open, MIT licensed.

## What a Wrapped shows

One card per subject, made from what was recorded:

- time in Azeroth and the longest night; levels gained; quests turned in and the biggest night
- the enemies that fell most often; the zones where the time went; the companions who were there longest
- deaths and where they happened; loot worth keeping; dungeons and their bosses
- your rhythm (the weekday and hour you play most, the latest night out)
- your own `/wrapped note` lines, quoted as written, and your pictures
- a persona (The Wanderer, The Slayer, The Errand Runner, The Good Company, The Daredevil or The Chronicler),
  chosen by fixed rules: the same nights always give the same answer

With [Claude Code](https://claude.com/claude-code) logged in, a writer adds one line per card and a closing
paragraph, using only the facts on the cards. Without it the page is complete from the facts.

## What a night looks like

```
Rambleon Birdsong · September 21, 2026 · 1h 47m in Azeroth

 9:47 PM — Began the adventure
 9:47 PM — Joined forces with Hazardelf (Rogue)
 9:55 PM — Completed "Zenn's Bidding"
10:01 PM — Entered Starbreeze Village (Teldrassil)
10:13 PM — 8/8 Timberling Seed — "Timberling Seeds"
10:14 PM — Note: "alone at the lake slayin timberlings"
10:24 PM — Reached Level 9
11:01 PM — Joined forces with Tiamaat (Druid)

Levels gained: 1 (8 → 9) · Quests completed: 10 · Enemies slain: 63 · Places visited: 9 · People: 2
```

Each night gets a Markdown log and an HTML story page (recap, numbers, quests, timeline, pictures), built by
themselves after you log out. The Wrapped links to the nights it mentions.

## Install (macOS)

You need [Homebrew](https://brew.sh) and WoW installed. Then:

```bash
brew install uv
uv tool install "git+https://github.com/realworldbuilder/wowwrapped@v0.1.0#subdirectory=companion"
wrapped setup
```

`wrapped setup` finds your WoW folder, links the AddOn into it, starts a background watcher that survives reboots,
and opens your (empty) journal. Start WoW, or log out to the character screen and back in so it sees the AddOn.
That is the whole setup. The line above installs release 0.1.0; leave out the `@v…` tag for the newest code on `main`,
and run the same line again (with `--force`) to upgrade, then `wrapped service install` to restart the watcher.

For the written lines on the Wrapped, install [Claude Code](https://claude.com/claude-code) and log in once
(`claude`, then `/login`). Without it you still get every card, every night page, and a prompt file you can paste
into any assistant. `wrapped setup --no-ai` turns the step off.

To remove it: `wrapped uninstall` (your archive stays unless you ask for it to go).

## Playing with it

- `/wrapped` (or `/ww`) opens the panel: time, place, level, quests, places, kills, loot, deaths, people, and the
  recent journey. The first time, it says what WoWwrapped is; after that it stays out of the way.
- `/wrapped note the cave is extremely cursed` — your own words outrank anything the game can tell us. They are
  quoted on the Wrapped and are the best evidence the writer gets.
- `/wrapped mark` — remember this moment and take a picture (there is a keybinding for it under AddOns).
- Level ups and the first step into a new zone are photographed too; `/wrapped shots off` (or the Pictures row on the
  panel) if you would rather not.
- Log out when you are done. That is the save. A few seconds later the night's page and the Wrapped are written on
  your Mac.

On the Mac:

- `wrapped make --open` makes the Wrapped of the character you played last and opens it. `wrapped make <slug>` picks
  a character; `--month 2026-09`, `--year 2026` or `--since 2026-09-21 --until 2026-10-03` give a range its own page;
  `--voice field-journal` has it narrated in another voice; `--no-ai` writes only the facts and the prompt.
- `wrapped nights` lists the nights, `wrapped page tonight` opens a night's story page.
- `wrapped finish tonight` does everything for a night again (or for a night the watcher missed).
- `wrapped share tonight` puts a night's page, its pictures and the character's Wrapped on your GitHub Pages site
  after asking. It needs your own fork of this repository, checked out, with Pages on.
- `wrapped doctor --fix` repairs a broken link or a stopped watcher. `wrapped --help` has the rest.

### Your files and settings

Everything of yours is in one folder: `~/WoWwrapped/` (when you run from a git checkout, the checkout).

| | |
|---|---|
| `archive/` | your history: every session as plain JSON, and the raw files WoW wrote, byte for byte |
| `exports/` | everything made from it (logs, night pages, the Wrapped); can always be rebuilt |
| `wowwrapped.local.toml` | your settings; optional, every key has a default. `wrapped config` shows what is in effect and warns about a key it does not know |
| `prompts/` | your own voices, Wrapped rules and page theme ([docs/extending.md](docs/extending.md)) |

```toml
# ~/WoWwrapped/wowwrapped.local.toml — all optional
[wrapped]
voice = "field-journal"     # the voice the Wrapped is narrated in (`wrapped voices`), or a path to your own .md
model = "sonnet"            # the Claude model

[characters."rambleon-birdsong"]
gender = "male"             # a fact about a character the game did not record

[people."Cassidy"]
note = "my friend from work"   # your own words about a companion; the writer gets them as evidence
```

A voice of your own is a text file: put `saga.md` in `~/WoWwrapped/prompts/voices/` and run `wrapped make --voice saga`.

Want every night and the Wrapped on your site the moment they are written, no questions asked? Put this in `wowwrapped.local.toml`
(it only affects that Mac) and restart the watcher with `wrapped service install`:

```toml
[share]
auto = true
```

Inviting a friend? Send them [docs/invite-prompt.md](docs/invite-prompt.md): a message they can paste into Claude Code
and it installs WoWwrapped for them.

## What it records, and what it never records

Recorded: where you went, quests accepted, completed and abandoned and their objectives, levels, experience, kills
that gave experience (from the chat line), uncommon-or-better loot, deaths, who you grouped with and for how long,
dungeons and the bosses you defeated in them, the inn you made home, achievements, screenshots (yours, and the ones it takes at level ups, marks and new zones), your notes and marks, playtime.

Never: damage numbers or the combat log, chat content, other players beyond your group roster as the game shows it,
anything Blizzard marks protected or secret. Nothing leaves your Mac unless you share or run the AI step. With the
AI step, the only thing sent is the prompt for the Wrapped (the facts on its cards), through your own Claude login.
`wrapped share` is the only command that publishes anything, and it asks first unless you turned on `[share] auto`
yourself.

Your history lives as plain JSON in `~/WoWwrapped/archive/` (or the checkout's `archive/`). Raw files WoW wrote are
kept byte for byte and never edited. Pages are always generated downstream; the record is never touched to make
a better page.

## Why the Mac side exists

WoW only writes AddOn data on logout and reload, and the Forever beta currently does not restore it on the next
launch. So the AddOn treats every login as a fresh session and the Mac watcher snapshots every write. WoW may
forget; WoWwrapped does not.

## Development

```bash
git clone https://github.com/realworldbuilder/wowwrapped && cd wowwrapped
scripts/bootstrap        # uv, the companion env, `wrapped` on PATH (editable)
scripts/test             # luac -p, a simulated session under a WoW API stub, pytest
```

[CONTRIBUTING.md](CONTRIBUTING.md) has the rules in short. [docs/extending.md](docs/extending.md) shows the three
things WoWwrapped is built to have added: a new thing to remember (one entry in the AddOn's `EventTypes.lua` and one in
the companion's `events.py`), a new output (one step in `pipeline.py`), and a new voice, your own Wrapped rules or a
page theme (a file, no code). `docs/` also has the Forever API findings, the data model, a running progress log and the roadmap.

## Roadmap, briefly

Done: the fork from Rambleon, the cuts, the rename and the Wrapped (0.1.0). Next: check the renamed AddOn in game,
check the name against Blizzard's and Spotify's policies, then publish the repository and a real example. After
that, ideas: shareable picture cards, a Wrapped across all your characters, a Wrapped panel in game.
See `docs/roadmap.md`.

That's a wrap.
