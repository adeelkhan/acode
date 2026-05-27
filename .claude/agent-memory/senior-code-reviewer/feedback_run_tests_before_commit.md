---
name: feedback-run-tests-before-commit
description: Always run pytest -v before committing; catches regressions on all changes including CSS
metadata:
  type: feedback
---

Always run `pytest -v` before committing.

**Why:** User explicitly requires this. Regressions have been caught before on all kinds of changes including CSS.

**How to apply:** Before any commit recommendation or after any code change, remind user to run tests or run them yourself.
