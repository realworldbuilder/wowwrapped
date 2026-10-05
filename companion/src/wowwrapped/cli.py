"""The `wrapped` command."""
from __future__ import annotations

import functools
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from . import __version__
from .archive import Archive
from .doctor import apply_fixes, run_doctor
from .export import duration, export_session, night_stats, render_markdown
from .install import install_addon
from .luaparse import LuaParseError
from .paths import resolve_paths
from . import service as svc
from .nights import nights as list_nights, resolve_night
from .notify import notify
from .publish import write_html_index
from .config import effective, load_config, writer_voice
from .share import ShareError, share as run_share
from . import pipeline, prompts
from .watch import Finalizer
from .wowstate import logged_out_since
from .writer import DEFAULT_MODEL, DEFAULT_VOICE
from .watch import ingest_once, reprocess as run_reprocess, watch as run_watch

app = typer.Typer(help="WoWwrapped — your Azeroth adventure journal, Mac side.", no_args_is_help=True, add_completion=False,
                  pretty_exceptions_enable=False)
console = Console()

# What can go wrong without it being a bug: a file that is not there or not readable, a value that makes no
# sense, git or X saying no. Said in one line. Anything else is a bug and keeps its traceback.
EXPECTED = (ValueError, OSError, RuntimeError, LuaParseError)


def command(target: typer.Typer, *args, **kwargs):
    """`target.command(...)`, with expected failures reported in one red line and exit code 1.
    WOWWRAPPED_DEBUG=1 shows the traceback instead."""
    def decorate(fn):
        @functools.wraps(fn)
        def guarded(*a, **k):
            try:
                return fn(*a, **k)
            except (typer.Exit, typer.Abort):     # how a command says "done" or "cancelled" (both are RuntimeErrors)
                raise
            except EXPECTED as e:
                if os.environ.get("WOWWRAPPED_DEBUG"):
                    raise
                console.print(f"[red]{escape(str(e) or type(e).__name__)}[/red]", highlight=False, soft_wrap=True)
                raise typer.Exit(1)
        return target.command(*args, **kwargs)(guarded)
    return decorate


def log(msg: str) -> None:
    console.print(f"[dim]{datetime.now():%H:%M:%S}[/dim] {escape(msg)}", highlight=False)


def _archive() -> tuple[Archive, "Paths"]:  # type: ignore[name-defined]
    paths = resolve_paths()
    archive = Archive(paths.archive_dir)
    archive.ensure()
    return archive, paths


def _load(ref: str) -> dict:
    archive, _ = _archive()
    session = archive.load_session(ref)
    if session is None:
        console.print(f"[red]no archived session matches {ref!r}[/red] — try `wrapped sessions`")
        raise typer.Exit(1)
    return session


def _night(ref: str) -> dict:
    """A chapter = a night. ref: latest | tonight | YYYY-MM-DD | night id | session id."""
    archive, _ = _archive()
    night = resolve_night(archive, ref)
    if night is None:
        console.print(f"[red]no night matches {ref!r}[/red] — try `wrapped nights`")
        raise typer.Exit(1)
    return night


@command(app)
def version() -> None:
    """Print the companion version."""
    console.print(f"wrapped {__version__}")


def _print_checks(checks) -> None:
    width = max(len(c.label) for c in checks) + 1
    for c in checks:
        color = "green" if c.ok else ("yellow" if not c.essential else "red")
        console.print(f"{c.label + ':':<{width}} [{color}]{c.status}[/{color}]  [dim]{escape(c.detail)}[/dim]", highlight=False)


@command(app)
def doctor(fix: bool = typer.Option(False, "--fix", help="Repair what can be repaired (AddOn link, background service)."),
           check_ai: bool = typer.Option(False, "--check-ai", help="Ask the Claude CLI one small (paid) question to see if it is logged in.")) -> None:
    """Check WoW, the AddOn, SavedVariables, the archive, the watcher and the AI adapter."""
    paths = resolve_paths()
    checks = run_doctor(paths, check_ai=check_ai)
    _print_checks(checks)
    if fix:
        actions = apply_fixes(paths, checks)
        for a in actions:
            console.print(f"[green]fixed[/green] {a}")
        if actions:
            _print_checks(run_doctor(paths))
    if any(not c.ok and c.essential for c in checks):
        raise typer.Exit(1)


