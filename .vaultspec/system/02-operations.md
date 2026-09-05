---
order: 2
---

# Operations

- **Tool output:** Prefer quiet command output; keep full output only when the result
  cannot be judged without it. Run independent tool calls in parallel. Run commands that
  do not terminate on their own (servers, watchers) in the background.

- **Secrets:** Never write, log, or commit secrets, keys, or credentials.

- **Commits:** Commit after each Step under a plan, and after each cohesive change
  outside one. Pre-commit hooks and lint must pass on the files you touched. Match the
  style of recent commits and write the message for *why*, not *what*. If a commit
  fails, report it; do not work around the hook unasked.

- **Remotes:** Never push, force-push, or open a pull request unless the user asked.
