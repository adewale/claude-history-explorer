# Claude History Explorer Architecture

## Overview

Claude History Explorer is a command-line tool designed to read and analyze Claude Code conversation history stored locally. The architecture follows a clean separation of concerns with three main layers: data models, core business logic, and CLI interface.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI Layer                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐ │
│  │   Commands      │  │   Formatters    │  │   Display        │ │
│  │  (projects,     │  │  (tables,       │  │  (Rich console,  │ │
│  │   sessions,     │  │   panels,       │  │   sparklines)    │ │
│  │   show, story)  │  │   charts)       │  │                  │ │
│  └─────────────────┘  └─────────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐ │
│  │   Data Access   │  │   Statistics    │  │   Story          │ │
│  │  (File I/O,     │  │  (ProjectStats, │  │  (ProjectStory,  │ │
│  │   Parsing)      │  │   GlobalStats)  │  │   GlobalStory)   │ │
│  └─────────────────┘  └─────────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Model Layer                           │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────┐ │
│  │  Message  │  │  Session  │  │  Project  │  │  SessionInfo  │ │
│  │           │  │           │  │           │  │  (analysis)   │ │
│  └───────────┘  └───────────┘  └───────────┘  └───────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   External Data Store                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐ │
│  │  ~/.claude/     │  │  projects/      │  │  *.jsonl         │ │
│  │  (config)       │  │  (project dirs) │  │  (sessions)      │ │
│  └─────────────────┘  └─────────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Module Structure

```
claude_history_explorer/
├── __init__.py      # Package metadata
├── cli.py           # CLI commands and display formatting
├── history.py       # Data models, parsing, statistics, story generation
└── constants.py     # Thresholds for story personality analysis
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
- Handle different message formats (text, tool_use)
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

#### SessionInfo Class
```python
@dataclass
class SessionInfo:
    start_time: datetime
    end_time: datetime
    message_count: int
    duration_minutes: float
    is_agent: bool
```

**Responsibilities:**
- Lightweight session summary for story analysis
- Track agent vs main session distinction
- Enable concurrent usage detection

#### ProjectStory & GlobalStory Classes
```python
@dataclass
class ProjectStory:
    project_name: str
    lifecycle_days: int
    personality_traits: List[str]
    concurrent_claude_instances: int
    # ... narrative insights
    
@dataclass
class GlobalStory:
    total_projects: int
    common_traits: List[tuple[str, int]]
    project_stories: List[ProjectStory]
    # ... aggregated insights
```

**Responsibilities:**
- Generate narrative insights about development patterns
- Detect concurrent Claude instance usage
- Classify work style and personality traits

### 2. Constants (`constants.py`)

Centralizes thresholds used for personality analysis:

```python
# Message rate thresholds (messages per hour)
MESSAGE_RATE_HIGH = 30
MESSAGE_RATE_MEDIUM = 20

# Session duration thresholds (in hours)
SESSION_LENGTH_LONG = 2.0
SESSION_LENGTH_EXTENDED = 1.0

# Agent collaboration ratios
AGENT_RATIO_HIGH = 0.8
AGENT_RATIO_BALANCED = 0.5

# Activity intensity (messages per day)
ACTIVITY_INTENSITY_HIGH = 300
ACTIVITY_INTENSITY_MEDIUM = 100
```

### 3. Business Logic (`history.py`)

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

**Story Generation:**
- `generate_project_story()`: Create narrative insights for a project
- `generate_global_story()`: Aggregate stories across all projects

**Helper Functions:**
- `format_duration()`: Convert minutes to human-readable format
- `duration_minutes()`: Calculate duration between timestamps
- `classify()`: Threshold-based classification for traits

**Data Flow:**
```
JSONL File → Message.from_json() → Message Object
     ↓
Session File → parse_session() → Session Object
     ↓
Project Dir → Project.from_dir() → Project Object
     ↓
All Projects → calculate_global_stats() → GlobalStats Object
            → generate_global_story() → GlobalStory Object
```

### 4. CLI Interface (`cli.py`)

#### Command Structure
```python
@click.group()
def main(): pass

@main.command()
def projects(): pass    # List all projects

@main.command()
def sessions(): pass    # List sessions for a project

@main.command()
def show(): pass        # View session messages

@main.command()
def search(): pass      # Search across conversations

@main.command()
def export(): pass      # Export session to file

@main.command()
def stats(): pass       # Show statistics

@main.command()
def summary(): pass     # Generate summary with charts

@main.command()
def story(): pass       # Tell development journey story

@main.command()
def info(): pass        # Show storage info
```

#### Output Formatting
- **Rich Tables**: Structured data display
- **Panels**: Highlighted information boxes
- **Syntax Highlighting**: Code and JSON display
- **Sparklines**: Activity trend visualization
- **Story Formats**: Brief, detailed, and timeline views

## Data Flow Architecture

### Read-Only Data Access Pattern

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   CLI Cmd   │───▶│   Business  │───▶│   File I/O  │
│  (Request)  │    │   Logic     │    │  (Read Only)│
└─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Display   │◀───│   Data      │◀───│  JSONL      │
│  (Rich)     │    │ Processing  │    │  Files      │
└─────────────┘    └─────────────┘    └─────────────┘
```

### Story Generation Pipeline

```
Project Discovery
     │
     ▼
Session File Collection
     │
     ▼
SessionInfo Extraction
     │
     ▼
Pattern Analysis (concurrent usage, work pace, collaboration style)
     │
     ▼
Personality Classification (using constants thresholds)
     │
     ▼
ProjectStory / GlobalStory Object
     │
     ▼
Formatted Output (brief/detailed/timeline)
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

## Testing Architecture

### Test Categories
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

1. **Unit Tests**: Individual component behavior
2. **Integration Tests**: Command execution and data flow
3. **Security Tests**: Read-only behavior verification
4. **Error Handling Tests**: Edge cases and failure modes

## Dependencies

### Core Dependencies
```
click>=8.1.0      # CLI framework
rich>=13.0.0      # Terminal formatting
sparklines>=0.5.0 # Activity visualization
```

### Runtime Requirements
- **Python 3.10+**: Core language requirement
- **File System**: Read access to `~/.claude/projects/`
- **Terminal**: ANSI support for Rich formatting

## Summary

The Claude History Explorer architecture emphasizes:

1. **Simplicity**: Clear separation of concerns across 3 modules
2. **Safety**: Read-only design with comprehensive testing
3. **Performance**: Efficient streaming and lazy loading
4. **Insight**: Story generation with personality analysis
5. **User Experience**: Rich terminal interface with multiple output formats
