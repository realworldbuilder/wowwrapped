# wowwrapped (Mac companion)

The `wrapped` command: it watches World of Warcraft's SavedVariables for the WoWwrapped AddOn, keeps every session in
a plain-JSON archive, and turns each night into a factual log, an AI-written chapter (optional), a story page and
a route guide, then publishes the chapters back into the game.

```bash
uv tool install "git+https://github.com/realworldbuilder/wowwrapped@v0.1.0#subdirectory=companion"
wrapped setup        # link the AddOn (bundled in this package), start the background watcher, open the journal
wrapped doctor       # is everything where WoWwrapped expects it?
wrapped --help       # everything else
```

macOS, Python 3.11+. Your files live in `~/WoWwrapped/` (archive, exports, `wowwrapped.local.toml`, `prompts/`).
The repository README has the full picture: https://github.com/realworldbuilder/wowwrapped
