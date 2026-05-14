#!/usr/bin/env python3
"""Snapshot / restore the Zava simulator state.

Bundles the Kuzu entity graph (`data/portal/entity_graph.kuzu/`) plus an
ambient-state JSON sidecar into a portable tarball at
`data/snapshots/<name>.tgz`. Lets a pitch operator capture a known-good
"morning run" and rehydrate it on cold boot in 2-5 seconds, instead of
waiting for the substrate + simulator ramp loop to populate the graph.

Bundle layout (`<name>.tgz`):
    entity_graph.kuzu/    — full Kuzu DB directory (directly under root)
    ambient_state.json    — placeholder for in-memory ambient-agent state.
                            Currently `{}`. Future tracks (e.g. j7 —
                            persistent ambient-agent state across restarts)
                            will populate this sidecar; the bundle format
                            stays stable.
    meta.json             — {name, created_at, kuzu_size_bytes,
                            ambient_state_keys, substrate_version}

Process management is OUT OF SCOPE: the script does NOT stop or start the
running stack. The operator must `Ctrl-C` `make up` before `restore`,
otherwise Kuzu will keep its file lock and the restore will fail. See
`_check_kuzu_locked()` for the diagnostic.

No third-party dependencies — stdlib only (tarfile / pathlib / json /
subprocess).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PORTAL_DIR = REPO_ROOT / "data" / "portal"
KUZU_DIR_NAME = "entity_graph.kuzu"
KUZU_PATH = PORTAL_DIR / KUZU_DIR_NAME
SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots"
AMBIENT_STATE_FILENAME = "ambient_state.json"
META_FILENAME = "meta.json"


# ---------------------------------------------------------------------------
# Ambient + learning modules whose in-memory state is captured into the
# `ambient_state.json` sidecar (pitch-j7). Each module exposes a
# ``dump_state() -> dict`` and ``load_state(dict) -> None`` pair — the
# bundle uses the dotted module path as the namespacing key so a stale
# entry for a removed module is silently skipped on restore.
# ---------------------------------------------------------------------------
AMBIENT_STATE_MODULES: tuple[str, ...] = (
    "api.server.services.ambient_agents.auto_block_rule_learner",   # I2
    "api.server.services.classifier_cache",                          # I3
    "api.server.services.routing_stats",                             # I4
    "api.server.services.persona_experience",                        # I6
    "api.server.services.ambient_agents.vendor_block_watcher",       # H1
    "api.server.services.ambient_agents.brand_budget_watcher",       # H2
    "api.server.services.ambient_agents.subsidiary_capacity_watcher",  # H4
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _git_short_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _snapshot_path(name: str) -> Path:
    if not name or "/" in name or name.startswith("."):
        raise SystemExit(f"error: invalid snapshot name: {name!r}")
    return SNAPSHOT_DIR / f"{name}.tgz"


def _check_kuzu_locked(kuzu_dir: Path) -> str | None:
    """Return a human-readable message if the Kuzu DB is held by another
    process, else None.

    Kuzu writes a `.lock` file inside the DB dir on first open and never
    removes it (it's a sentinel for an OS-level advisory file lock). The
    file's mere presence is therefore *not* evidence the engine is
    running. We try to acquire an exclusive `flock` on it: if another
    process holds it (e.g. the live FastAPI server), the call fails and
    we know to bail out before clobbering the directory.

    On platforms without `fcntl` (Windows) we fall back to a best-effort
    rename probe.
    """
    if not kuzu_dir.exists():
        return None
    lock_path = kuzu_dir / ".lock"
    if not lock_path.exists():
        return None
    try:
        import fcntl  # POSIX only
        with open(lock_path, "rb") as fh:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                return None
            except OSError:
                return (
                    "Kuzu DB at "
                    f"{kuzu_dir} is locked by another process — the stack "
                    "appears to be running. Stop it (Ctrl-C `make up`) and retry."
                )
    except ImportError:
        # Windows: try renaming the dir as a probe.
        probe = kuzu_dir.with_suffix(kuzu_dir.suffix + ".probe")
        try:
            kuzu_dir.rename(probe)
            probe.rename(kuzu_dir)
            return None
        except OSError:
            return (
                f"Kuzu DB at {kuzu_dir} appears locked — stop the stack "
                "(Ctrl-C `make up`) and retry."
            )


def _read_counts(kuzu_dir: Path) -> dict[str, int]:
    """Best-effort entity / edge counts. Returns {} if Kuzu isn't usable."""
    try:
        import kuzu  # type: ignore
    except ImportError:
        return {}
    try:
        db = kuzu.Database(str(kuzu_dir))
        conn = kuzu.Connection(db)
        nodes = 0
        edges = 0
        try:
            tables = conn.execute("CALL show_tables() RETURN *;")
            while tables.has_next():
                row = tables.get_next()
                # row layout (kuzu 0.6): [name, type, database_name, comment]
                tname = row[0]
                ttype = row[1]
                if ttype == "NODE":
                    res = conn.execute(f"MATCH (n:`{tname}`) RETURN count(n);")
                    if res.has_next():
                        nodes += int(res.get_next()[0])
                elif ttype == "REL":
                    res = conn.execute(f"MATCH ()-[r:`{tname}`]->() RETURN count(r);")
                    if res.has_next():
                        edges += int(res.get_next()[0])
        finally:
            del conn
            del db
        return {"nodes": nodes, "edges": edges}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


def _collect_ambient_state() -> dict[str, dict]:
    """Import each AMBIENT_STATE_MODULES entry and call its ``dump_state``.
    Tolerant: a module that fails to import or lacks ``dump_state`` is
    skipped with a warning rather than aborting the snapshot."""
    import importlib
    out: dict[str, dict] = {}
    for mod_path in AMBIENT_STATE_MODULES:
        try:
            mod = importlib.import_module(mod_path)
            dumper = getattr(mod, "dump_state", None)
            if dumper is None:
                print(f"warn: {mod_path} has no dump_state(); skipping", file=sys.stderr)
                continue
            out[mod_path] = dumper()
        except Exception as exc:
            print(f"warn: dump_state failed for {mod_path}: {exc}", file=sys.stderr)
    return out


def _restore_ambient_state(state: dict[str, dict]) -> None:
    """Call ``load_state`` on each known module. Per-module try/except so a
    stale or removed module doesn't fail the whole restore."""
    import importlib
    for mod_path, payload in state.items():
        try:
            mod = importlib.import_module(mod_path)
            loader = getattr(mod, "load_state", None)
            if loader is None:
                print(f"warn: {mod_path} has no load_state(); skipping", file=sys.stderr)
                continue
            loader(payload or {})
        except Exception as exc:
            print(f"warn: load_state failed for {mod_path}: {exc}", file=sys.stderr)


def cmd_save(name: str) -> int:
    if not KUZU_PATH.exists():
        print(f"error: no Kuzu DB at {KUZU_PATH}", file=sys.stderr)
        return 1
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _snapshot_path(name)
    if out_path.exists():
        print(f"warn: overwriting existing snapshot {out_path.name}")

    counts = _read_counts(KUZU_PATH)
    ambient_state = _collect_ambient_state()
    meta = {
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "kuzu_size_bytes": _dir_size_bytes(KUZU_PATH),
        "ambient_state_keys": sorted(ambient_state.keys()),
        "substrate_version": _git_short_sha(),
        "counts": counts,
    }

    tmp = out_path.with_suffix(".tgz.partial")
    with tarfile.open(tmp, "w:gz") as tar:
        tar.add(KUZU_PATH, arcname=KUZU_DIR_NAME)
        _add_json(tar, AMBIENT_STATE_FILENAME, ambient_state)
        _add_json(tar, META_FILENAME, meta)
    tmp.replace(out_path)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"saved {out_path.relative_to(REPO_ROOT)} ({size_mb:.1f} MiB)")
    if counts:
        print(f"  nodes={counts.get('nodes', 0)} edges={counts.get('edges', 0)}")
    return 0


