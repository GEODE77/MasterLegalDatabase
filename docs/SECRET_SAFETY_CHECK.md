# Secret Safety Check

Project Geode uses a small safety check before future download commits and pushes.

The check scans staged text files for likely API keys, tokens, passwords, bearer tokens, and secret-looking values near words like `api_key`, `token`, or `secret`.

It is meant to stop accidental leaks before data refresh work reaches GitHub.

## How It Runs

The repository includes local Git hooks in `.githooks/`:

- `pre-commit`
- `pre-push`

Turn them on once per local checkout:

```bash
git config core.hooksPath .githooks
```

After that, Git automatically runs the safety check before commit and before push.

## Manual Check

You can also run it directly:

```bash
python -m geode.validation.secret_safety --staged
```

If the check finds a possible secret, remove the value from the file, use an environment variable instead, and stage the corrected file again.

## Boundary

This is a safety net, not a guarantee. It reduces the chance of leaking API keys, but reviewers should still avoid placing credentials in files, command logs, dashboards, reports, screenshots, or source archives.
