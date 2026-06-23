"""Commit the docs/ folder and push it to GitHub (where Pages serves it).

Usage:  python -m skautcast.publish ["commit message"]
"""
import subprocess
import sys

from . import config


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=config.ROOT,
                          capture_output=True, text=True)


def publish(message: str) -> int:
    if not (config.ROOT / ".git").exists():
        print("No git repository here yet. One-time setup:")
        print("  git init && git add . && git commit -m 'init'")
        print("  git branch -M main")
        print("  git remote add origin <your-repo-url>")
        print("  git push -u origin main")
        print("Then enable Pages: Settings -> Pages -> source = main / /docs")
        return 1

    _git("add", "docs", "data/state.json", "data/summaries")
    if _git("diff", "--cached", "--quiet").returncode == 0:
        print("[publish] nothing to publish.")
        return 0

    cm = _git("commit", "-m", message)
    if cm.returncode != 0:
        print(cm.stdout, cm.stderr)
        return 1
    push = _git("push")
    print(push.stdout or push.stderr)
    if push.returncode != 0:
        return 1
    print(f"[publish] pushed. Feed: {config.BASE_URL}/feed.xml")
    return 0


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "feed: update episodes"
    raise SystemExit(publish(msg))
