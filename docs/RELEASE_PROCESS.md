# Release Process

Use this checklist to publish future `claude-history-explorer` releases.

## Prerequisites

- Clean working tree on `main`.
- GitHub CLI authenticated with permission to push tags and create releases.
- `uv`, Python, Node.js, and npm installed.
- `wrapped-website/node_modules` installed when running bridge tests locally (`cd wrapped-website && npm ci`).
- Optional: PyPI credentials if package publishing is part of the release.

## 1. Choose the version

Follow semantic versioning:
- Patch (`0.2.1`) for bug fixes that do not change public behavior.
- Minor (`0.3.0`) for new features, compatibility improvements, or significant docs/test additions.
- Major (`1.0.0+`) for stable API commitments or breaking changes after 1.0.

Use a leading `v` only for git tags and GitHub releases (`v0.2.0`), not for package metadata (`0.2.0`).

## 2. Update release metadata

Edit:
- `pyproject.toml` → `[project].version`
- `claude_history_explorer/__init__.py` → `__version__`
- `CHANGELOG.md`

In `CHANGELOG.md`:
1. Keep an empty `## [Unreleased]` section at the top.
2. Add `## [X.Y.Z] - YYYY-MM-DD` below it.
3. Move notable changes under `Added`, `Changed`, `Fixed`, `Security`, or other Keep-a-Changelog headings.
4. Update comparison links at the bottom:

```md
[Unreleased]: https://github.com/adewale/claude-history-explorer/compare/vX.Y.Z...HEAD
[X.Y.Z]: https://github.com/adewale/claude-history-explorer/compare/vPREVIOUS...vX.Y.Z
```

For the first historical release, link to the tag tree instead of a compare if there is no earlier tag.

## 3. Validate locally

Run the same checks CI depends on, plus the local-corpus smoke test when a Claude corpus is available:

```bash
uv run --locked ruff check .
uv run --locked pytest -q
HOME=$(mktemp -d) uv run --locked pytest -q
uv run --locked python scripts/smoketest_local_corpus.py

cd wrapped-website
npm test
npm run typecheck
npm run lint
npm audit --omit=dev
npm audit
cd ..
```

If `scripts/smoketest_local_corpus.py` cannot run because no local Claude corpus exists, note that explicitly in the release notes instead of claiming it passed.

## 4. Build artifacts

```bash
rm -rf dist/
uv build
ls -lh dist/
```

Expected artifacts:
- `dist/claude_history_explorer-X.Y.Z.tar.gz`
- `dist/claude_history_explorer-X.Y.Z-py3-none-any.whl`

## 5. Commit and push

```bash
git add pyproject.toml claude_history_explorer/__init__.py CHANGELOG.md docs/RELEASE_PROCESS.md
git commit -m "Release X.Y.Z"
git push origin main
```

Wait for the `main` CI run to pass before tagging.

## 6. Tag the release

```bash
git tag -a vX.Y.Z -m "Release X.Y.Z"
git push origin vX.Y.Z
```

If a previous changelog compare target is missing, create the missing historical tag only if the commit is known and already has matching version metadata. Example from this repository's first release:

```bash
git tag -a v0.1.0 4c7eb42 -m "Release 0.1.0"
git push origin v0.1.0
```

## 7. Create the GitHub release

Prepare release notes from the changelog entry, then upload build artifacts:

```bash
gh release create vX.Y.Z dist/* \
  --title "X.Y.Z" \
  --notes-file /tmp/release-notes-X.Y.Z.md
```

Verify:

```bash
gh release view vX.Y.Z --json tagName,name,publishedAt,url
```

## 8. Optional publishing/deployment

If publishing to PyPI is in scope:

```bash
uv publish
```

If the Wrapped website is not automatically deployed from `main`, deploy it manually and smoke-test a generated URL:

```bash
cd wrapped-website
npm run deploy
cd ..
claude-history wrapped --no-copy
```

## 9. Final verification

Confirm:
- `git status -sb` is clean.
- `git tag --points-at HEAD` includes the release tag.
- GitHub release exists and includes artifacts.
- `gh run list --branch main --limit 1` shows a successful release commit CI run.
- Any known warnings or skipped optional checks are documented in the release notes.
