# Invite a friend

Send them everything below the line. They paste it into Claude Code (or any Claude that can run commands on their
Mac) and it walks them through the install. WoWwrapped is free and open; their data stays on their Mac unless
they choose to share a page.

---

I want to set up **WoWwrapped** on this Mac. It is a free, open-source "Spotify Wrapped" for World of Warcraft
characters: a small AddOn quietly records my adventure while I play (places, levels, quests, deaths, people I grouped
with, my own notes, screenshots at big moments), and a Mac companion sums it into a Wrapped page per character, with
a facts page for every night. Repo and README: https://github.com/realworldbuilder/wowwrapped. Please read the README first, then do
the following, telling me what each step does before you run it, and stopping to ask me if anything needs a decision.

1. Check the ground: this must be macOS with World of Warcraft installed (WoWwrapped was built on WoW: Forever, the
   Classic-beta client, and expects the mainline-style 12.x AddOn API). Tell me which WoW folders you find.
2. Install the companion:
   - `brew install uv` if `uv` is missing (install Homebrew first if that is missing too, and tell me).
   - `uv tool install "git+https://github.com/realworldbuilder/wowwrapped@v0.1.0#subdirectory=companion"`
   - `wrapped setup` — it finds my WoW folder, links the AddOn into `Interface/AddOns`, installs a background
     watcher that survives reboots, and opens my empty journal. If it cannot find WoW, ask me for the path and set
     `WOWWRAPPED_WOW_DIR`. Run `wrapped doctor` afterwards and show me the result.
3. The AI step is optional. If I have Claude Code installed and logged in (`claude`, then `/login`), the companion
   uses it to add one written line per card and a closing paragraph to my Wrapped. If not, tell me I still get every
   card, the factual log, the night pages and a prompt file I can paste anywhere, and offer `wrapped setup --no-ai`.
4. Explain the in-game side in a few lines: start WoW (or relog so it sees the AddOn), `/wrapped` opens the panel,
   `/wrapped note <text>` adds my own words (they are quoted on my Wrapped), `/wrapped mark` remembers a moment
   and takes a picture, and logging out is the save. There is no end button.
5. Tell me what WoWwrapped never does: no DPS meter, no guide, no automation, no combat log, nothing leaves my Mac
   except, when AI is on, the prompt for the Wrapped.
6. Sharing is manual: `wrapped share tonight` puts a night's page and my Wrapped on a GitHub Pages site, but only
   from a git checkout of my own fork with Pages enabled. Leave that for later unless I ask.

When you are done, give me a short checklist of what is installed and where, and what to do after my first night
(`wrapped make --open`, `wrapped nights`, `wrapped page tonight`).
