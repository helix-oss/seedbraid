# Release Workflow (Phase 0-6)

## Phase 0: Preflight

1. Run `gh auth status` to verify authentication. If not authenticated, tell the user to run `gh auth login` and stop immediately.

## Phase 1: Determine Tag and Revision

2. If `rev=` is NOT specified, use HEAD of the default branch.
3. If `tag=` is NOT specified:
   a. Read the version file to get the current version.
   b. Analyze commits since the last tag. Categorize by commit convention type.
   c. Propose 2-3 version candidates with reasoning based on the versioning scheme and changes found.
   d. Present the candidates to the user and wait for selection or custom input.
   e. The user's response becomes the tag. Ensure `v` prefix for git tags, strip `v` for version strings in code.

## Phase 2: Update Version and Changelog

4. Update the version file with the new version string (without `v` prefix).
5. Update the changelog:
   a. Create a new section below the unreleased header with the new version and today's date.
   b. Categorize commits into appropriate subsections (Added, Changed, Fixed, etc.).
   c. Update comparison URLs at the bottom of the file.

## Phase 3: Verify

6. Run the lint command. If it fails, fix the issue before proceeding.
7. Run the test command. If it fails, fix the issue before proceeding.

## Phase 4: Commit, PR, and Merge

8. Create a release branch: `git checkout -b release/<TAG>`
9. Stage and commit the changed files with message: `chore: bump version to <VERSION>`.
10. Push, create PR to the default branch, wait for CI, and squash-merge. Follow the same flow as /create-pr-with-merge: push unpushed commits, create PR with title `chore: release <TAG>`, wait for CI checks, then merge using the project's merge strategy. On CI failure or merge conflict, stop and report (do NOT force-merge, keep the PR open).

## Phase 5: Tag and Release

11. Sync local default branch: `git checkout <default-branch> && git pull --rebase origin <default-branch>`
12. Create an annotated tag: `git tag -a <TAG> -m "Release <TAG>"` on the target revision.
13. Push the tag: `git push origin <TAG>`
14. Monitor the release workflow: `gh run list --limit 1` then `gh run watch <RUN_ID>`
15. If the publish job fails but build succeeds, inform the user that publishing may not be configured. Proceed to step 16.
16. If the release job is skipped or fails, create a GitHub Release manually with `gh release create`. Add `--prerelease` flag if the version is a pre-release. Generate notes from the changelog section for this version.

## Phase 6: Report

17. Print a summary: release tag and version, GitHub Release URL, publish status (success / failed / skipped), and list of included changes.

## Error Handling

- **gh auth failure**: Tell the user to run `gh auth login` and stop.
- **Protected branch push rejected**: This is expected. Use the PR-based flow in Phase 4.
- **CI check failure**: Show the failing check and stop. Do NOT force-merge.
- **Tag already exists**: Inform the user and stop. Do NOT delete existing tags without explicit confirmation.
- **No changes since last tag**: Warn the user. Ask whether to proceed.
- **Merge conflict**: Show the conflict and stop. Do NOT auto-resolve.
