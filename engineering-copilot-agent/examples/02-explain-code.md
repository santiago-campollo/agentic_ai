# Example 2 - Explain code with a skill

**Concept:** a *skill* is a reusable procedure. The `explain-code` skill tells
the agent which steps to follow and which sections the answer must have. The
tool reads the file; the skill shapes the explanation.

## Run it

```bash
engineering-agent explain sample_project/calculator.py --level beginner
```

## Trace

```text
 1. Received request.
 2. Classified intent as code explanation.
 3. Selected explain-code skill.
 4. Loaded instructions from skills/explain-code/SKILL.md.
 5. Selected inspect_project.read_file.
 6. Validated requested path.
 7. Read file successfully.
 8. Parsed the source with ast (the code was not executed).
 9. Applied the explain-code response structure (7 sections, beginner level).
10. Produced educational response.
```

## Response (excerpt)

```markdown
## Example

    # Make the function available (run Python from the folder with calculator.py).
    from calculator import calculate

    # Call the function with sample inputs and keep the result.
    result = calculate('add', 6, 3)
    print(result)

The agent never runs code, so the output is not shown. Try it yourself and
compare with what you expect.
```

## What to notice

1. The section names come from `## Response Sections` in
   `skills/explain-code/SKILL.md`, not from Python code.
2. Step 8: the agent *parses* Python with `ast`. It never executes it.
3. The example uses a real function and a real operation name (`'add'`) found
   in the file. The skill says: do not invent.

## Compare levels

```bash
engineering-agent explain sample_project/calculator.py --level intermediate
engineering-agent explain sample_project/calculator.py --level advanced
```

`advanced` shows signatures, line ranges, branch counts and call relationships.

## Experiment

Swap two lines under `## Response Sections` in `skills/explain-code/SKILL.md`
and run the command again. The order of the answer changes. Then add a line
`- Fun Fact` and run it again: the agent says it has no generator for that
section instead of making something up. Undo your changes when you finish.
