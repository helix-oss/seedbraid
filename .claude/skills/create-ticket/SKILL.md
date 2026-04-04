---
name: create-ticket
description: >-
  Create a structured refactoring ticket with scope analysis, acceptance
  criteria, and Claude Code workflow recommendations. Use when defining
  new work items or breaking down features into tickets.
allowed-tools:
  - Agent
  - Read
  - Glob
  - Grep
  - Write
  - Edit
  - AskUserQuestion
argument-hint: "<ticket description>"
---

# /create-ticket

Ticket description: $ARGUMENTS

## Instructions

Generate a structured refactoring ticket from the given ticket description.

### Phase 1: Investigation (researcher agent)

Use the researcher agent to investigate:

1. Source code related to the ticket description (`src/seedbraid/`, `tests/`)
2. Affected files and line ranges
3. Existing test coverage
4. Related documentation (`docs/`)
5. Dependencies (relationships with other tickets)

### Phase 2: Planning (planner agent)

Use the planner agent to design:

1. Ticket structure (Background, Scope, Acceptance Criteria, Implementation Notes)
2. Appropriate category (Security / CodeQuality / Doc / DevOps / Community) and size (S/M/L/XL)
3. Workflow recommendations based on category x size, referencing `references/workflow-patterns.md`

### Phase 3: Ticket output

Read `references/ticket-template.md` for the output format.

### Workflow selection guide

Read available skills and agents from `.claude/skills/` and `.claude/agents/`,
and reference patterns in `references/workflow-patterns.md` to design the workflow.

**Category-specific guidelines**:
- **Security**: Wrap with `/security-scan` before and after. Spec-first with documentation leading.
- **CodeQuality**: Use `/refactor` skill. Guarantee no behavior changes.
- **Doc**: Use doc-writer agent.
- **DevOps**: CI/CD configs are hard to test; design carefully with `/plan2doc`.
- **Community**: Reference industry-standard templates.

**Size-specific guidelines**:
- **S**: `/plan2doc` optional. Direct implementation.
- **M**: `/plan2doc` recommended.
- **L/XL**: `/plan2doc` required. Incremental implementation recommended.
