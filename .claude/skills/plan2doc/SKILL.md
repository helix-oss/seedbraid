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

## Instructions

1. Analyze the feature/change request and explore relevant code
2. Identify dependencies, affected files, risks, and implementation order
3. Read `.docs/templates/workflow-patterns.md` to understand available workflow patterns
4. Read `.claude/agents/` and `.claude/skills/` to identify available tools
5. Write the full plan to `.docs/plans/{feature}.md` including:
   - Overview and goals
   - Affected files and components
   - Step-by-step implementation plan (numbered)
   - Risk assessment and testing strategy
   - `### Claude Code Workflow` section with phase/command/agent table
6. Return a summary with the plan file path
7. Recommend: "Start a new session with /catchup for implementation"
