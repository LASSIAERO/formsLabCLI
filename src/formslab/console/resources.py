"""The console's view of the external-resource registry.

A renderer, and deliberately nothing more. Every fact shown here comes from
``forms.bricks.resources.resource_report()`` and every action goes through
``forms.bricks.fetch.update_resource()``. The previous version of this file kept
its own copy of the eight IAU filenames, its own 30-day staleness threshold and
its own EOP-only update branch — three pieces of registry knowledge that drifted
from the library the moment either side changed.

Adding a resource is now an edit to the registry alone; this file learns about
it for free.
"""

from __future__ import annotations

from rich.console import Group
from rich.table import Table
from rich.text import Text

import formslab.bridge as bridge
import formslab.console.style as style
from formslab.console.sessions.base import CLIResult


def _state_text(status) -> Text:
    """One word per row — what an operator needs to see at a glance."""
    if status.ok:
        return Text("OK", style=style.SUCCESS)
    if not status.present:
        return Text("MISSING", style=style.ERROR)
    if status.missing_members:
        return Text("INCOMPLETE", style=style.WARNING)
    return Text("STALE", style=style.WARNING)


def _detail(status) -> str:
    """The middle column: coverage, age, or how many members are absent."""
    bits = []
    if status.missing_members and not status.detail:
        # A directory resource already reports "N/M files present" in `detail`;
        # only spell the count out when it does not.
        bits.append(f"missing {len(status.missing_members)} file(s)")
    if status.detail:
        bits.append(status.detail)
    if status.age_days is not None:
        bits.append(f"{status.age_days} days old")
    return "; ".join(bits)


def _render_resource_tables() -> Group:
    registry = bridge.resources()
    ENV_VAR = registry.ENV_VAR
    bundled_dir, external_dir = registry.bundled_dir, registry.external_dir
    repo_dirs, resources_root = registry.repo_dirs, registry.resources_root
    resource_report = registry.resource_report

    roots = Table(title="Resource roots (searched in this order)",
                  show_lines=False)
    roots.add_column("Root", style=style.HEADER)
    roots.add_column("Path", style=style.DIM, overflow="fold")
    roots.add_column("Status")

    ext = external_dir()
    roots.add_row(
        f"external (${ENV_VAR})",
        str(ext) if ext is not None else "(unset)",
        Text("OK", style=style.SUCCESS)
        if ext is not None and ext.exists()
        else Text("unset" if ext is None else "MISSING",
                  style=style.DIM if ext is None else style.ERROR),
    )
    # Every checkout folder, not just the first: a git worktree has a partial
    # resources/ of its own and the rest lives in the checkout it came from.
    for i, repo in enumerate(repo_dirs()):
        roots.add_row(
            "checkout" if i == 0 else "checkout (main)", str(repo),
            Text("OK", style=style.SUCCESS))
    bundled = bundled_dir()
    roots.add_row(
        "bundled (in package)", str(bundled),
        Text("OK", style=style.SUCCESS) if bundled.exists()
        else Text("MISSING", style=style.ERROR),
    )
    target = resources_root()
    roots.caption = (f"Updates write to: {target}" if target is not None
                     else f"No writable root — set ${ENV_VAR} to update.")

    table = Table(title="FORMS Resources", show_lines=False)
    table.add_column("Key", style=style.HEADER)
    table.add_column("Tier", style=style.DIM)
    table.add_column("State")
    table.add_column("Detail", style=style.TEXT, overflow="fold")
    table.add_column("Path", style=style.DIM, overflow="fold")

    report = resource_report()
    for status in report:
        table.add_row(status.key, status.tier, _state_text(status),
                      _detail(status), status.path)

    todo = [f"  {s.key}: {s.action}" for s in report if s.action]
    actions = Text(
        ("Actions:\n" + "\n".join(todo)) if todo
        else "Everything present and current.",
        style=style.WARNING if todo else style.SUCCESS,
    )

    tips = Text(
        "Commands: resources | resources <key> --check | resources <key> "
        "--update [--force] | resources --update-stale",
        style=style.DIM,
    )
    return Group(roots, table, actions, tips)


