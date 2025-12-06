# JSON Schema Documentation

This document describes the JSON output formats for commands that support `--format json`.

## Commands with JSON Output

| Command | Flag | Description |
|---------|------|-------------|
| `stats` | `--format json` | Statistics for all projects or a specific project |
| `export` | `--format json` | Full session export with messages |

---

## Global Statistics Schema

**Command:** `claude-history stats --format json`

```json
{
  "total_projects": 4,
  "total_sessions": 67,
  "total_messages": 4701,
  "total_user_messages": 375,
  "total_duration_minutes": 17094,
  "total_duration_str": "284h 54m",
  "total_size_mb": 45.44,
  "avg_sessions_per_project": 16.75,
  "avg_messages_per_session": 70.16,
  "most_active_project": "/Users/foo/Documents/myproject",
  "largest_project": "/Users/foo/Documents/bigproject",
  "most_recent_activity": "2025-12-06T13:01:05.319000+00:00",
  "projects": [
    {
      "path": "/Users/foo/Documents/project1",
      "sessions": 15,
      "messages": 1480,
      "size_mb": 9.85,
      "duration_str": "63h 24m"
    }
  ]
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `total_projects` | integer | Number of Claude Code projects |
| `total_sessions` | integer | Sum of all session files |
| `total_messages` | integer | Sum of all messages (user + assistant) |
| `total_user_messages` | integer | Sum of user messages only |
| `total_duration_minutes` | integer | Total development time in minutes |
| `total_duration_str` | string | Human-readable duration (e.g., "284h 54m") |
| `total_size_mb` | float | Total storage used in megabytes |
| `avg_sessions_per_project` | float | Mean sessions per project |
| `avg_messages_per_session` | float | Mean messages per session |
| `most_active_project` | string | Path of project with most messages |
| `largest_project` | string | Path of project using most storage |
| `most_recent_activity` | string | ISO 8601 timestamp of latest session |
| `projects` | array | Per-project breakdown (see below) |

### Projects Array Item

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Decoded project path |
| `sessions` | integer | Number of sessions |
| `messages` | integer | Total messages |
| `size_mb` | float | Storage in megabytes |
| `duration_str` | string | Human-readable total duration |

---

## Project Statistics Schema

**Command:** `claude-history stats -p <project> --format json`

```json
{
  "project_path": "/Users/foo/Documents/myproject",
  "total_sessions": 21,
  "total_messages": 1701,
  "total_user_messages": 96,
  "total_duration_minutes": 5397,
  "total_duration_str": "89h 57m",
  "agent_sessions": 18,
  "main_sessions": 3,
  "total_size_mb": 11.94,
  "avg_messages_per_session": 81.0,
  "longest_session_duration": "86h 23m",
  "most_recent_session": "2025-12-06T12:46:32.438000+00:00"
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `project_path` | string | Decoded project path |
| `total_sessions` | integer | Number of session files |
| `total_messages` | integer | Sum of all messages |
| `total_user_messages` | integer | Sum of user messages only |
| `total_duration_minutes` | integer | Total time in minutes |
| `total_duration_str` | string | Human-readable duration |
| `agent_sessions` | integer | Count of `agent-*.jsonl` files |
| `main_sessions` | integer | Count of non-agent sessions |
| `total_size_mb` | float | Storage in megabytes |
| `avg_messages_per_session` | float | Mean messages per session |
| `longest_session_duration` | string | Duration of longest session |
| `most_recent_session` | string | ISO 8601 timestamp |

---

## Session Export Schema

**Command:** `claude-history export <session_id> --format json`

```json
{
  "session_id": "25cf8189-42ce-449d-af3b-976dd1afc11d",
  "project_path": "/Users/foo/Documents/myproject",
  "slug": "generic-coalescing-ullman",
  "start_time": "2025-12-02T20:22:02.398000+00:00",
  "end_time": "2025-12-02T22:25:41.882000+00:00",
  "messages": [
    {
      "role": "user",
      "content": "Hello, can you help me?",
      "timestamp": "2025-12-02T20:22:02.398000+00:00",
      "tool_uses": []
    },
    {
      "role": "assistant",
      "content": "Of course! Let me check the project.",
      "timestamp": "2025-12-02T20:22:15.000000+00:00",
      "tool_uses": [
        {
          "name": "Bash",
          "input": {
            "command": "ls -la",
            "description": "List files"
          }
        }
      ]
    }
  ]
}
```

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Unique session identifier (UUID) |
| `project_path` | string | Decoded project path |
| `slug` | string \| null | Session slug/title (may be null) |
| `start_time` | string \| null | ISO 8601 timestamp of first message |
| `end_time` | string \| null | ISO 8601 timestamp of last message |
| `messages` | array | Ordered list of messages |

### Message Object

| Field | Type | Description |
|-------|------|-------------|
| `role` | string | Either `"user"` or `"assistant"` |
| `content` | string | Text content of the message |
| `timestamp` | string \| null | ISO 8601 timestamp |
| `tool_uses` | array | List of tools used (assistant only) |

### Tool Use Object

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Tool name (e.g., "Bash", "Read", "Write") |
| `input` | object | Tool-specific input parameters |

---

## Usage Examples

### Get global stats as JSON for scripting

```bash
claude-history stats --format json | jq '.total_messages'
```

### Get most active project

```bash
claude-history stats --format json | jq -r '.most_active_project'
```

### Export session and extract user messages

```bash
claude-history export abc123 --format json | jq '.messages[] | select(.role == "user") | .content'
```

### Count agent vs main sessions for a project

```bash
claude-history stats -p myproject --format json | jq '{agent: .agent_sessions, main: .main_sessions}'
```

### Get all project paths

```bash
claude-history stats --format json | jq -r '.projects[].path'
```

---

## Notes

- All timestamps are in ISO 8601 format with timezone information
- Paths are decoded from the Claude Code storage format (e.g., `-Users-foo-bar` becomes `/Users/foo/bar`)
- The `tool_uses` array is empty for user messages
- The `input` field in tool uses varies by tool type
- Duration strings use the format `Xh Ym` (hours and minutes)