def cmd_restore(name: str) -> int:
    src = _snapshot_path(name)
    if not src.exists():
        print(f"error: snapshot not found: {src}", file=sys.stderr)
        return 1

    locked_msg = _check_kuzu_locked(KUZU_PATH)
    if locked_msg:
        print(f"error: {locked_msg}", file=sys.stderr)
        print(
            "  → stop the stack (Ctrl-C in the `make up` terminal) and re-run.",
            file=sys.stderr,
        )
        return 2

    PORTAL_DIR.mkdir(parents=True, exist_ok=True)
    backup = PORTAL_DIR / f"{KUZU_DIR_NAME}.bak"
    if KUZU_PATH.exists():
        if backup.exists():
            shutil.rmtree(backup)
        try:
            KUZU_PATH.rename(backup)
            print(f"  backed up live DB → {backup.relative_to(REPO_ROOT)}")
        except OSError as exc:
            print(
                f"error: could not move live DB aside ({exc}). "
                f"Is the stack still running?",
                file=sys.stderr,
            )
            return 2

    try:
        with tarfile.open(src, "r:gz") as tar:
            members = tar.getmembers()
            for m in members:
                # guard against path traversal
                target = (PORTAL_DIR / m.name).resolve()
                if not str(target).startswith(str(PORTAL_DIR.resolve())):
                    raise SystemExit(f"refusing unsafe member: {m.name}")
            tar.extractall(PORTAL_DIR)
    except Exception as exc:
        # roll back
        if KUZU_PATH.exists():
            shutil.rmtree(KUZU_PATH, ignore_errors=True)
        if backup.exists():
            backup.rename(KUZU_PATH)
        print(f"error: extract failed ({exc}); rolled back from .bak", file=sys.stderr)
        return 3

    counts = _read_counts(KUZU_PATH)
    print(f"restored {src.relative_to(REPO_ROOT)} → {KUZU_PATH.relative_to(REPO_ROOT)}")
    if counts:
        print(f"  nodes={counts.get('nodes', 0)} edges={counts.get('edges', 0)}")

    # Rehydrate ambient + learning module state (pitch-j7).
    ambient_path = PORTAL_DIR / AMBIENT_STATE_FILENAME
    loaded_keys: list[str] = []
    if ambient_path.exists():
        try:
            with open(ambient_path, "r", encoding="utf-8") as fh:
                ambient_state = json.load(fh)
            if isinstance(ambient_state, dict) and ambient_state:
                _restore_ambient_state(ambient_state)
                loaded_keys = sorted(ambient_state.keys())
        except Exception as exc:
            print(
                f"warn: could not parse {AMBIENT_STATE_FILENAME} "
                f"({exc}); ambient state not rehydrated",
                file=sys.stderr,
            )
    if loaded_keys:
        print(f"  rehydrated ambient state for {len(loaded_keys)} module(s)")

    print(
        f"  previous DB preserved at {backup.relative_to(REPO_ROOT)} "
        f"(delete manually when satisfied)"
    )
    return 0