def _resources_help() -> CLIResult:
    resource_keys = bridge.resources().resource_keys

    lines = [
        "Resource Commands:",
        "  resources                       Show the resource inventory",
        "  resources --help                Show this help",
        "  resources <key> --check         Status of one resource",
        "  resources <key> --update        Fetch it if stale (--force to always)",
        "  resources --update-stale        Fetch everything stale that has a source",
        "  --resources ...                 Legacy alias (still supported)",
        "",
        "Keys: " + ", ".join(resource_keys()),
        "",
        "FORMS never downloads on its own — every fetch is a command you run.",
    ]
    return CLIResult(content=Text("\n".join(lines), style=style.TEXT))


def _check(key: str) -> CLIResult:
    resource_status = bridge.resources().resource_status

    try:
        status = resource_status(key)
    except KeyError as exc:
        return CLIResult(content=Text(str(exc), style=style.ERROR))

    lines = [
        f"{status.key} — {status.title}",
        f"  tier: {status.tier} ({status.kind})",
        f"  path: {status.path}",
        f"  present: {status.present}",
    ]
    if status.age_days is not None:
        lines.append(f"  age: {status.age_days} days")
    if status.detail:
        lines.append(f"  detail: {status.detail}")
    if status.missing_members:
        lines.append(f"  missing: {', '.join(status.missing_members)}")
    if status.required_for:
        lines.append(f"  needed for: {status.required_for}")
    if status.note:
        lines.append(f"  note: {status.note}")
    lines.append(f"  action: {status.action or 'none — present and current'}")

    return CLIResult(content=Text(
        "\n".join(lines),
        style=style.SUCCESS if status.ok else style.WARNING))


def _update(key: str, *, force: bool) -> CLIResult:
    update_resource = bridge.fetch().update_resource

    try:
        outcome = update_resource(key, force=force)
    except (KeyError, ValueError, RuntimeError) as exc:
        return CLIResult(content=Text(str(exc), style=style.ERROR))
    except Exception as exc:                    # network, disk, permissions
        return CLIResult(content=Text(f"{key}: update failed: {exc}",
                                      style=style.ERROR))

    if not outcome.updated:
        return CLIResult(content=Text(f"{outcome.key}: {outcome.reason}",
                                      style=style.SUCCESS))
    size = (f" ({outcome.bytes_written / 1024:.1f} KB)"
            if outcome.bytes_written else "")
    return CLIResult(content=Text(
        f"{outcome.key}: updated{size} -> {outcome.path}", style=style.SUCCESS))


def _update_stale() -> CLIResult:
    update_stale_resources = bridge.fetch().update_stale_resources

    try:
        outcomes = update_stale_resources()
    except Exception as exc:
        return CLIResult(content=Text(f"update failed: {exc}",
                                      style=style.ERROR))

    if not outcomes:
        return CLIResult(content=Text(
            "Nothing to update — every fetchable resource is current.",
            style=style.SUCCESS))
    lines = [f"  {o.key}: {'updated' if o.updated else o.reason} -> {o.path}"
             for o in outcomes]
    return CLIResult(content=Text("Updated:\n" + "\n".join(lines),
                                  style=style.SUCCESS))


def handle_resources_command(raw: str) -> CLIResult:
    parts = raw.strip().split()
    if len(parts) == 1:
        return CLIResult(content=_render_resource_tables())

    token = parts[1].lower()
    if token in ("--help", "help"):
        return _resources_help()
    if token in ("status", "--status"):
        return CLIResult(content=_render_resource_tables())
    if token in ("--update-stale", "update-stale"):
        return _update_stale()

    # Anything else is a resource key or alias; the registry decides, so a new
    # resource is reachable here the moment it is registered.
    key = parts[1]
    if len(parts) == 2:
        return _check(key)

    action = parts[2].lower()
    force = any(p.lower() == "--force" for p in parts[3:])
    if action in ("--check", "check", "status"):
        return _check(key)
    if action in ("--update", "update", "download"):
        return _update(key, force=force)
    return CLIResult(content=Text(
        f"Unknown option {parts[2]!r} for {key!r}; use --check or --update.",
        style=style.ERROR))
