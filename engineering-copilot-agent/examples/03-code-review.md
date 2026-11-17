# Example 3 - Review code

**Concept:** the `code-review` skill defines a checklist and a finding format.
The agent uses the tool several times: to check what the path is, to read the
code and to read its tests. Findings are separated into **verified**,
**potential** and **suggestions**.

## Run it

```bash
engineering-agent review sample_project/calculator.py
```

## Trace

```text
 1. Received request.
 2. Classified intent as code review.
 3. Selected code-review skill.
 4. Loaded instructions from skills/code-review/SKILL.md.
 5. Selected inspect_project.file_info.
 6. Validated requested path and collected file metadata.
 7. Selected inspect_project.read_file.
 8. Validated requested path.
 9. Read file successfully.
10. Selected inspect_project.read_file.
11. Validated requested path.
12. Read file successfully.
13. Applied the code-review checklist: correctness, error handling, readability, tests, security and edge cases.
14. Prioritized findings: verified first, then by severity.
15. Produced educational response (no files were modified).
```

Steps 7-9 read `calculator.py`. Steps 10-12 read `test_calculator.py`.
A good reviewer looks at the tests too.

## Shape of the response

```markdown
# Code review

## Summary
Reviewed 1 file(s): ...
Found N verified finding(s), N potential concern(s) and N suggestion(s). Highest severity: ...
No files were modified.

## Verified Findings
### 1. [SEVERITY] Category - file, line N
- Observation: ...
- Why it matters: ...
- Suggested improvement: ...

## Potential Concerns
...
## Suggestions
...
## Limitations
...
```

The actual findings are left for you to discover. Run the command!

## Discuss

1. Pick the HIGH finding. Do you agree it is a defect? What should the code do instead?
2. Pick a potential concern. Why is it *potential* and not *verified*?
3. The tests pass. Why can there still be verified findings?

## Try next

```bash
engineering-agent review sample_project              # review a whole folder
engineering-agent ask "find potential issues in sample_project/calculator.py"
engineering-agent review sample_project/calculator.py --json
```

In the JSON output, `observation` holds the main file read, and
`supporting_observations` holds the other tool calls.
