# Claude History Explorer Architecture

## Overview

Claude History Explorer is a command-line tool designed to read and analyze Claude Code conversation history stored locally. The architecture follows a clean separation of concerns with three main layers: data models, core business logic, and CLI interface.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Commands      │  │   Formatters    │  │   Display    │ │
│  │  (projects,    │  │  (tables,       │  │  (Rich       │ │
│  │   sessions,     │  │   panels,       │  │   console)   │ │
│  │   show, etc.)   │  │   charts)       │  │              │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Data Access   │  │   Statistics    │  │   Search     │ │
│  │  (File I/O,     │  │  (ProjectStats, │  │  (Regex,     │ │
│  │   Parsing)      │  │   GlobalStats)  │  │   Content)   │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Model Layer                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │    Message      │  │     Session     │  │   Project    │ │
│  │  (role, content,│  │  (messages,    │  │  (path,      │ │
│  │   tools, time)  │  │   duration,     │  │   sessions)  │ │
│  │                 │  │   metadata)     │  │              │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   External Data Store                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │  ~/.claude/     │  │  projects/      │  │  *.jsonl     │ │
│  │  (config)       │  │  (project dirs) │  │  (sessions)  │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Data Models (`history.py`)

#### Message Class
```python
@dataclass
class Message:
    role: str           # 'user' or 'assistant'
    content: str        # Text content
    timestamp: Optional[datetime]
    tool_uses: list     # Tool usage information
```

**Responsibilities:**
- Parse JSONL message data
- Extract text content and tool usage
- Handle different message formats (text, tool_use, tool_result)
- Filter out irrelevant message types

#### Session Class
```python
@dataclass
class Session:
    session_id: str
    project_path: str
    file_path: Path
    messages: list[Message]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    slug: Optional[str]
```

**Responsibilities:**
- Aggregate messages from a single conversation
- Calculate session duration and statistics
- Provide access to session metadata

#### Project Class
```python
@dataclass
class Project:
    name: str
    path: str
    dir_path: Path
    session_files: list[Path]
```

**Responsibilities:**
- Represent a Claude Code project
- Decode encoded project paths
- Manage session file discovery
- Track project metadata

### 2. Business Logic (`history.py`)

#### Core Functions

**File Operations:**
- `list_projects()`: Discover all projects
- `parse_session()`: Parse JSONL session files
- `find_project()`: Search for projects by path
- `get_session_by_id()`: Retrieve specific sessions

**Search & Analysis:**
- `search_sessions()`: Regex-based content search
- `calculate_project_stats()`: Generate project statistics
- `calculate_global_stats()`: Aggregate statistics across projects

**Data Flow:**
```
JSONL File → Message.from_json() → Message Object
     ↓
Session File → parse_session() → Session Object
     ↓
Project Dir → Project.from_dir() → Project Object
     ↓
All Projects → calculate_global_stats() → GlobalStats Object
```

### 3. CLI Interface (`cli.py`)

#### Command Structure
```python
@click.group()
def main(): pass

@main.command()
def projects(): pass

@main.command()
def sessions(): pass

@main.command()
def show(): pass

@main.command()
def search(): pass

@main.command()
def export(): pass

@main.command()
def stats(): pass

@main.command()
def summary(): pass
```

#### Output Formatting
- **Rich Tables**: Structured data display
- **Panels**: Highlighted information boxes
- **Syntax Highlighting**: Code and JSON display
- **Progress Indicators**: User feedback

## Data Flow Architecture

### Read-Only Data Access Pattern

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   CLI Cmd   │───▶│   Business  │───▶│   File I/O   │
│  (Request)  │    │   Logic     │    │  (Read Only) │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Display   │◀───│   Data      │◀───│  JSONL      │
│  (Rich)     │    │ Processing  │    │  Files      │
└─────────────┘    └─────────────┘    └─────────────┘
```

### Session Parsing Pipeline

```
JSONL Line
     │
     ▼
JSON Validation
     │
     ▼
Message Type Filter
     │
     ▼
