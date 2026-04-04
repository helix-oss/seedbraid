---
name: plan2doc
description: >-
  Create an implementation plan via planner agent and save to .docs/plans/.
  Use when planning a feature, refactoring, or significant change.
context: fork
agent: planner
argument-hint: "<feature or change to plan>"
---

Create an implementation plan for: $ARGUMENTS

Current changes:
!`git diff --stat`

Existing research (if any):
!`ls -t .docs/research/*.md 2>/dev/null | head -5`

## Instructions

1. If existing research files are listed above, read them to build on prior findings
2. Identify dependencies, affected files, risks, and implementation order
3. Read `.docs/templates/workflow-patterns.md` if it exists (skip if missing)
4. Scan `.claude/agents/` and `.claude/skills/` frontmatter only (not full file contents) to identify available tools
5. Write the full plan to `.docs/plans/{feature}.md` including:
   - Overview and goals
   - Affected files and components
   - Step-by-step implementation plan (numbered)
   - Risk assessment and testing strategy
   - `### Claude Code Workflow` section with phase/command/agent table
6. Return a summary with the plan file path

## Error Handling

- **Empty arguments**: Print "Usage: /plan2doc <feature or change to plan>" and stop.
- **Missing .docs/ directories**: Create `.docs/plans/` automatically.
- **Missing workflow-patterns.md**: Skip the workflow pattern selection step; generate the Claude Code Workflow section from available skills/agents directly.
