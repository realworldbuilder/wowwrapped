# wowwrapped (Mac companion)

The `wrapped` command: it watches World of Warcraft's SavedVariables for the WoWwrapped AddOn, keeps every session in
a plain-JSON archive, writes a factual log and a story page for each night, and sums each character's nights into
a Wrapped: one page of cards, narrated by the Claude CLI when it is logged in (optional).

```bash
uv tool install "git+https://github.com/realworldbuilder/wowwrapped@v0.1.0#subdirectory=companion"
wrapped setup        # link the AddOn (bundled in this package), start the background watcher, open the journal
wrapped doctor       # is everything where WoWwrapped expects it?
wrapped make --open  # your character's Wrapped so far (--month, --year, --since/--until for a range)
wrapped --help       # everything else
```

macOS, Python 3.11+. Your files live in `~/WoWwrapped/` (archive, exports, `wowwrapped.local.toml`, `prompts/`).
The repository README has the full picture: https://github.com/realworldbuilder/wowwrapped
