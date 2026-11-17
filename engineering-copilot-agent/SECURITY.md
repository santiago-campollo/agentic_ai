# Security Policy

This project is used in classrooms. Its safety boundaries are part of what it
teaches, so please keep them intact.

## What the agent can and cannot do

| The agent **can** | The agent **cannot** |
|---|---|
| List files and folders inside the workspace root | Read anything outside the workspace root |
| Read UTF-8 text files up to 100 KB | Read binary files or very large files |
| Return file metadata | Write, modify, move or delete files |
| Parse Python with `ast` (no execution) | Execute inspected code |
| | Run shell or system commands |
| | Read `.env` files, private keys or credential files |
| | Call external services or require API keys |

## How the boundaries are enforced

- **Read-only tool.** `tools/inspect_project.py` only has `tree`, `read_file`
  and `file_info` operations. None of them write anything.
- **Path validation.** Every path is resolved with `Path.resolve()` (which
  collapses `..` and follows symbolic links) and must stay inside the root.
  Attempts such as `../secret.txt` return `PATH_OUTSIDE_ROOT`.
- **Sensitive-file denylist.** `.env*`, `.git/`, `.ssh/`, `.aws/`, `id_rsa`,
  `*.pem`, `*.key`, `credentials.json`, `secrets.*` and similar files return
  `SENSITIVE_FILE` and are hidden from `tree`.
- **Size and type limits.** Files over 100 KB return `FILE_TOO_LARGE`; binary or
  non-UTF-8 files return `BINARY_FILE`.
- **No code execution.** Python files are parsed with `ast.parse`, which builds a
  syntax tree without running the code. The project does not use `eval`,
  `exec`, `pickle`, `subprocess` or `shell=True`.

## Rules for contributors and students

- Never commit secrets: tokens, passwords, API keys, private keys or `.env` files.
  `.gitignore` already excludes common secret files; do not remove those lines.
- Do not add realistic-looking example tokens to code, tests or docs. Use
  obvious placeholders such as `placeholder`.
- Do not add write or execute operations to `inspect_project`. If you need new
  capabilities, create a separate tool and discuss its risks in your pull request.
- If you accidentally push a secret, **revoke it immediately** with the provider,
  then remove it from the repository history. Deleting the file is not enough.

## Reporting a security problem

If you find a way to bypass these boundaries (for example, reading a file
outside the workspace):

1. **Do not** open a public issue with exploit details.
2. Contact the repository maintainers privately. On GitHub, use
   **Security -> Report a vulnerability** if private vulnerability reporting is enabled.
   Otherwise, contact your instructor directly.
3. Include the command you ran, the expected behavior, the actual behavior and
   your operating system.

We will acknowledge the report, fix the issue and add a regression test.
