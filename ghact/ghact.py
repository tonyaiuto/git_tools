#!/usr/bin/env python3
"""ghact — schedule GitHub Actions to run later.

Usage:
  ghact [--at TIME | --after DURATION] [--if CONDITION] [--repo OWNER/REPO]
        <PR> <command> [args...]

PR may be a number or a full GitHub PR URL (https://github.com/owner/repo/pull/N).
When a URL is given the embedded repo is used unless --repo overrides it.

See idea.md for full documentation.
"""

import argparse
import re
import sys
from datetime import datetime

import actions
import conditions
import timing
import version


_GH_PR_URL = re.compile(r'https://github\.com/([^/]+)/([^/]+)/pull/(\d+)')


def _parse_pr_ref(s, repo_override):
    """Return (pr_number: int, repo: str | None) from a number string or URL."""
    m = _GH_PR_URL.fullmatch(s)
    if m:
        owner, name, num = m.groups()
        return int(num), repo_override or f"{owner}/{name}"
    try:
        return int(s), repo_override
    except ValueError:
        return None, None


def build_parser():
    parser = argparse.ArgumentParser(
        prog='ghact',
        description='Schedule a GitHub action to run at a future time.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── Global options ────────────────────────────────────────────────────────
    when = parser.add_mutually_exclusive_group()
    when.add_argument(
        '--at', metavar='TIME',
        help='Run at a specific time: 0300, 14:30, 2:30am',
    )
    when.add_argument(
        '--after', metavar='DURATION',
        help='Run after a delay: 2h, 90m, 1h30m',
    )
    parser.add_argument(
        '--if', dest='condition', metavar='CONDITION[,CONDITION...]',
        help='Only act if all conditions are met: ' + ', '.join(sorted(conditions.KNOWN_CONDITIONS)),
    )
    parser.add_argument(
        '--repo', metavar='OWNER/REPO',
        help='GitHub repository (default: repo in current directory)',
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='Print status messages (e.g. sleep notifications)',
    )
    parser.add_argument(
        '--version', action='version', version='%(prog)s ' + version.VERSION,
    )

    # ── PR positional ─────────────────────────────────────────────────────────
    parser.add_argument(
        'pr', metavar='PR',
        help='PR number or GitHub PR URL',
    )

    # ── Subcommands ───────────────────────────────────────────────────────────
    sub = parser.add_subparsers(dest='command', metavar='command')
    sub.required = True

    p = sub.add_parser('add-label', help='Add a label to a PR')
    p.add_argument('label', metavar='LABEL')

    p = sub.add_parser('remove-label', help='Remove a label from a PR')
    p.add_argument('label', metavar='LABEL')

    p = sub.add_parser('add-comment', help='Add a comment to a PR')
    p.add_argument('body', metavar='BODY')

    sub.add_parser('merge', help='Merge a PR')
    sub.add_parser('close', help='Close a PR')
    sub.add_parser('ready', help='Mark a draft PR as ready for review')
    sub.add_parser('pr', help='Check --if condition; exit 0 if true, 1 if false')

    p = sub.add_parser('gh', help='Pass args directly to gh (--repo injected if known)')
    p.add_argument('gh_args', nargs=argparse.REMAINDER)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # ── Resolve PR reference ──────────────────────────────────────────────────
    pr, repo = _parse_pr_ref(args.pr, args.repo)
    if pr is None:
        parser.error(f"PR must be a number or GitHub PR URL, got: {args.pr!r}")

    # ── Resolve target time ───────────────────────────────────────────────────
    target_time = None
    if args.at:
        try:
            target_time = timing.parse_at(args.at)
        except ValueError as e:
            parser.error(str(e))
    elif args.after:
        try:
            target_time = datetime.now() + timing.parse_after(args.after)
        except ValueError as e:
            parser.error(str(e))

    if target_time:
        timing.sleep_until(target_time, verbose=args.verbose)

    # ── pr subcommand: check condition, exit 0/1, no output ──────────────────
    if args.command == 'pr':
        if not args.condition:
            parser.error("'pr' command requires --if CONDITION")
        try:
            met = conditions.check_conditions(args.condition, pr, repo)
        except ValueError as e:
            parser.error(str(e))
        except RuntimeError:
            sys.exit(1)
        sys.exit(0 if met else 1)

    # ── Check condition ───────────────────────────────────────────────────────
    if args.condition:
        try:
            met = conditions.check_conditions(args.condition, pr, repo)
        except ValueError as e:
            parser.error(str(e))
        except RuntimeError as e:
            print(f"Error checking condition: {e}", file=sys.stderr)
            sys.exit(1)
        if not met:
            print(
                f"Condition '{args.condition}' not met for PR #{pr} — no action taken.",
                file=sys.stderr,
            )
            return

    # ── Execute action ────────────────────────────────────────────────────────
    try:
        if args.command == 'add-label':
            actions.add_label(pr, args.label, repo)
        elif args.command == 'remove-label':
            actions.remove_label(pr, args.label, repo)
        elif args.command == 'add-comment':
            actions.add_comment(pr, args.body, repo)
        elif args.command == 'merge':
            actions.merge(pr, repo)
        elif args.command == 'close':
            actions.close(pr, repo)
        elif args.command == 'ready':
            actions.ready(pr, repo)
        elif args.command == 'gh':
            actions.run_gh(args.gh_args, repo)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