def cmd_list() -> int:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    snaps = sorted(SNAPSHOT_DIR.glob("*.tgz"))
    if not snaps:
        print("no snapshots in data/snapshots/")
        return 0
    print(f"{'NAME':<24} {'SIZE':>10}  CREATED")
    for p in snaps:
        size = p.stat().st_size
        size_h = _human_size(size)
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        print(f"{p.stem:<24} {size_h:>10}  {mtime.isoformat(timespec='seconds')}")
    return 0


def cmd_info(name: str) -> int:
    src = _snapshot_path(name)
    if not src.exists():
        print(f"error: snapshot not found: {src}", file=sys.stderr)
        return 1
    with tarfile.open(src, "r:gz") as tar:
        try:
            f = tar.extractfile(META_FILENAME)
        except KeyError:
            f = None
        if f is None:
            print(f"error: {src.name} has no {META_FILENAME}", file=sys.stderr)
            return 1
        meta = json.load(f)
    print(json.dumps(meta, indent=2, sort_keys=True))
    return 0


# ---------------------------------------------------------------------------
# tar helpers
# ---------------------------------------------------------------------------


def _add_json(tar: tarfile.TarFile, name: str, payload) -> None:
    import io
    blob = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    info = tarfile.TarInfo(name=name)
    info.size = len(blob)
    info.mtime = int(time.time())
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(blob))


def _human_size(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} TiB"


# ---------------------------------------------------------------------------
# entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="zava-snapshot",
        description="Snapshot / restore the Zava simulator state "
                    "(Kuzu entity graph + ambient-state sidecar).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sp_save = sub.add_parser("save", help="bundle current state into data/snapshots/<name>.tgz")
    sp_save.add_argument("name")
    sp_restore = sub.add_parser("restore", help="restore from data/snapshots/<name>.tgz")
    sp_restore.add_argument("name")
    sub.add_parser("list", help="list available snapshots")
    sp_info = sub.add_parser("info", help="show metadata of a snapshot")
    sp_info.add_argument("name")

    args = p.parse_args(argv)
    if args.cmd == "save":
        return cmd_save(args.name)
    if args.cmd == "restore":
        return cmd_restore(args.name)
    if args.cmd == "list":
        return cmd_list()
    if args.cmd == "info":
        return cmd_info(args.name)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
