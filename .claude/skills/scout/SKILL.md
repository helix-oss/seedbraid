---
name: scout
description: >-
  Investigate codebase and create an implementation plan by chaining
  /investigate (researcher, sonnet) and /plan2doc (planner, opus).
  Use when you need both research and planning for a feature or ticket.
disable-model-invocation: true
allowed-tools:
  - Skill
argument-hint: "<topic or ticket to investigate and plan>"
---

Investigate and plan: $ARGUMENTS

## Instructions

1. Call `/investigate` with the topic to run codebase research via the researcher agent (sonnet).
2. If investigate returns a failure status, print the error and stop.
3. Print the research summary and file path returned by investigate.
4. Call `/plan2doc` with the same topic to create an implementation plan via the planner agent (opus). The planner will read the research output from `.docs/research/` automatically.
5. Print the plan summary and file path returned by plan2doc.
6. Print a final summary with both file paths.

## Error Handling

- **Empty arguments**: Print "Usage: /scout <topic or ticket>" and stop.
- **investigate failure**: Print the error, do NOT proceed to plan2doc.
- **plan2doc failure**: Print the error and the research file path (research is still valid).
