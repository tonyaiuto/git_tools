"""Action implementations for ghact subcommands."""

import subprocess
import sys


def add_label(pr, label, repo=None):
    """Add a label to a PR."""
    print(f"Adding label {label!r} to PR #{pr}", file=sys.stderr)
    _gh(['pr', 'edit', str(pr), '--add-label', label], repo)


def remove_label(pr, label, repo=None):
    """Remove a label from a PR."""
    print(f"Removing label {label!r} from PR #{pr}", file=sys.stderr)
    _gh(['pr', 'edit', str(pr), '--remove-label', label], repo)


def add_comment(pr, body, repo=None):
    """Add a comment to a PR."""
    print(f"Adding comment to PR #{pr}", file=sys.stderr)
    _gh(['pr', 'comment', str(pr), '--body', body], repo)


def merge(pr, repo=None):
    """Merge a PR."""
    print(f"Merging PR #{pr}", file=sys.stderr)
    _gh(['pr', 'merge', str(pr), '--merge'], repo)


def close(pr, repo=None):
    """Close a PR."""
    print(f"Closing PR #{pr}", file=sys.stderr)
    _gh(['pr', 'close', str(pr)], repo)


def ready(pr, repo=None):
    """Mark a draft PR as ready for review."""
    print(f"Marking PR #{pr} as ready for review", file=sys.stderr)
    _gh(['pr', 'ready', str(pr)], repo)


def run_gh(gh_args, repo=None):
    """Pass args directly to gh, injecting --repo if known. Streams output."""
    cmd = ['gh'] + list(gh_args)
    if repo:
        cmd += ['--repo', repo]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"gh command failed")


# ── gh helper ─────────────────────────────────────────────────────────────────

def _gh(args, repo=None):
    """Run a gh command, streaming its output. Raises RuntimeError on failure."""
    cmd = ['gh'] + args
    if repo:
        cmd += ['--repo', repo]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gh command failed: {' '.join(cmd)}")
