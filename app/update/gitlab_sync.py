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


def _run_git(args: list[str], cwd: Optional[Path] = None, timeout: int = 120,
             git_exe: str = "git") -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            [git_exe] + args,
            capture_output=True, text=True, timeout=timeout,
            cwd=str(cwd) if cwd else None,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "git command timed out"
    except FileNotFoundError:
        return -1, "", f"git executable '{git_exe}' not found"
    except Exception as e:
        return -1, "", str(e)


def _get_commit(local_path: Path, git_exe: str) -> Optional[str]:
    rc, out, _ = _run_git(["rev-parse", "HEAD"], cwd=local_path, git_exe=git_exe)
    return out if rc == 0 else None


def sync_repository(name: str, url: str, branch: str, local_path: Path,
                    git_exe: str = "git",
                    log: Optional[Callable[[str], None]] = None) -> GitSyncResult:
    log = log or (lambda msg: None)

    if local_path.exists() and (local_path / ".git").exists():
        log(f"[{name}] Fetching from {url}…")
        rc, _, err = _run_git(["fetch", "origin"], cwd=local_path, git_exe=git_exe)
        if rc != 0:
            return GitSyncResult(name=name, success=False, error=f"git fetch failed: {err}")

        log(f"[{name}] Resetting to origin/{branch}…")
        rc, _, err = _run_git(["reset", "--hard", f"origin/{branch}"], cwd=local_path, git_exe=git_exe)
        if rc != 0:
            return GitSyncResult(name=name, success=False, error=f"git reset failed: {err}")

        rc, _, err = _run_git(["clean", "-fd"], cwd=local_path, git_exe=git_exe)
        if rc != 0:
            log(f"[{name}] Warning: git clean failed: {err}")
    else:
        log(f"[{name}] Cloning {url}…")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        rc, _, err = _run_git(["clone", "--branch", branch, url, str(local_path)], git_exe=git_exe)
        if rc != 0:
            return GitSyncResult(name=name, success=False, error=f"git clone failed: {err}")

    commit = _get_commit(local_path, git_exe)
    log(f"[{name}] Synced. Commit: {commit or 'unknown'}")
    return GitSyncResult(name=name, success=True, commit=commit)


def sync_all_repositories(repos: list[dict], sources_dir: Path,
                           git_exe: str = "git",
                           log: Optional[Callable[[str], None]] = None) -> list[GitSyncResult]:
    results = []
    for repo in repos:
        name = repo.get("name", "unknown")
        url = repo.get("url", "")
        branch = repo.get("branch", "main")
        local_path = Path(repo.get("local_path", str(sources_dir / "gitlab" / name)))
        result = sync_repository(name=name, url=url, branch=branch,
                                 local_path=local_path, git_exe=git_exe, log=log)
        results.append(result)
    return results
