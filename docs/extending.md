# Extending WoWwrapped

Three things are built to be added to: what is remembered, what is made from a night, and how it is written.
Each is one entry in one list. Before any of them, ask the question in `CLAUDE.md`:
**will this help the player remember their adventure?** Memories, not telemetry.

`scripts/test` must pass afterwards. It runs a scripted evening through the AddOn under a WoW API stub, writes that
evening as the companion's test fixture, and runs the companion's tests against it.

## 1. A new thing to remember (an event type)

An event type lives in two tables that must agree: `addon/WoWwrapped/EventTypes.lua` and
`companion/src/wowwrapped/events.py`. The tests fail if one has a type the other lacks, if their counters differ, or if
the scripted evening never records it.

Worked example: remembering that the player took a flight (`FLIGHT_TAKEN`).

**AddOn**

1. `EventTypes.lua`: one entry. `describe` is how it reads in the in-game log; `counter` (optional) is the key in
   `session.counters` that goes up by one.

   ```lua
   FLIGHT_TAKEN = { describe = function(ev) return "Flew to " .. tostring(ev.name or "somewhere") end },
   ```

2. `Events.lua`: a handler for the game event that tells you. Registration is automatic and guarded (an event this
   client does not know is skipped and listed under `/wrapped debug`).

   ```lua
   handlers.SOME_GAME_EVENT = function(destination)
     if not ns.EnsureSession() then return end
     ns.AddEvent("FLIGHT_TAKEN", { name = ns.CleanString(destination) })
   end
   ```

   Rules that are not optional: values go through `ns.Clean` / `ns.CleanString` (nothing secret, nothing that is not
   a string, number or boolean); call client functions through `ns.SafeCall`; no combat log, no protected APIs.
   `ns.AddEvent` adds the time, level and place by itself.

3. `addon/tests/wowstub.lua` if the handler calls a client function the stub lacks, and `addon/tests/run.lua`: fire
   the event in the scripted evening (before the fixture is written, without adding clock time) and assert the result.

**Companion**

4. `events.py`: the twin entry.

   ```python
   "FLIGHT_TAKEN": EventType(lambda ev: f"Flew to {ev.get('name') or 'somewhere'}"),
   ```

   | field | meaning | default |
   |---|---|---|
   | `describe` | the line in the Markdown log and the story page timeline | required |
   | `stitch` | joining sessions into a night: `keep`, `drop`, `first`, `last` | `keep` |
   | `timeline` | listed at all | `True` |
   | `shot_fallback` | a screenshot with no event of its own may be captioned by this moment | `True` |
   | `counter` | the counter the AddOn bumps; must also be in `model.COUNTER_KEYS` | none |

That is a complete type: it is archived and shown in the log and on the night's page. Anything more specific
(a number or a card on the Wrapped) is ordinary code in `wrapped.py`: `build_wrapped` sums it, `cards` shows it.

A type the companion does not know yet is never dropped: it reads as its name in plain words. So an AddOn that is
newer than the companion loses nothing.

Adding a **new file** to `addon/WoWwrapped/` means listing it in both TOCs, in `companion/pyproject.toml`
(`force-include`) and in `addon/tests/run.lua`; `tests/test_packaging.py` checks all four agree.

## 2. A new output (a pipeline step)

What happens after a night is `STEPS` in `companion/src/wowwrapped/pipeline.py`. The watcher runs all of them;
`wrapped finish` does the same by hand. A step is a function of the `NightContext` that returns a line for the log:

```python
def step_recap_card(ctx: NightContext) -> str:
    out = ctx.paths.exports_dir / "social" / f"{ctx.night['id']}.txt"
    atomic_write_bytes(out, render_recap(ctx.night).encode("utf-8"))
    ctx.outputs["recap_card"] = out
    return f"recap card {out}"

STEPS = [..., Step("page", step_page), Step("recap_card", step_recap_card), Step("index", step_index), ...]
```

The steps today: `screenshots` → `markdown` → `wrapped` → `page` → `index` → `share` → `notify`.

- A step that raises is logged and recorded as failed; the steps after it still run.
- `raise Skip("why")` when there is nothing to do.
- `ctx.unattended` is true when the watcher is running it: nobody is there to ask. Anything that leaves the Mac
  must be opted into in `wowwrapped.local.toml` when unattended, and asked for by hand otherwise (see `step_share`).
- `needs_ai=True` marks a step that may call the Claude CLI. It must still do its non-AI part (write the prompt)
  when `ctx.use_ai` is false.

A new HTML page is a body inside `pages.shell(...)`; the styles are `assets/page.css` (and `assets/wrapped.css` for
the Wrapped).

A new setting goes in `config.py`: a field on the section's dataclass and a rule in `SECTIONS`. Unknown keys and
bad values are reported by `wrapped config` and `wrapped doctor` without any further code.

## 3. A new way of writing (voices, rules, theme)

No code. Files in the player's own folder, `<home>/prompts/` (`~/WoWwrapped/prompts/` for a package install, the
checkout otherwise; `wrapped voices` prints the path):

| file | what it is | used by |
|---|---|---|
| `voices/<name>.md` | a voice: how the Wrapped's lines should sound | `wrapped make --voice <name>`, `[wrapped] voice = "<name>"` |
| `wrapped.md` | the rules the Wrapped is narrated by (replaces the bundled ones) | every Wrapped |
| `theme.css` | CSS added after the page styles | every story page, index and Wrapped |

A file of yours with a bundled name wins. A path to a `.md` file works wherever a name does.

Placeholders WoWwrapped fills in in `wrapped.md`: `{voice}`, `{name}` and `{pronouns}`. Any other `{word}` is sent
to the writer as written, and pointed out when the prompt is built in case it was a typo. The writer must answer in
the shape the bundled rules ask for (one `key: sentence` line per card, a `---CLOSING---` line, a closing
paragraph), so keep that part when you write your own.

To ship a voice with WoWwrapped, put the file in `companion/src/wowwrapped/prompts/voices/`.
The honesty rules in the bundled `prompts/wrapped.md` (only the facts on the cards; names exactly as given; the
player's notes are the most important evidence) are the product; a voice changes the sound, never the facts.
