---
name: feedback-tests-for-every-change
description: Every new feature or code change must include corresponding tests, not added later
metadata:
  type: feedback
---

Every new feature or code change must include corresponding tests in the same PR/commit — not deferred to a later commit.

**Why:** User standard. Tests are a first-class deliverable alongside the code.

**How to apply:** When reviewing PRs or suggesting changes, flag any feature code that lacks accompanying tests as a blocker, not a suggestion.
