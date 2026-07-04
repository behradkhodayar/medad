---
name: review-diff
description: Review the uncommitted working-tree changes for bugs and cleanups.
---

# Review the working-tree diff

Review the current uncommitted changes like a careful teammate.

1. Run `git diff` (and `git diff --cached` if there are staged changes) to
   collect the full diff. Read any changed file whose surrounding context you
   need to judge the change.
2. Look for, in priority order:
   - correctness bugs: wrong logic, unhandled edge cases, broken error paths
   - security issues: injection, unvalidated input, secrets in code
   - simpler ways to do the same thing with code that already exists in the repo
   - missing test coverage for changed behavior
3. Report findings as a list, most severe first. For each: the file and line,
   one sentence on what is wrong, and a concrete failure scenario. If the diff
   is clean, say so plainly — do not invent findings.
4. Do not change any files; this skill only reports.
