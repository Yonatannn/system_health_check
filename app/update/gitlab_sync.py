from __future__ import annotations
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable


@dataclass
class GitSyncResult:
    name: str
    success: bool
    commit: Optional[str] = None
    error: Optional[str] = None


def _run_git(args: list[str], cwd: Optional[Path] = None, timeout: int = 120) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["git"] + args,
            capture_output=True, text=True, timeout=timeout,
            cwd=str(cwd) if cwd else None,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "git command timed out"
    except FileNotFoundError:
        return -1, "", "git executable not found"
    except Exception as e:
        return -1, "", str(e)


def _get_commit(local_path: Path, log: Callable[[str], None]) -> Optional[str]:
    rc, out, err = _run_git(["rev-parse", "HEAD"], cwd=local_path)
    if rc == 0 and out:
        return out
    log(f"  Warning: could not read HEAD commit (rc={rc}): {err or 'no output'}")
    return None


def sync_repository(name: str, url: str, branch: str, local_path: Path,
                    log: Optional[Callable[[str], None]] = None) -> GitSyncResult:
    log = log or (lambda msg: None)

    log(f"[{name}] Local path: {local_path.resolve()}")

    if local_path.exists() and (local_path / ".git").exists():
        log(f"[{name}] Repo exists — fetching from {url}…")
        rc, out, err = _run_git(["fetch", "origin"], cwd=local_path)
        if rc != 0:
            log(f"[{name}] git fetch stderr: {err}")
            return GitSyncResult(name=name, success=False, error=f"git fetch failed: {err}")
        if err:
            log(f"[{name}] fetch info: {err}")

        log(f"[{name}] Resetting to origin/{branch}…")
        rc, out, err = _run_git(["reset", "--hard", f"origin/{branch}"], cwd=local_path)
        if rc != 0:
            log(f"[{name}] git reset stderr: {err}")
            return GitSyncResult(name=name, success=False, error=f"git reset failed: {err}")
        log(f"[{name}] Reset: {out or err or 'ok'}")

        rc, out, err = _run_git(["clean", "-fd"], cwd=local_path)
        if rc != 0:
            log(f"[{name}] Warning: git clean failed: {err}")

        log(f"[{name}] Updating submodules…")
        rc, out, err = _run_git(["submodule", "update", "--init", "--recursive"], cwd=local_path)
        if rc != 0:
            log(f"[{name}] Warning: submodule update failed: {err}")
        elif out or err:
            log(f"[{name}] Submodules: {out or err}")
    else:
        if local_path.exists():
            log(f"[{name}] Directory exists but has no .git — recloning")
        else:
            log(f"[{name}] Directory not found — cloning fresh")
        log(f"[{name}] Cloning {url} (branch: {branch})…")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        rc, out, err = _run_git(
            ["clone", "--recurse-submodules", "--branch", branch, url, str(local_path)],
        )
        if rc != 0:
            log(f"[{name}] git clone stderr: {err}")
            return GitSyncResult(name=name, success=False, error=f"git clone failed: {err}")
        log(f"[{name}] Clone complete")

    commit = _get_commit(local_path, log)
    log(f"[{name}] HEAD commit: {commit or 'unknown'}")

    # Log top-level directory contents so user can see what was cloned
    try:
        entries = sorted(p.name for p in local_path.iterdir())
        log(f"[{name}] Repo root contents: {', '.join(entries) or '(empty)'}")
    except Exception:
        pass

    return GitSyncResult(name=name, success=True, commit=commit)


def sync_all_repositories(repos: list[dict], sources_dir: Path,
                           log: Optional[Callable[[str], None]] = None) -> list[GitSyncResult]:
    results = []
    for repo in repos:
        name = repo.get("name", "unknown")
        url = repo.get("url", "")
        branch = repo.get("branch", "main")
        local_path = Path(repo.get("local_path", str(sources_dir / "gitlab" / name)))
        result = sync_repository(name=name, url=url, branch=branch,
                                 local_path=local_path, log=log)
        results.append(result)
    return results
