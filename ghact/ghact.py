#!/usr/bin/env python3
"""ghact — schedule GitHub Actions to run later.

Usage:
  ghact [--at TIME | --after DURATION] [--if CONDITION] [--repo OWNER/REPO]
        <command> <PR> [args...]

See idea.md for full documentation.
"""

import argparse
import sys
from datetime import datetime

import actions
import conditions
import timing


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

    # ── Subcommands ───────────────────────────────────────────────────────────
    sub = parser.add_subparsers(dest='command', metavar='command')
    sub.required = True

    p = sub.add_parser('add-label', help='Add a label to a PR')
    p.add_argument('pr', type=int, metavar='PR')
    p.add_argument('label', metavar='LABEL')

    p = sub.add_parser('remove-label', help='Remove a label from a PR')
    p.add_argument('pr', type=int, metavar='PR')
    p.add_argument('label', metavar='LABEL')

    p = sub.add_parser('add-comment', help='Add a comment to a PR')
    p.add_argument('pr', type=int, metavar='PR')
    p.add_argument('body', metavar='BODY')

    p = sub.add_parser('merge', help='Merge a PR')
    p.add_argument('pr', type=int, metavar='PR')

    p = sub.add_parser('close', help='Close a PR')
    p.add_argument('pr', type=int, metavar='PR')

    p = sub.add_parser('pr', help='Check --if condition; exit 0 if true, 1 if false')
    p.add_argument('pr', type=int, metavar='PR')

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

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
    pr = args.pr
    if args.command == 'pr':
        if not args.condition:
            parser.error("'pr' command requires --if CONDITION")
        try:
            met = conditions.check_conditions(args.condition, pr, args.repo)
        except ValueError as e:
            parser.error(str(e))
        except RuntimeError:
            sys.exit(1)
        sys.exit(0 if met else 1)

    # ── Check condition ───────────────────────────────────────────────────────
    if args.condition:
        try:
            met = conditions.check_conditions(args.condition, pr, args.repo)
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
            actions.add_label(pr, args.label, args.repo)
        elif args.command == 'remove-label':
            actions.remove_label(pr, args.label, args.repo)
        elif args.command == 'add-comment':
            actions.add_comment(pr, args.body, args.repo)
        elif args.command == 'merge':
            actions.merge(pr, args.repo)
        elif args.command == 'close':
            actions.close(pr, args.repo)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
