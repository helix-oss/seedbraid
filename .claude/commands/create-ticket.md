---
allowed-tools: Agent, Read, Glob, Grep, Write, Edit, AskUserQuestion
description: "Create a new refactoring ticket with Claude Code workflow recommendations"
---

# /create-ticket

Ticket description: $ARGUMENTS

## Instructions

Generate a structured refactoring ticket from the given ticket description.

### Phase 1: Investigation (researcher agent)

Use the researcher agent to investigate:

1. Source code related to the ticket description (`src/helix/`, `tests/`)
2. Affected files and line ranges
3. Existing test coverage
4. Related documentation (`docs/`)
5. Dependencies (relationships with other tickets)

### Phase 2: Planning (planner agent)

Use the planner agent to design:

1. Ticket structure (Background, Scope, Acceptance Criteria, Implementation Notes)
2. Appropriate category (Security / CodeQuality / Doc / DevOps / Community) and size (S/M/L/XL)
3. Workflow recommendations based on category x size, referencing `.docs/templates/workflow-patterns.md`

### Phase 3: Ticket output

Generate the ticket in the following format and present it to the user:

```markdown
## T-NNN: [Title]

| Field | Value |
|-------|-------|
| Priority | **P?** |
| Category | [Category] |
| Size | [S/M/L/XL] |
| Dependencies | [Dependent tickets or —] |

### Background

[Problem description and rationale]

### Scope

| File | Lines | Change |
|------|-------|--------|
| ... | ... | ... |

### Acceptance Criteria

1. ...
2. ...

### Implementation Notes

- ...

### Claude Code Workflow

| Phase | Command / Agent | Purpose |
|-------|----------------|---------|
| 1. ... | ... | ... |

**Example execution**:
```
[Command flow]
```
```

### Workflow selection guide

Read available commands and agents from `.claude/commands/` and `.claude/agents/`,
and reference patterns in `.docs/templates/workflow-patterns.md` to design the workflow.

**Category-specific guidelines**:
- **Security**: Wrap with `/security-scan` before and after. Spec-first with documentation leading.
- **CodeQuality**: Use `/refactor` command. Guarantee no behavior changes.
- **Doc**: Use doc-writer agent.
- **DevOps**: CI/CD configs are hard to test; design carefully with `/plan`.
- **Community**: Reference industry-standard templates.

**Size-specific guidelines**:
- **S**: `/plan` optional. Direct implementation.
- **M**: `/plan` recommended.
- **L/XL**: `/plan` required. Incremental implementation recommended.