@command(app)
def setup(no_ai: bool = typer.Option(False, "--no-ai", help="Do not use the Claude CLI.")) -> None:
    """One command for a new Mac: link the AddOn, start the background watcher, build the journal index, open it."""
    paths = resolve_paths()
    archive = Archive(paths.archive_dir)
    archive.ensure()
    if paths.wow_dir is None:
        console.print("[red]World of Warcraft was not found.[/red] Install WoW: Forever, or set WOWWRAPPED_WOW_DIR to its folder "
                      "(the one that contains Interface/ and WTF/).")
        raise typer.Exit(1)
    console.print(f"WoW: {paths.wow_dir}")
    try:
        console.print(install_addon(paths))
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    try:
        console.print(svc.install(["--no-ai"] if no_ai else []))
    except RuntimeError as e:
        console.print(f"[yellow]background watcher not installed: {e}[/yellow] — you can run `wrapped watch` in a terminal instead")
    index = write_html_index(archive, paths.exports_dir)
    console.print(f"journal: {index}")
    checks = run_doctor(paths, check_ai=True)
    _print_checks(checks)
    console.print()
    console.print("Next: start WoW (or log out to the character screen and back in so it sees the AddOn), then play. "
                  "Type /wrapped in game. When you log out for the night, your pages are written by themselves.")
    if any(c.label == "Claude CLI" and c.status != "FOUND" for c in checks):
        console.print("For AI narration, install Claude Code and log in: run `claude`, then `/login`. "
                      "Without it you still get every page, built from the facts.")
    if sys.platform == "darwin":
        subprocess.run(["open", str(index)], check=False)


@command(app)
def uninstall(keep_archive: bool = typer.Option(True, "--keep-archive/--delete-archive",
                                                help="The archive (your history) is kept unless you say otherwise.")) -> None:
    """Remove the background service and the AddOn link. Your archive stays unless --delete-archive."""
    paths = resolve_paths()
    console.print(svc.uninstall())
    dest = paths.addon_install
    if dest and dest.is_symlink():
        dest.unlink()
        console.print(f"removed AddOn link {dest}")
    elif dest and dest.is_dir():
        console.print(f"AddOn copy left in place at {dest} (delete it yourself if you want it gone)")
    if not keep_archive:
        import shutil
        shutil.rmtree(paths.archive_dir, ignore_errors=True)
        console.print(f"deleted {paths.archive_dir}")
    else:
        console.print(f"archive kept at {paths.archive_dir}")


@command(app)
def install(copy: bool = typer.Option(False, "--copy", help="Copy the AddOn instead of symlinking it.")) -> None:
    """Link (or copy) the AddOn into the WoW Forever AddOns folder."""
    paths = resolve_paths()
    try:
        console.print(install_addon(paths, copy=copy))
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print("Now /reload in WoW (or restart it if WoWwrapped was not loaded before).")


def _finish_night(archive: Archive, paths, use_ai: bool, model: str | None = None, voice: str | None = None):
    """The watcher's part: every step of pipeline.STEPS for the night a session belongs to."""
    def run(session: dict) -> None:
        pipeline.finish_night(archive, paths, session["id"], log=log, use_ai=use_ai, model=model, voice=voice, unattended=True)
    return run


def _steps(ref: str | None, only: set[str], **options) -> pipeline.NightContext:
    """Run some of the pipeline's steps by hand; a step that failed is the command's failure."""
    archive, paths = _archive()
    ctx = pipeline.run_steps(pipeline.NightContext(archive=archive, paths=paths, night=_night(ref) if ref is not None else None,
                                                   log=log, **options), only=only)
    if ctx.failed:
        raise typer.Exit(1)
    return ctx