Content Extraction
     │
     ▼
Tool Use Processing
     │
     ▼
Message Object
```

### Statistics Calculation Pipeline

```
Project Discovery
     │
     ▼
Session File Collection
     │
     ▼
Session Parsing
     │
     ▼
Message Aggregation
     │
     ▼
Statistics Calculation
     │
     ▼
Stats Object (ProjectStats/GlobalStats)
```

## Security & Safety

### Read-Only Guarantee
1. **Static Analysis**: Tests verify no write operations in core modules
2. **File Mode Validation**: All file opens use read modes
3. **Path Sanitization**: Project path decoding prevents traversal
4. **Error Handling**: Graceful handling of missing/corrupted files

### Path Security
```
Encoded Path: -Users-username-Documents-my-project
     │
     ▼
Decoding: "/" + name.lstrip("-").replace("-", "/")
     │
     ▼
Result: /Users/username/Documents/my/project
```

## Performance Considerations

### Efficient File Operations
- **Streaming JSONL**: Line-by-line parsing, no full file loading
- **Lazy Loading**: Sessions parsed on-demand
- **File Metadata**: Uses `stat()` for size/timestamp without opening
- **Memory Management**: Generators for large result sets

### Caching Strategy
- **Project Discovery**: Cached during command execution
- **Session Metadata**: Calculated once per session
- **Statistics**: Aggregated from cached data

## Extensibility

### Plugin Architecture Potential
```
┌─────────────────┐
│   Core Engine   │
└─────────┬───────┘
          │
    ┌─────┴─────┐
    │           │
┌───▼───┐   ┌───▼───┐
│Plugins│   │Themes│
└───────┘   └───────┘
```

### Extension Points
1. **Output Formatters**: New export formats
2. **Data Sources**: Support for other chat histories
3. **Analysis Modules**: Custom statistics and insights
4. **Display Themes**: Different visual styles

## Testing Architecture

### Test Pyramid
```
┌─────────────────┐
│  Integration    │  (CLI commands, file operations)
└─────────────────┘
┌─────────────────┐
│   Unit Tests    │  (Individual functions, classes)
└─────────────────┘
┌─────────────────┐
│  Static Analysis│  (Read-only verification, security)
└─────────────────┘
```

### Test Categories
1. **Unit Tests**: Individual component behavior
2. **Integration Tests**: Command execution and data flow
3. **Security Tests**: Read-only behavior verification
4. **Error Handling Tests**: Edge cases and failure modes

## Dependencies & External Interfaces

### Core Dependencies
```
click>=8.1.0     # CLI framework
rich>=13.0.0     # Terminal formatting
```

### External Interfaces
- **File System**: Read-only access to `~/.claude/projects/`
- **Standard Output**: Formatted text display
- **Environment**: Home directory detection

## Configuration Management

### Runtime Configuration
- **No config files**: All settings via CLI arguments
- **Environment Detection**: Automatic Claude directory discovery
- **Default Behaviors**: Sensible defaults for all options

### Future Configuration
```
~/.claude-history-explorer/
├── config.yaml      # User preferences
├── themes/          # Custom themes
└── plugins/         # User plugins
```

## Deployment Architecture

### Installation Methods
```
Source Install → pip install .
UV Install      → uv tool install .
Docker         → docker run claude-history-explorer
Standalone      → Single binary (PyInstaller)
```

### Runtime Requirements
- **Python 3.10+**: Core language requirement
- **File System**: Read access to user home directory
- **Terminal**: ANSI support for Rich formatting
- **Memory**: Minimal (streaming processing)

## Summary

The Claude History Explorer architecture emphasizes:

1. **Simplicity**: Clear separation of concerns
2. **Safety**: Read-only design with comprehensive testing
3. **Performance**: Efficient streaming and lazy loading
4. **Extensibility**: Plugin-ready architecture
5. **User Experience**: Rich terminal interface with multiple output formats

The modular design allows for easy maintenance and extension while maintaining the core guarantee of read-only access to user data.