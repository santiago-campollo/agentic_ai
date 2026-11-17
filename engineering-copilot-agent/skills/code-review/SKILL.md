---
name: code-review
description: Review a file or project for correctness, error handling, readability, tests, security and edge cases, with prioritized findings.
---

# Skill: Code Review

Use this skill when someone asks to review code, find potential issues, or
check quality before a pull request. The skill defines **how** to review. The
agent still needs a tool (`inspect_project`) to observe the files.

## When to use

- "Review `sample_project/calculator.py`."
- "Find potential issues in this project."
- "Is this code ready for a pull request?"

## Procedure

1. **Understand the purpose first.** Read the file and, if it exists, its test
   file (`test_<name>.py` next to it or in `tests/`).
2. **Correctness.** Does the code return the right result for every input?
3. **Error handling.** Are errors raised with specific types and helpful
   messages? Are any errors silently swallowed or hidden behind fake values?
4. **Readability and maintainability.** Clear names, single responsibility,
   docstrings, type hints, no unnecessary complexity.
5. **Tests.** Is every public function tested? Are error paths and edge cases
   tested?
6. **Security basics.** No `eval`/`exec`, no `shell=True`, no secrets in code,
   no reading of untrusted paths without validation.
7. **Edge cases.** Zero, negative numbers, empty input, very large values,
   unexpected types.
8. **Prioritize.** Verified findings first, then by severity.
9. **Propose concrete improvements** for every finding.
10. **Do not modify files** unless the user explicitly asks for it.

## Finding format

Every finding must include:

- **Severity:** `LOW`, `MEDIUM` or `HIGH`.
- **Category:** for example Correctness, Error handling, Readability,
  Maintainability, Testing, Security, Edge cases.
- **File.**
- **Line** or approximate section when possible.
- **Observation:** what you saw.
- **Why it matters:** the consequence.
- **Suggested improvement:** a concrete next step.

## Verified vs. potential vs. suggestion

- **Verified findings:** directly observable in the files you read (for
  example "returns `0` when `b == 0`").
- **Potential concerns:** plausible risks that depend on context or intent.
  Phrase them as questions or risks, not as confirmed bugs.
- **Suggestions:** optional improvements that are not defects.

Never present an assumption as a confirmed defect.

## Response Sections

- Summary
- Verified Findings
- Potential Concerns
- Suggestions
- Limitations

## Quality checklist

- The summary comes first and states how many findings of each kind exist.
- Every finding points to a real file and, when possible, a line.
- No file was modified.
