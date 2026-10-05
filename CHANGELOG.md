# Changelog

## 0.1.0

WoWwrapped starts here, grown out of Rambleon 0.4.0 (https://github.com/realworldbuilder/rambleon).

- New: the Wrapped. `wrapped make` (and the watcher, after every night) writes one page of cards per character:
  time, levels, quests, enemies, zones, companions, deaths, loot, dungeons, your rhythm, your own notes, pictures
  and a persona. `--month`, `--year` or `--since/--until` make one for a range. With the Claude CLI logged in, each
  card gets a line and the page a closing paragraph; without it the page is complete from the facts.
- Fixed: pictures of an archive that was moved are found again.
- Renamed: the AddOn is `WoWwrapped` (`/wrapped`, `/ww`), the companion is `wrapped`, settings live in
  `wowwrapped.local.toml`, the home folder is `~/WoWwrapped`. Archives recorded by Rambleon still load.
- Removed: posting to X, the route guide, the AI-written chapter per night and the in-game chapter reader.
  A night is now a facts-only page: recap, numbers, quests, timeline, pictures.
