# WoWwrapped roadmap

Updated 2026-10-05 (0.1.0). WoWwrapped is Spotify Wrapped for your WoW characters: you play, it quietly records, and
it hands you a Wrapped page per character, with a facts page per night underneath. Free and open. Mac only and
WoW: Forever only for now, said plainly.

## Done (0.1.0)

- [x] **Fork** from Rambleon 0.4.0: the AddOn, the watcher, the archive, nights, the pipeline, story pages, sharing.
- [x] **Cuts**: posting to X, the route guide, the AI-written chapter per night (and the memory between chapters),
      the in-game chapter reader, `catchup`. A night keeps a facts-only page.
- [x] **Rename**: AddOn `WoWwrapped` (`/wrapped`, `/ww`, `WoWwrappedDB`), package `wowwrapped`, command `wrapped`,
      `wowwrapped.local.toml`, `WOWWRAPPED_*`, `~/WoWwrapped`. Raw snapshots recorded by Rambleon still reprocess.
- [x] **The Wrapped**: `wrapped make`, one page of cards per character (so far, a month, a year or a range), kept
      current by a pipeline step, narrated by the Claude CLI when it is there and complete without it.

## Next (in order)

1. **Verify the renamed AddOn in game.** Nothing under the new name has run in the real client yet. The list is at
   the top of `docs/progress.md`.
2. **Check the name before it goes public.** Blizzard's fan-content naming policy ("WoW" in a project name), and
   Spotify's stance on "Wrapped" used by others. Rename again if either says no.
3. **Create the GitHub repository** (`realworldbuilder/wowwrapped`, with Pages) and tag `v0.1.0`. Until then the
   install lines in the READMEs point at a repository that does not exist.
4. **Refresh `site/example`** with a real Wrapped (`wrapped share --all`). What is there now are Rambleon's pages.

## Ideas, after that

Each is a new output: a step in `pipeline.py` or a card in `wrapped.py` (`docs/extending.md`).

- Shareable PNG cards: each card of the Wrapped as a picture to post.
- An account-wide Wrapped: one page across all of a player's characters.
- A Wrapped panel in game.

## Non-negotiables

- Passive. Never automates, never touches protected or secret values, never needs the network in game.
- Not a DPS meter, not a guide. It says what you did, never what to do.
- The player's own notes outrank anything the API says.
- Plain files on the player's disk. Nothing leaves the Mac unless the player shares or runs the AI step, and then
  only the prompt does.
- Other players appear only as the game shows them in your group. No chat content is stored.
- Raw history is never edited to make a page better. AI is downstream, always.