@command(app)
def watch(interval: float = typer.Option(1.0, help="Seconds between polls."),
          copy_screenshots: bool = typer.Option(True, "--copy-screenshots/--no-copy-screenshots", help="Copy matching screenshots into the archive."),
          no_ai: bool = typer.Option(False, "--no-ai", help="Do not call the Claude CLI when a night ends."),
          no_auto: bool = typer.Option(False, "--no-auto", help="Only archive; skip the pages."),
          model: str = typer.Option(None, "--model", help=f"Claude model (default: [wrapped] model, else {DEFAULT_MODEL})."),
          voice: str = typer.Option(None, "--voice", help="Voice profile (see `wrapped voices`; default: [wrapped] voice).")) -> None:
    """Watch SavedVariables and archive every session WoW writes. Leave this running while you play.
    When a night ends it also writes the log, the story page and the index."""
    archive, paths = _archive()
    if paths.wow_dir is None:
        console.print("[red]WoW directory not found[/red] (set WOWWRAPPED_WOW_DIR)")
        raise typer.Exit(1)
    finalizer = None if no_auto else Finalizer(_finish_night(archive, paths, use_ai=not no_ai, model=model, voice=voice), log,
                                               logged_out=lambda since: logged_out_since(paths.wow_dir, since))
    if finalizer:
        try:   # what a watcher that was down (or crashed) still owes
            finalizer.recover(pipeline.unfinished(archive, paths.exports_dir))
        except Exception as e:  # noqa: BLE001 — never a reason not to watch
            log(f"could not look for unfinished nights: {type(e).__name__}: {e}")

    seen_config: list = [None]

    def check_config() -> None:
        """Say it once when wowwrapped.local.toml changes into something that cannot be used."""
        cfg_path = paths.repo_root / "wowwrapped.local.toml"
        try:
            stamp = cfg_path.stat().st_mtime_ns
        except OSError:
            stamp = 0
        if stamp == seen_config[0]:
            return
        seen_config[0] = stamp
        cfg = load_config(paths.repo_root)
        if cfg.error:
            log(f"{cfg.error} — auto-share is off until it is fixed")
            notify("WoWwrapped", "wowwrapped.local.toml cannot be read; auto-share is off until it is fixed.")
        for w in cfg.warnings:
            log(f"wowwrapped.local.toml: {w}")
    check_config()

    def tick() -> None:
        check_config()
        finalizer.tick()
    try:
        run_watch(paths, archive, log, interval=interval, copy_screenshots=copy_screenshots,
                  after_capture=finalizer.on_capture if finalizer else None, tick=tick if finalizer else None)
    except KeyboardInterrupt:
        console.print("\nstopped.")


@command(app)
def finish(ref: str = typer.Argument("latest", help="tonight | latest | YYYY-MM-DD | night id"),
           no_ai: bool = typer.Option(False, "--no-ai", help="Do not call the Claude CLI."),
           model: str = typer.Option(None, "--model", help=f"Claude model (default: [wrapped] model, else {DEFAULT_MODEL})."),
           voice: str = typer.Option(None, "--voice", help="Voice profile (see `wrapped voices`)."),
           share_it: bool = typer.Option(False, "--share", help="Also put the page on your GitHub Pages site (asks first).")) -> None:
    """Do for a night everything the watcher does when you log out: log, story page, index.
    For a night the watcher missed, or to write one again."""
    archive, paths = _archive()
    try:
        ctx = pipeline.finish_night(archive, paths, ref, log=log, use_ai=not no_ai, model=model, voice=voice,
                                    share=share_it, confirm=lambda q: typer.confirm(q, default=False))
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(1)
    for name, result in ctx.results.items():
        color = "red" if result.startswith("failed") else "dim" if result.startswith("skipped") else "green"
        console.print(f"  {name}: [{color}]{escape(result)}[/{color}]", highlight=False)
    if ctx.failed:
        raise typer.Exit(1)


service_app = typer.Typer(help="Run the watcher in the background at login (launchd), no terminal needed.", pretty_exceptions_enable=False)
app.add_typer(service_app, name="service")


@command(service_app, "install")
def service_install(no_ai: bool = typer.Option(False, "--no-ai")) -> None:
    """Install and start the background watcher (starts again at every login)."""
    try:
        console.print(svc.install(["--no-ai"] if no_ai else []))
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@command(service_app, "uninstall")
def service_uninstall() -> None:
    """Stop and remove the background watcher."""
    console.print(svc.uninstall())


@command(service_app, "status")
def service_status() -> None:
    """Is the background watcher installed and running?"""
    console.print(svc.status())


