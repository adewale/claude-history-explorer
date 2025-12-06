# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/adewale/claude-history-explorer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/adewale/claude-history-explorer/releases/tag/v0.1.0
