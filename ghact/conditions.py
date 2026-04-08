"""Condition evaluation for ghact --if flag."""

import json
import subprocess


KNOWN_CONDITIONS = frozenset({
    'approved',
    'unapproved',
    'passing',
    'failing',
    'draft',
    'ready',
    'mergeable',
})


def check_condition(condition, pr, repo=None):
    """Return True if PR satisfies condition, False otherwise.

    Raises ValueError for unknown conditions.
    Raises RuntimeError if the gh CLI call fails.
    """
    if condition == 'approved':
        return _is_approved(pr, repo)
    elif condition == 'unapproved':
        return not _is_approved(pr, repo)
    elif condition == 'passing':
        return _is_ci_passing(pr, repo)
    elif condition == 'failing':
        return not _is_ci_passing(pr, repo)
    elif condition == 'draft':
        return _is_draft(pr, repo)
    elif condition == 'ready':
        return not _is_draft(pr, repo)
    elif condition == 'mergeable':
        return _is_approved(pr, repo) and _is_ci_passing(pr, repo)
    else:
        raise ValueError(
            f"Unknown condition {condition!r}. "
            f"Known conditions: {', '.join(sorted(KNOWN_CONDITIONS))}"
        )


# ── gh helpers ────────────────────────────────────────────────────────────────

def _gh(args, repo=None):
    """Run a gh command and return parsed JSON. Raises RuntimeError on failure."""
    cmd = ['gh'] + args
    if repo:
        cmd += ['--repo', repo]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"gh command failed ({' '.join(cmd)}):\n{result.stderr.strip()}"
        )
    return json.loads(result.stdout)


def _is_approved(pr, repo):
    data = _gh(['pr', 'view', str(pr), '--json', 'reviewDecision'], repo)
    return data.get('reviewDecision') == 'APPROVED'


def _is_ci_passing(pr, repo):
    data = _gh(['pr', 'view', str(pr), '--json', 'statusCheckRollup'], repo)
    checks = data.get('statusCheckRollup') or []
    if not checks:
        return False
    # GitHub uses 'conclusion' for Actions runs and 'state' for commit statuses.
    passing = {'SUCCESS', 'SKIPPED', 'NEUTRAL'}
    return all(
        c.get('conclusion') in passing or c.get('state') == 'SUCCESS'
        for c in checks
    )


def _is_draft(pr, repo):
    data = _gh(['pr', 'view', str(pr), '--json', 'isDraft'], repo)
    return bool(data.get('isDraft'))