@command(app)
def config() -> None:
    """Show the settings in effect and where they come from (wowwrapped.local.toml; every key is optional)."""
    paths = resolve_paths()
    cfg = load_config(paths.repo_root)
    console.print(f"file: {cfg.path} ({'found' if cfg.exists else 'not there; these are the defaults'})", highlight=False, soft_wrap=True)
    if cfg.error:
        console.print(f"[red]{cfg.error}[/red]", highlight=False)
        raise typer.Exit(1)
    for section, values in effective(cfg).items():
        console.print(f"[{section}]", markup=False, highlight=False)
        for key, value in values.items():
            shown = "unset" if value is None else (", ".join(value) or "all" if isinstance(value, (list, tuple)) else str(value).lower() if isinstance(value, bool) else value)
            console.print(f"  {key} = {shown}", markup=False, highlight=False)
    for slug, fields in cfg.characters.items():
        console.print(f'[characters."{slug}"] ' + ", ".join(f"{k} = {v}" for k, v in fields.items()), markup=False, highlight=False)
    for name, note in cfg.people.items():
        console.print(f'[people."{name}"] note = {note}', markup=False, highlight=False)
    for w in cfg.warnings:
        console.print(f"[yellow]warning[/yellow] {escape(w)}", highlight=False)


@command(app)
def voices() -> None:
    """List voice profiles: the bundled ones and your own. Default: golden, or `[wrapped] voice`."""
    default = writer_voice() or DEFAULT_VOICE
    for name, path in sorted(prompts.available("voices").items()):
        marker = " (default)" if name == default else ""
        console.print(f"{name}{marker}  [dim]{'yours' if prompts.is_yours(path) else 'bundled'}[/dim]", highlight=False)
    console.print(f"[dim]Your own: put <name>.md in {escape(str(prompts.user_dir() / 'voices'))}, or pass --voice /path/to/file.md[/dim]",
                  highlight=False, soft_wrap=True)


@command(app)
def nights() -> None:
    """List chapters: one per night, per character."""
    archive, _ = _archive()
    rows = list_nights(archive)
    if not rows:
        console.print("no nights archived yet.")
        return
    table = Table(box=None, header_style="bold")
    for col in ("Night", "Character", "Duration", "Lv", "Quests", "Places", "Kills", "Deaths", "People", "Sessions", "State"):
        table.add_column(col)
    for n in rows:
        st = night_stats(n)
        lv = f"{st['startLevel'] or '?'}→{st['endLevel'] or '?'}" if st["startLevel"] != st["endLevel"] else str(st["endLevel"] or "?")
        table.add_row(n["nightDate"], str(n["character"].get("displayName")), st["duration"], lv, str(st["quests"]),
                      str(st["places"]), str(st["kills"]), str(st["deaths"]), str(st["people"]),
                      str(len(n["sessionIds"])), n["state"])
    console.print(table)


@command(app)
def page(ref: str = typer.Argument("latest"), open_it: bool = typer.Option(True, "--open/--no-open")) -> None:
    """Build the HTML story page for a night (recap, screenshots, timeline) and open it in the browser."""
    out = _steps(ref, {"screenshots", "page"}).outputs["page"]
    if open_it and sys.platform == "darwin":
        subprocess.run(["open", str(out)], check=False)


