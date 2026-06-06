# Lessons Learned

Last updated: 2026-06-06

This file records project-level lessons from building, auditing, fixing, and validating Claude History Explorer. Keep it concise, current, and linked to tests or docs when possible.

## 1. Treat Claude history as a hostile-but-local input boundary

The tool is read-only, but the files it reads are still untyped external input. JSONL lines can be malformed, invalid UTF-8, extremely large, or partially written while Claude Code is running.

Practices that followed:
- Parse JSONL with bounded binary `readline()` before decoding text.
- Skip malformed lines without failing the whole session.
- Keep output-file writes explicit and path-sanitized.
- Verify the read-only guarantee with tests and local smoke tests.

## 2. Claude project path encoding is ambiguous

Claude project directory names are encoded path strings, not a reversible schema. Unix paths, Windows drive paths, UNC paths, dots, underscores, spaces, and hyphenated path components can collide once non-alphanumeric characters become `-`.

Practices that followed:
- Recognize Unix, Windows drive-letter, and UNC root shapes.
- Prefer probing real filesystem components by re-encoding candidate child names.
- Fall back to normalized display paths only when the original path is unavailable.
- Test dotted, spaced, hyphenated, empty, duplicate-basename, and Windows-style cases.

## 3. Filters must fail closed, not silently broaden scope

A missed `--project` filter once risked falling back to all projects for commands such as `show`, `search`, and `export`. That is a privacy and correctness failure, not a convenience feature.

Practices that followed:
- If the user supplied a project filter and it does not match, stop and report the miss.
- Compile/validate search regexes before project discovery when possible.
- Add regression tests that assert broader searches are not called on filter misses.

## 4. Documentation is part of the public API

The CLI docs still mentioned `--head` after the option was removed. The fix was to preserve the documented flag rather than make users adapt to an accidental compatibility break.

Practices that followed:
- Keep documented flags working unless a breaking-change note and migration path exist.
- Use docs as compatibility tests for command behavior.
- Update README, FAQ, architecture notes, and specs together when behavior changes.

## 5. Wrapped URLs are shareable public artifacts

Wrapped payloads are intentionally reversible. The privacy model is therefore about data minimization, transparent decodeability, strict validation, and safe rendering—not about pretending Base64 is encryption.

Practices that followed:
- Include aggregate stats, short project names, and visualization data only.
- Exclude conversation text, full paths, code content, and tool input text.
- Validate Base64URL size, MessagePack shape, version, arrays, RLE bounds, and year range.
- Escape rendered fields and set restrictive website headers.
- Keep Python and TypeScript decoders aligned with golden/bridge tests.

## 6. Cross-language features need contract tests, not parallel assumptions

Python encodes Wrapped data and TypeScript decodes/renders it. Bugs appeared when test commands skipped bridge tests or when Vitest did not include all test files.

Practices that followed:
- Run Python↔TypeScript schema alignment and backwards-compatibility tests.
- Fail bridge tests in CI if Node dependencies are missing; skip only in local opt-out situations.
- Keep one authoritative test command for the website (`npm test`) that runs all Vitest tests.

## 7. Security fixes should be regression-tested at the boundary

The highest-value tests were not broad coverage assertions; they were specific boundary tests for traversal, invalid regexes, overlarge lines, malformed Wrapped data, and escaping.

Practices that followed:
- For validators and decoders, test both valid preservation and invalid rejection.
- Prefer public CLI/API tests over private implementation tests when possible.
- Add focused regression tests before or alongside bug fixes.

## 8. Real-corpus smoke tests catch integration gaps unit tests miss

Unit and fixture tests are necessary but not sufficient. A privacy-preserving smoke test against the developer's real Claude corpus exercises command wiring, file discovery, parsing, output generation, and Wrapped encode/decode on actual data shapes.

Practices that followed:
- Keep `scripts/smoketest_local_corpus.py` output redacted: print counts and pass/fail status, not transcript content.
- Exercise every CLI command family: discovery, browsing, search, export, stats, summary, story, and Wrapped.
- Use temporary output directories and delete artifacts by default.

## 9. Specs and roadmaps must distinguish current behavior from proposals

Wrapped docs evolved from proposals for Story Mode, year-path URLs, PNG cards, KV counters, queues, and R2 to the current V3 print-view implementation with `/wrapped?d=...` URLs and SVG social preview. Mixing those states creates audit noise and user confusion.

Practices that followed:
- Put explicit current-implementation notes at the top of historical/proposal docs.
- Keep related-doc links accurate (`WRAPPED_V3_SPEC.md`, not removed spec filenames).
- Label future Cloudflare primitives as proposals unless code and tests prove otherwise.

## 10. CI should encode the project’s real support claims

Windows compatibility cannot rely on local macOS tests. Wrapped bridge coverage cannot rely on optional local dependencies. CI should reflect the supported OS and language boundaries.

Practices that followed:
- Run Python tests on Ubuntu, macOS, and Windows across supported Python versions.
- Install website dependencies before Python bridge tests.
- Run lint, typecheck, test, and audit commands for the website.

## Maintenance checklist

When a new bug or audit finding is fixed, ask:
1. Is the root cause a trust boundary, path/schema ambiguity, or docs/API mismatch?
2. Is there a regression test at the smallest useful tier?
3. Did README, FAQ, Trust, Architecture, schemas/specs, Roadmap, and Changelog stay consistent?
4. Should this file gain a new lesson or update an old one?
