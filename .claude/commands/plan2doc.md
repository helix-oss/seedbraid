---
description: "Create an implementation plan and save to .docs/plans/"
argument-hint: "<feature or change to plan>"
---

Create an implementation plan for: $ARGUMENTS

Current changes:
!`git diff --stat`

## Instructions

1. Spawn the **planner** agent to create a detailed plan
2. Do NOT read files directly — delegate ALL planning to the agent
3. The planner will save the plan to `.docs/plans/`
4. Report the plan summary and file path to the user
5. Recommend: "Start a new session with /catchup for implementation"
