# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Wrapped website decoder now normalizes legacy optional V3 sample fields before runtime validation, so previously generated golden URLs render after deployment.

## [0.2.0] - 2026-06-06

### Added
- Claude Code Wrapped V3 with compact MessagePack/Base64URL encoding, `/wrapped?d=...` URLs, print-view website rendering, SVG social preview, and Python/TypeScript decoder coverage.
- Work type classification available through `--show-worktype` on statistics and summaries.
- GitHub Actions CI covering Python 3.10 and 3.13 on Ubuntu, macOS, and Windows, plus Wrapped website test/typecheck/lint/audit jobs.
- Python↔TypeScript schema alignment, golden URL backwards-compatibility tests, and website Vitest coverage for all `wrapped-website/tests/**/*.test.ts` files.
- `scripts/smoketest_local_corpus.py` for privacy-preserving end-to-end smoke testing against a developer's local Claude corpus.
- `docs/LESSONS_LEARNED.md` and `docs/RELEASE_PROCESS.md` for project maintenance and release procedures.
- Domain model, FAQ, Wrapped architecture/spec, Trust, and Cloudflare proposal documentation.

### Changed
- Split the original monolithic history implementation into focused modules (`models.py`, `parser.py`, `projects.py`, `stats.py`, `stories.py`, `wrapped.py`) while keeping `history.py` as a backwards-compatible facade.
- Improved cross-platform project discovery and path decoding for Unix, Windows drive-letter, UNC, dotted, spaced, underscored, and hyphenated project paths.
- Preserved documented `--head` behavior for `sessions` and `show`, and made `--project` misses fail closed instead of falling back to all projects.
- Updated Wrapped project labeling so duplicate basenames remain distinct (for example, `app` and `app (2)`).
- Made Wrapped year handling consistent across CLI, Python decoder, and website routes.
- Refreshed documentation for current Wrapped V3 behavior, ambiguity-aware path decoding, validation commands, and related-document links.

### Fixed
- Active-duration calculation now caps idle gaps consistently, avoiding inflated session hours.
- `search_sessions()` again yields the documented `(session, messages)` tuples and avoids duplicate message matches when content and tool input both match.
- Partial session lookup supports substring matches as documented.
- Project listing no longer crashes when empty project directories produce `None` timestamps alongside timezone-aware datetimes.
- JSONL parsing tolerates invalid UTF-8 and skips oversized physical lines without reading whole lines into memory.
- Regex handling reports Click errors for invalid patterns and rejects additional nested-quantifier ReDoS patterns.
- Story/global summary generation handles zero-session projects and concurrent session counting correctly.
- Session fingerprint quarter buckets now behave correctly for short sessions.
- Tests no longer dirty tracked fixtures and are portable across Windows default encodings and `npx.cmd` subprocess behavior.

### Security
- Hardened output path sanitization against sibling-prefix traversal.
- Hardened Wrapped decoders against malformed Base64URL, oversized payloads, invalid MessagePack/schema, unsupported versions, and malformed/bounded RLE heatmaps.
- Escaped and clamped Wrapped website rendering, removed inline event handlers/remote fonts, added stricter security headers, and avoided per-user Cloudflare cache persistence.
- Updated JavaScript dependencies and verified `npm audit --omit=dev` and full `npm audit` with no vulnerabilities.

## [0.1.0] - 2025-12-06

### Added
- Initial release of Claude History Explorer
- **Commands**:
  - `projects` - List all Claude Code projects
  - `sessions` - List sessions for a specific project
  - `show` - Display messages from a session
  - `search` - Search across all conversations with regex support
  - `export` - Export sessions to markdown, JSON, or text
  - `stats` - Show detailed statistics with JSON output option
  - `summary` - Generate comprehensive summaries with ASCII charts and sparklines
  - `story` - Tell the narrative story of your development journey
  - `info` - Show Claude Code storage location and usage statistics
- **Story Generation**:
  - Project lifecycle and evolution analysis
  - Collaboration style detection (agent vs main sessions)
  - Work intensity and session pattern analysis
  - Personality trait classification
  - Concurrent Claude instance detection
  - Timeline visualization with sparklines
- **Data Models**:
  - `Message`, `Session`, `Project` for core data
  - `SessionInfo`, `ProjectStory`, `GlobalStory` for analysis
  - `ProjectStats`, `GlobalStats` for statistics
- **Output Formats**:
  - Rich terminal formatting with tables, panels, and syntax highlighting
  - JSON export for scripting and automation
  - Markdown export for documentation
  - Brief, detailed, and timeline story formats
- **Safety**:
  - Read-only access to Claude Code history (verified by tests)
  - Path sanitization to prevent directory traversal
  - Graceful handling of missing or corrupted files
- **Documentation**:
  - README with usage examples
  - Architecture documentation
  - JSON schema documentation

[Unreleased]: https://github.com/adewale/claude-history-explorer/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/adewale/claude-history-explorer/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/adewale/claude-history-explorer/tree/v0.1.0
