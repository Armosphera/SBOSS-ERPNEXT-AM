# Commit message pitfalls (lessons from the A1 portfolio)

When writing commit messages in shell, three things bite you:

## 1. Backticks get shell-interpreted

`git commit -m "feat: \`foo\`" ` will run \`foo\` as a command and substitute the output. Use **single quotes**:

```bash
git commit -m 'feat(am): seed `frappe_armenia` chart of accounts (350 accounts)'
```

Or use a here-doc / `-F`:

```bash
git commit -F- <<'EOF'
feat(am): seed frappe_armenia chart of accounts (350 accounts)

Includes bilingual (HY/EN) account names. Closes #42.
EOF
```

## 2. `$HOME` expands in double-quoted strings

```bash
# BAD — $HOME expands:
git commit -m "chore: clean $HOME/.cache/bench"

# GOOD — single-quote:
git commit -m 'chore: clean $HOME/.cache/bench'
```

## 3. `$(gh auth token)` in push URL gets re-evaluated

```bash
# BAD — every shell eval re-runs gh auth token:
git push https://x-access-token:$(gh auth token)@github.com/armosphera/SBOSS-ERPNEXT-AM.git

# GOOD — use gh's own credential helper:
gh auth setup-git   # one-time
git push            # uses the credential helper, not literal URL
```

## Lint rule

CI runs `commitlint` (see `ci/github-actions/lint.yml`) with a custom rule
that fails any commit message containing unescaped backticks in the subject
line. Single-quoted messages are safe.

## Verify before push

```bash
git log -1 --pretty=%B | grep -E '`' && echo "WARNING: backticks in subject" || echo "OK"
```
