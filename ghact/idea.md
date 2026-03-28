# ghact — Schedule GitHub Actions to Run Later

A command-line tool that sleeps until a specified time, checks a condition on a PR,
and then performs an action. Uses the `gh` CLI for all GitHub interactions.

## Command Syntax

```
ghact [--at TIME | --after DURATION] [--if CONDITION] [--repo OWNER/REPO]
      <command> <PR> [args...]
```

## Global Options

| Flag | Example | Description |
|---|---|---|
| `--at TIME` | `0300`, `14:30`, `2:30am` | Sleep until this wall-clock time (tomorrow if already past) |
| `--after DURATION` | `2h`, `90m`, `1h30m` | Sleep for this duration from now |
| `--if CONDITION` | `approved`, `unapproved` | Only act if the PR satisfies this condition |
| `--repo OWNER/REPO` | `bazelbuild/bazel` | GitHub repo (default: current directory's repo) |

`--at` and `--after` are mutually exclusive. All global options are optional.

## Conditions (`--if`)

| Condition | Meaning |
|---|---|
| `approved` | PR has an approving review and no blocking changes-requested |
| `unapproved` | PR has not been approved |
| `ci-passing` | All required status checks are green |
| `ci-failing` | At least one required status check is not green |
| `draft` | PR is in draft state |
| `ready` | PR is not a draft |
| `mergeable` | PR is approved and CI is passing |

If `--if` is specified and the condition is **not** met, a message is printed to
stderr and the tool exits 0 (condition unmet is not an error).

## Commands

| Command | Args | Description |
|---|---|---|
| `add-label` | `<PR> <label>` | Add a label to a PR |
| `remove-label` | `<PR> <label>` | Remove a label from a PR |
| `add-comment` | `<PR> <body>` | Add a comment to a PR |
| `merge` | `<PR>` | Merge a PR |
| `close` | `<PR>` | Close a PR |

## Examples

```bash
# At 3am, if PR #42 is not approved, add a "needs-review" label
ghact --at 0300 --if unapproved add-label 42 "needs-review"

# At 3am, if PR #42 is approved, post a /merge comment
ghact --at 0300 --if approved add-comment 42 "/merge"

# In 2 hours, add a label regardless of approval state
ghact --after 2h add-label 42 "night-build"

# Right now, if approved, merge
ghact --if approved merge 42

# In a specific repo, after 90 minutes, add a comment
ghact --after 90m --repo bazelbuild/bazel add-comment 123 "Triggered nightly run"
```