@command(app)
def share(refs: list[str] = typer.Argument(None, help="tonight | latest | YYYY-MM-DD | night id (default: tonight)"),
          all_nights: bool = typer.Option(False, "--all", help="Every night; replaces site/example entirely."),
          yes: bool = typer.Option(False, "--yes", "-y", help="Do not ask before pushing."),
          dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be copied and run; change nothing.")) -> None:
    """Put a night's story page (with its pictures) on your public GitHub Pages site. Manual on purpose:
    this is the moment the chapter leaves your Mac."""
    archive, paths = _archive()
    try:
        result = run_share(archive, paths, list(refs or []), all_nights=all_nights, yes=yes, dry_run=dry_run, log=log,
                           confirm=lambda q: typer.confirm(q, default=False))
    except ShareError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    if dry_run:
        for cmd in result.commands:
            console.print("  " + " ".join(cmd))
    console.print(result.message)
    for url in result.urls:
        console.print(url)


@command(app)
def ingest(copy_screenshots: bool = typer.Option(True, "--copy-screenshots/--no-copy-screenshots")) -> None:
    """Archive whatever WoWwrapped SavedVariables exist right now (one pass, no watching)."""
    archive, paths = _archive()
    outcomes = ingest_once(paths, archive, log, copy_screenshots)
    if outcomes:
        console.print(f"{len(outcomes)} outcome(s): " + ", ".join(outcomes))
    else:
        console.print("nothing new.")


@command(app)
def reprocess(copy_screenshots: bool = typer.Option(True, "--copy-screenshots/--no-copy-screenshots")) -> None:
    """Rebuild normalized sessions from the archived raw snapshots (use after upgrading the companion)."""
    archive, paths = _archive()
    run_reprocess(paths, archive, log, copy_screenshots)


@command(app)
def status() -> None:
    """Archive overview and the latest session."""
    archive, paths = _archive()
    sessions = archive.list_sessions()
    owed = pipeline.unfinished(archive, paths.exports_dir)
    pid = archive.watcher_pid()
    console.print(f"Archive: {paths.archive_dir} — {len(sessions)} session(s)")
    console.print(f"Watcher: {'running (pid ' + str(pid) + ')' if pid else 'not running'}")
    sv = paths.saved_variables_files()
    if sv:
        newest = max(sv, key=lambda p: p.stat().st_mtime)
        console.print(f"SavedVariables last written: {datetime.fromtimestamp(newest.stat().st_mtime):%Y-%m-%d %H:%M:%S}")
    total = sum(s.get("playedSeconds") or 0 for s in sessions)
    if sessions:
        console.print(f"Total time in Azeroth (archived): {duration(total)}")
        s = sessions[-1]
        console.print(f"Latest: {s['character']} — {datetime.fromtimestamp(s['startedAt']):%B %-d, %Y %-I:%M %p} — "
                      f"{duration(s.get('playedSeconds'))} — {s['events']} events — {s['state']}")
    for night in owed:
        console.print(f"[yellow]Not finished:[/yellow] {night['character'].get('displayName')}, {night['nightDate']} — the watcher writes it "
                      f"when it starts, or run `wrapped finish {night['nightDate']}`", highlight=False)


@command(app)
def sessions() -> None:
    """List archived sessions."""
    archive, _ = _archive()
    rows = archive.list_sessions()
    if not rows:
        console.print("no sessions archived yet.")
        return
    table = Table(box=None, header_style="bold")
    for col in ("When", "Character", "Duration", "Lv", "Quests", "Places", "Deaths", "People", "Events", "State", "Session ID"):
        table.add_column(col)
    for s in rows:
        c = s.get("counters", {})
        lv = f"{s.get('startLevel', '?')}→{s.get('endLevel', '?')}" if s.get("startLevel") != s.get("endLevel") else str(s.get("endLevel", "?"))
        table.add_row(datetime.fromtimestamp(s["startedAt"]).strftime("%Y-%m-%d %H:%M"), str(s.get("character")),
                      duration(s.get("playedSeconds")), lv, str(c.get("questsCompleted", 0)), str(c.get("zonesVisited", 0)),
                      str(c.get("deaths", 0)), str(s.get("people", 0)), str(s.get("events")),
                      ("trivial" if s.get("trivial") else str(s.get("state"))), str(s.get("id")))
    console.print(table)


@command(app)
def show(ref: str = typer.Argument("latest"), as_json: bool = typer.Option(False, "--json")) -> None:
    """Show one session (default: latest) as a factual log, or as JSON."""
    session = _load(ref)
    if as_json:
        console.print_json(json.dumps(session))
    else:
        console.print(render_markdown(session), markup=False, highlight=False)


@command(app)
def export(ref: str = typer.Argument("latest"), all_nights: bool = typer.Option(False, "--all")) -> None:
    """Write the factual Markdown log of a night (latest | tonight | YYYY-MM-DD | session id) to exports/markdown/."""
    archive, paths = _archive()
    targets = list_nights(archive) if all_nights else [_night(ref)]
    for night in targets:
        out = export_session(night, paths.exports_dir)
        console.print(f"exported {out}")


def _slug(archive: Archive, ref: str) -> str:
    """A character slug from `latest` (the character who played last) or a slug seen in the archive."""
    if ref in ("latest", "tonight", "last", ""):
        night = resolve_night(archive, "latest")
        if night is None:
            console.print("[red]no nights archived yet[/red] — play a session first, or run `wrapped ingest`")
            raise typer.Exit(1)
        return night["character"].get("slug", "unknown")
    known = sorted({n["character"].get("slug") for n in list_nights(archive) if n["character"].get("slug")})
    if ref in known:
        return ref
    console.print(f"[red]no character matches {ref!r}[/red] — known: {', '.join(known) or 'none yet'}")
    raise typer.Exit(1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
