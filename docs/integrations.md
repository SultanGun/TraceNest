# Agent Integrations

TraceNest provides a modular adapter architecture to connect with AI coding agents and autonomous toolchains.

---

## OpenCode Adapter

### Overview
TraceNest includes an adapter for [OpenCode](https://github.com/opencode-ai/opencode) agent workflows.

### What TraceNest Observes
- Working tree files added, modified, deleted, or renamed during an OpenCode session.
- Credential leaks or suspicious patterns introduced into codebase files.
- Scope boundary compliance.
- Baseline snapshots taken prior to agent task invocation.

### What TraceNest Cannot Observe
- In-memory agent thoughts, prompts, or intermediate streaming reasoning.
- Terminal commands executed that did not alter the repository filesystem.
- Ephemeral network requests made by the agent.

### Integration Workflow

```bash
# 1. Take a baseline snapshot before running OpenCode
tracenest snapshot create --label "opencode-task-start"

# 2. Run OpenCode on your task
opencode "Implement JWT token refresh endpoint in auth.py"

# 3. Review what OpenCode changed
tracenest review
```

---

## General Agent Workflow (Claude Code, Cursor, Cline, Codex)

TraceNest is agent-agnostic and functions with any AI tool modifying local files:

1. `tracenest snapshot create` before launching your agent.
2. Allow your agent to make edits.
3. Run `tracenest review` to audit the diff and verify security rules before staging or committing.
