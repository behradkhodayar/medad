---
name: commit-message
description: Write a commit message for the currently staged changes.
---

# Commit message

Write a commit message for the staged changes, then commit.

1. Run `git diff --cached --stat` and `git diff --cached` to see exactly what
   is staged. If nothing is staged, say so and stop — do not stage anything
   yourself.
2. Summarize the change in one imperative-mood subject line of at most 70
   characters: what the change does, not what you did ("Add retry to the
   fetch loop", not "Added retries").
3. If the why is not obvious from the subject, add a blank line and a short
   body paragraph explaining the motivation. No emojis, no co-author lines.
4. Show the message and run `git commit` with it.
