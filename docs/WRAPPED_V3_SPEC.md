# Claude Code Wrapped V3: Tufte Edition

## Executive Summary

A complete redesign of the Wrapped visualization system, replacing narrative "personality labels" with **data integrity**: actual distributions, continuous metrics, and information-dense visualizations that reward close inspection. Inspired by Edward Tufte's principles: maximize data-ink ratio, show the data, enable micro/macro readings.

**Core Philosophy**: Context transforms data into understanding. A histogram of session lengths says more than "Deep-work focused." A density plot of agent ratios reveals nuance that "Collaborative" cannot.

---

## New Data Model

### WrappedStoryV3 Schema

The V3 data model expands from ~500 bytes to ~2-4KB to support rich visualizations while remaining URL-encodable.

```typescript
interface WrappedStoryV3 {
  v: 3;                          // Version
  y: number;                     // Year
  n?: string;                    // Display name (optional)

  // === CORE COUNTS ===
  p: number;                     // Total projects
  s: number;                     // Total sessions
  m: number;                     // Total messages
  h: number;                     // Total hours
  d: number;                     // Days active

  // === TEMPORAL DATA (for heatmaps/timelines) ===
  hm: number[];                  // 7×24 heatmap: 168 values (hour 0-23 × day 0-6)
                                 // Index = (dayOfWeek * 24) + hour
                                 // Value = message count in that slot
                                 // Encoding: RLE for sparse data

  ma: number[];                  // Monthly activity: 12 values (messages per month)
  mh: number[];                  // Monthly hours: 12 values
  ms: number[];                  // Monthly sessions: 12 values

  // === DISTRIBUTIONS (for histograms) ===
  sd: number[];                  // Session duration distribution: 10 buckets
                                 // [<15m, 15-30m, 30-60m, 1-2h, 2-4h, 4-8h, 8-12h, 12-24h, 24-48h, >48h]

  ar: number[];                  // Agent ratio distribution across projects: 10 buckets
                                 // [0-10%, 10-20%, ..., 90-100%] agent usage

  ml: number[];                  // Message length distribution: 8 buckets (chars)
                                 // [<50, 50-100, 100-200, 200-500, 500-1k, 1-2k, 2-5k, >5k]

  // === TRAIT SCORES (0-100 integers) ===
  // Quantized behavioral dimensions. Using integers for compact msgpack encoding
  // (1 byte vs 9 bytes for floats). Display as percentages or map to descriptors.
  ts: {
    ad: number;                  // Agent delegation tendency (0=hands-on, 100=heavy delegation)
    sp: number;                  // Session depth preference (0=quick, 100=marathon)
    fc: number;                  // Focus concentration (0=scattered, 100=single-project)
    cc: number;                  // Circadian consistency (0=chaotic, 100=regular schedule)
    wr: number;                  // Weekend ratio (0=weekday-only, 100=weekend-heavy)
    bs: number;                  // Burst vs steady (0=steady, 100=burst-oriented)
    cs: number;                  // Context-switching frequency (0=stays focused, 100=switches often)
    mv: number;                  // Message verbosity (0=terse, 100=verbose)
    td: number;                  // Tool diversity (0=minimal tools, 100=many tools)
    ri: number;                  // Response intensity (0=light sessions, 100=intense)
  };

  // === PROJECT DATA ===
  // Limited to top 12 projects by message count; remainder grouped as implicit "Other"
  // Wire format: [name, messages, hours, days, sessions, agent_ratio]
  tp: Array<{                    // Top projects (max 12)
    n: string;                   // Name (truncated to 50 chars)
    m: number;                   // Messages
    h: number;                   // Hours (integer)
    d: number;                   // Days active
    s: number;                   // Sessions
    ar: number;                  // Agent ratio (0-100)
  }>;

  // === PROJECT CO-OCCURRENCE (for graph) ===
  // Limited to top 20 edges by weight
  pc: Array<[number, number, number]>;  // [proj_idx_a, proj_idx_b, co_occurrence_days]
                                        // Only pairs with co_occurrence > 0

  // === TIMELINE EVENTS ===
  // Limited to 25 most significant events (increased from original 15 to use URL headroom)
  // Wire format: [day, type, value, project_idx] (-1 for missing optional values)
  te: Array<{
    d: number;                   // Day of year (1-366)
    t: number;                   // Event type index (see EVENT_TYPES)
    v?: number;                  // Optional value (e.g., message count for peak_day)
    p?: number;                  // Optional project index (into tp array)
  }>;

  // === SESSION FINGERPRINTS (subset for visualization) ===
  // Limited to 20 most significant sessions (increased from original 10 to use URL headroom)
  // Wire format: [duration, messages, is_agent, hour, weekday, project_idx, fp0..fp7]
  sf: Array<{                    // Top 20 most significant sessions
    d: number;                   // Duration minutes
    m: number;                   // Message count
    a: boolean;                  // Is agent session (wire: 1/0)
    h: number;                   // Start hour (0-23)
    w: number;                   // Day of week (0-6, 0=Monday)
    pi: number;                  // Project index (into tp array)
    fp: number[];                // Fingerprint: 8 integers 0-100 encoding session "shape"
                                 // [msg_rate_q1, msg_rate_q2, msg_rate_q3, msg_rate_q4,
                                 //  tool_density, error_rate, edit_ratio, thinking_ratio]
  }>;

  // === YEAR-OVER-YEAR (if previous year data exists) ===
  yoy?: {
    pm: number;                  // Previous year messages
    ph: number;                  // Previous year hours
    ps: number;                  // Previous year sessions
    pp: number;                  // Previous year projects
    pd: number;                  // Previous year days active
  };
}

// Event type indices (for compact encoding)
const EVENT_TYPES = [
  'peak_day',      // 0
  'streak_start',  // 1
  'streak_end',    // 2
  'new_project',   // 3
  'milestone',     // 4
  'gap_start',     // 5
  'gap_end',       // 6
] as const;
```

### Size Budget Analysis (Revised)

| Field | Typical Size | Max Size | Notes |
|-------|--------------|----------|-------|
| Core fields (v,y,n,p,s,m,h,d) | ~30 bytes | ~50 bytes | |
| Heatmap (168 values, RLE) | ~80 bytes | ~200 bytes | RLE compresses sparse data, quantized 0-15 |
| Monthly arrays (3×12) | ~50 bytes | ~60 bytes | Small integers |
| Distributions (3 arrays) | ~40 bytes | ~50 bytes | 10+10+8 bucket counts |
| Trait scores (10 ints) | ~15 bytes | ~20 bytes | 0-100 integers (1 byte each) |
| Projects (max 12) | ~400 bytes | ~600 bytes | ~50 bytes each, 6-element arrays |
| Co-occurrence (max 20) | ~80 bytes | ~120 bytes | Triples of small ints |
| Timeline events (max 25) | ~150 bytes | ~200 bytes | Indexed types, 4-element arrays |
| Session fingerprints (20) | ~400 bytes | ~500 bytes | 14-element arrays (no ID field) |
| YoY (5 values) | ~25 bytes | ~30 bytes | Optional |
| **Total** | **~1.3KB** | **~1.8KB** | Safe margin under 2KB |

### Hard Limits

These limits ensure URL size stays under 2KB:

| Field | Limit | Overflow Strategy |
|-------|-------|-------------------|
| `tp` (projects) | 12 | Remainder stats summed into hidden "Other" |
| `pc` (co-occurrence) | 20 edges | Keep highest-weight edges |
| `te` (events) | 25 | Prioritize: peak > milestones > streaks > gaps > new_project |
| `sf` (fingerprints) | 20 | Keep highest significance score |
| Project names | 50 chars | Truncate with ellipsis |
| Display name | 30 chars | Truncate |

---

## Phase 1: Data Collection Enhancement

### 1.1 Required Type Definitions

```python
# In history.py - add to existing types

@dataclass
class SessionInfoV3(SessionInfo):
    """Extended SessionInfo with project tracking."""
    project_name: str = ""       # Project this session belongs to
    project_path: str = ""       # Full project path


@dataclass
class ProjectStats:
    """Statistics for a single project."""
    name: str
    path: str
    message_count: int
    session_count: int
    agent_sessions: int
    main_sessions: int
    hours: float
    days_active: int
    first_day: int              # Day of year (1-366)
    last_day: int               # Day of year (1-366)

    @property
    def total_sessions(self) -> int:
        return self.agent_sessions + self.main_sessions

    @property
    def agent_ratio(self) -> float:
        if self.total_sessions == 0:
            return 0.0
        return self.agent_sessions / self.total_sessions
```

### 1.2 Heatmap Data Collection

```python
def compute_activity_heatmap(sessions: List[SessionInfoV3]) -> List[int]:
    """Compute 7×24 activity heatmap from sessions.

    Returns:
        List of 168 integers: heatmap[day * 24 + hour] = message_count
        day: 0=Monday, 6=Sunday
        hour: 0-23
    """
    heatmap = [0] * 168

    for session in sessions:
        if not session.start_time:
            continue

        # Attribute all messages to start hour (simplification)
        # More accurate: distribute across session duration
        day = session.start_time.weekday()  # 0=Monday
        hour = session.start_time.hour
        idx = day * 24 + hour
        heatmap[idx] += session.message_count

    return heatmap
```

### 1.3 Distribution Computation

```python
from bisect import bisect_right

SESSION_DURATION_BUCKETS = [15, 30, 60, 120, 240, 480, 720, 1440, 2880]  # minutes
AGENT_RATIO_BUCKETS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]      # 0-1
MESSAGE_LENGTH_BUCKETS = [50, 100, 200, 500, 1000, 2000, 5000]            # chars


def compute_distribution(values: List[float], buckets: List[float]) -> List[int]:
    """Bucket values into a histogram distribution.

    Uses bisect for correct bucket assignment:
    - Bucket 0: value <= buckets[0]
    - Bucket i: buckets[i-1] < value <= buckets[i]
    - Bucket n: value > buckets[n-1]

    Returns:
        List of len(buckets)+1 counts
    """
    dist = [0] * (len(buckets) + 1)
    for v in values:
        bucket_idx = bisect_right(buckets, v)
        dist[bucket_idx] += 1
    return dist


def compute_session_duration_distribution(sessions: List[SessionInfoV3]) -> List[int]:
    """Compute session duration histogram."""
    durations = [s.duration_minutes for s in sessions if s.duration_minutes > 0]
    return compute_distribution(durations, SESSION_DURATION_BUCKETS)


def compute_agent_ratio_distribution(projects: List[ProjectStats]) -> List[int]:
    """Compute agent ratio histogram across projects."""
    ratios = [p.agent_ratio for p in projects if p.total_sessions > 0]
    return compute_distribution(ratios, AGENT_RATIO_BUCKETS)
```

### 1.4 Continuous Trait Scores

```python
def compute_trait_scores(
    sessions: List[SessionInfoV3],
    projects: List[ProjectStats],
    heatmap: List[int]
) -> Dict[str, float]:
    """Compute continuous 0-1 scores for behavioral dimensions.

    These are self-relative normalized scores, NOT population percentiles.
    Each score is scaled to [0, 1] based on reasonable thresholds.
    """
    scores = {}

    # === AGENT DELEGATION (ad) ===
    # 0 = all hands-on, 1 = all agent
    total_sessions = len(sessions)
    agent_sessions = len([s for s in sessions if s.is_agent])
    scores['ad'] = agent_sessions / total_sessions if total_sessions > 0 else 0.5

    # === SESSION DEPTH PREFERENCE (sp) ===
    # 0 = median <15min, 1 = median >4 hours
    durations = sorted([s.duration_minutes for s in sessions if s.duration_minutes > 0])
    if durations:
        median_duration = durations[len(durations) // 2]
        scores['sp'] = min(1.0, median_duration / 240)  # 4 hours = 1.0
    else:
        scores['sp'] = 0.5

    # === FOCUS CONCENTRATION (fc) ===
    # Herfindahl-Hirschman Index: 1/n (even) to 1.0 (all in one project)
    if projects:
        total_messages = sum(p.message_count for p in projects)
        if total_messages > 0:
            hhi = sum((p.message_count / total_messages) ** 2 for p in projects)
            scores['fc'] = hhi
        else:
            scores['fc'] = 0.5
    else:
        scores['fc'] = 0.5

    # === CIRCADIAN CONSISTENCY (cc) ===
    # Low variance in start hours = high consistency
    start_hours = [s.start_time.hour for s in sessions if s.start_time]
    if len(start_hours) > 1:
        mean_hour = sum(start_hours) / len(start_hours)
        variance = sum((h - mean_hour) ** 2 for h in start_hours) / len(start_hours)
        # Variance of 36 (std=6 hours) = inconsistent
        scores['cc'] = max(0.0, 1 - variance / 36)
    else:
        scores['cc'] = 0.5

    # === WEEKEND RATIO (wr) ===
    # 0 = no weekend activity, 1 = 40%+ weekend (vs expected 28.6%)
    weekend_messages = sum(heatmap[5*24:7*24])  # Sat (5) + Sun (6)
    weekday_messages = sum(heatmap[0:5*24])      # Mon-Fri (0-4)
    total = weekend_messages + weekday_messages
    if total > 0:
        raw_ratio = weekend_messages / total
        scores['wr'] = min(1.0, raw_ratio / 0.4)  # 40% weekend = 1.0
    else:
        scores['wr'] = 0.0

    # === BURST VS STEADY (bs) ===
    # Coefficient of variation of daily message counts
    daily_messages: Dict[date, int] = defaultdict(int)
    for s in sessions:
        if s.start_time:
            day_key = s.start_time.date()
            daily_messages[day_key] += s.message_count

    if len(daily_messages) > 1:
        values = list(daily_messages.values())
        mean_daily = sum(values) / len(values)
        if mean_daily > 0:
            std_daily = (sum((v - mean_daily) ** 2 for v in values) / len(values)) ** 0.5
            cv = std_daily / mean_daily
            scores['bs'] = min(1.0, cv)  # CV > 1 = very bursty
        else:
            scores['bs'] = 0.5
    else:
        scores['bs'] = 0.5

    # === CONTEXT SWITCHING (cs) ===
    # Average unique projects per active day
    projects_per_day: Dict[date, Set[str]] = defaultdict(set)
    for s in sessions:
        if s.start_time and s.project_name:
            day_key = s.start_time.date()
            projects_per_day[day_key].add(s.project_name)

    if projects_per_day:
        avg_projects = sum(len(p) for p in projects_per_day.values()) / len(projects_per_day)
        # 1 project/day = 0, 4+ projects/day = 1
        scores['cs'] = min(1.0, (avg_projects - 1) / 3)
    else:
        scores['cs'] = 0.0

    # === MESSAGE VERBOSITY (mv) ===
    # Inverse of message rate (high rate = short messages = low verbosity)
    messages_per_hour = [
        s.message_count / max(0.1, s.duration_minutes / 60)
        for s in sessions if s.duration_minutes > 0
    ]
    if messages_per_hour:
        median_rate = sorted(messages_per_hour)[len(messages_per_hour) // 2]
        # 30 msg/hr = terse (0), 5 msg/hr = verbose (1)
        scores['mv'] = max(0.0, 1 - median_rate / 30)
    else:
        scores['mv'] = 0.5

    # === TOOL DIVERSITY (td) ===
    # Placeholder - requires parsing tool usage from messages
    # TODO: Implement when tool usage data is available
    scores['td'] = 0.5

    # === RESPONSE INTENSITY (ri) ===
    # Median messages per hour during sessions
    if messages_per_hour:
        median_intensity = sorted(messages_per_hour)[len(messages_per_hour) // 2]
        scores['ri'] = min(1.0, median_intensity / 20)  # 20 msg/hr = intense
    else:
        scores['ri'] = 0.5

    # Round all scores to 2 decimal places
    return {k: round(v, 2) for k, v in scores.items()}
```

### 1.5 Project Co-occurrence Graph

```python
def compute_project_cooccurrence(
    sessions: List[SessionInfoV3],
    project_names: List[str],
    max_edges: int = 20
) -> List[Tuple[int, int, int]]:
    """Compute project co-occurrence: which projects were worked on the same day.

    Args:
        sessions: List of sessions with project_name set
        project_names: Ordered list of project names (indices into tp array)
        max_edges: Maximum edges to return (keeps highest weights)

    Returns:
        List of (project_a_idx, project_b_idx, days_co_occurred)
        Sorted by weight descending, limited to max_edges
    """
    proj_to_idx = {name: i for i, name in enumerate(project_names)}

    # Group sessions by day
    sessions_by_day: Dict[date, Set[str]] = defaultdict(set)
    for s in sessions:
        if s.start_time and s.project_name:
            day = s.start_time.date()
            sessions_by_day[day].add(s.project_name)

    # Count co-occurrences
    cooccurrence: Dict[Tuple[int, int], int] = defaultdict(int)
    for day_projects in sessions_by_day.values():
        project_list = [p for p in day_projects if p in proj_to_idx]
        for i in range(len(project_list)):
            for j in range(i + 1, len(project_list)):
                idx_a = proj_to_idx[project_list[i]]
                idx_b = proj_to_idx[project_list[j]]
                # Always store smaller index first for consistency
                key = (min(idx_a, idx_b), max(idx_a, idx_b))
                cooccurrence[key] += 1

    # Sort by weight and limit
    edges = [(a, b, count) for (a, b), count in cooccurrence.items()]
    edges.sort(key=lambda x: x[2], reverse=True)
    return edges[:max_edges]
```

### 1.6 Timeline Events Detection

```python
EVENT_TYPE_INDICES = {
    'peak_day': 0,
    'streak_start': 1,
    'streak_end': 2,
    'new_project': 3,
    'milestone': 4,
    'gap_start': 5,
    'gap_end': 6,
}


def detect_timeline_events(
    sessions: List[SessionInfoV3],
    project_names: List[str],
    year: int,
    max_events: int = 15
) -> List[Dict]:
    """Detect significant events throughout the year.

    Events are prioritized: peak > milestones > streaks > gaps > new_project

    Returns:
        List of event dicts with 'd' (day), 't' (type index), 'v' (value), 'p' (project index)
    """
    proj_to_idx = {name: i for i, name in enumerate(project_names)}
    events = []

    # Group by day of year
    messages_by_day: Dict[int, int] = defaultdict(int)
    projects_first_day: Dict[str, int] = {}

    for s in sessions:
        if not s.start_time or s.start_time.year != year:
            continue

        day_of_year = s.start_time.timetuple().tm_yday
        messages_by_day[day_of_year] += s.message_count

        if s.project_name and s.project_name not in projects_first_day:
            projects_first_day[s.project_name] = day_of_year

    if not messages_by_day:
        return []

    # === PEAK DAY (highest priority) ===
    peak_day = max(messages_by_day.keys(), key=lambda d: messages_by_day[d])
    events.append({
        'd': peak_day,
        't': EVENT_TYPE_INDICES['peak_day'],
        'v': messages_by_day[peak_day]
    })

    # === MILESTONES ===
    cumulative = 0
    milestones = [100, 500, 1000, 2000, 5000, 10000]
    milestone_idx = 0
    for day in sorted(messages_by_day.keys()):
        cumulative += messages_by_day[day]
        while milestone_idx < len(milestones) and cumulative >= milestones[milestone_idx]:
            events.append({
                'd': day,
                't': EVENT_TYPE_INDICES['milestone'],
                'v': milestones[milestone_idx]
            })
            milestone_idx += 1

    # === STREAKS AND GAPS ===
    active_days = sorted(messages_by_day.keys())
    streak_start = active_days[0]
    streak_length = 1

    for i in range(1, len(active_days)):
        gap = active_days[i] - active_days[i-1]

        if gap == 1:
            streak_length += 1
        else:
            # End of streak
            if streak_length >= 5:
                events.append({'d': streak_start, 't': EVENT_TYPE_INDICES['streak_start']})
                events.append({'d': active_days[i-1], 't': EVENT_TYPE_INDICES['streak_end'], 'v': streak_length})

            # Gap detection
            if gap >= 7:
                events.append({'d': active_days[i-1], 't': EVENT_TYPE_INDICES['gap_start']})
                events.append({'d': active_days[i], 't': EVENT_TYPE_INDICES['gap_end'], 'v': gap})

            streak_start = active_days[i]
            streak_length = 1

    # Final streak check
    if streak_length >= 5:
        events.append({'d': streak_start, 't': EVENT_TYPE_INDICES['streak_start']})
        events.append({'d': active_days[-1], 't': EVENT_TYPE_INDICES['streak_end'], 'v': streak_length})

    # === NEW PROJECT EVENTS (lowest priority) ===
    for project, day in projects_first_day.items():
        if project in proj_to_idx:
            events.append({
                'd': day,
                't': EVENT_TYPE_INDICES['new_project'],
                'p': proj_to_idx[project]
            })

    # Sort by day, then by priority (lower type index = higher priority)
    events.sort(key=lambda e: (e['d'], e['t']))

    # Limit to max_events, keeping highest priority
    if len(events) > max_events:
        # Re-sort by priority, take top N, then re-sort by day
        events.sort(key=lambda e: e['t'])
        events = events[:max_events]
        events.sort(key=lambda e: e['d'])

    return events
```

### 1.7 Session Fingerprints

```python
def compute_session_fingerprint(session: Session) -> List[float]:
    """Compute an 8-value fingerprint encoding session "shape".

    Fingerprint encodes:
    [0-3]: Message distribution across session quarters (normalized)
    [4]: Tool invocation density (placeholder)
    [5]: Error/retry rate (placeholder)
    [6]: Edit operation ratio (placeholder)
    [7]: Thinking block ratio (placeholder)

    Returns:
        List of 8 floats in [0, 1]
    """
    fingerprint = [0.0] * 8

    if not session.messages or len(session.messages) < 2:
        return fingerprint

    # Divide session into 4 quarters by message index
    total_messages = len(session.messages)
    quarter_size = max(1, total_messages // 4)

    quarter_counts = [0, 0, 0, 0]
    for i, msg in enumerate(session.messages):
        quarter = min(3, i // quarter_size)
        quarter_counts[quarter] += 1

    # Normalize quarters to 0-1
    max_quarter = max(quarter_counts) or 1
    for i in range(4):
        fingerprint[i] = quarter_counts[i] / max_quarter

    # Placeholders for content analysis (TODO: implement)
    fingerprint[4] = 0.5  # tool_density
    fingerprint[5] = 0.1  # error_rate
    fingerprint[6] = 0.3  # edit_ratio
    fingerprint[7] = 0.2  # thinking_ratio

    return [round(v, 2) for v in fingerprint]


def get_top_session_fingerprints(
    sessions: List[SessionInfoV3],
    session_loader: Callable[[str], Session],
    project_names: List[str],
    limit: int = 10
) -> List[Dict]:
    """Get fingerprints for the most significant sessions.

    Args:
        sessions: List of SessionInfoV3 with project_name set
        session_loader: Function to load full Session by session_id
        project_names: Ordered list of project names for indexing
        limit: Max fingerprints to return

    Returns:
        List of fingerprint dicts
    """
    proj_to_idx = {name: i for i, name in enumerate(project_names)}

    # Score sessions by significance (messages × sqrt(duration))
    scored = []
    for s in sessions:
        if s.project_name in proj_to_idx:
            score = s.message_count * (s.duration_minutes ** 0.5 if s.duration_minutes > 0 else 1)
            scored.append((score, s))

    scored.sort(reverse=True, key=lambda x: x[0])

    fingerprints = []
    for _, info in scored[:limit]:
        try:
            full_session = session_loader(info.session_id)
            fp = compute_session_fingerprint(full_session)
        except Exception:
            fp = [0.5] * 8  # Default on error

        fingerprints.append({
            'id': info.session_id[:6],
            'd': info.duration_minutes,
            'm': info.message_count,
            'a': info.is_agent,
            'h': info.start_time.hour if info.start_time else 0,
            'w': info.start_time.weekday() if info.start_time else 0,
            'pi': proj_to_idx.get(info.project_name, 0),
            'fp': fp
        })

    return fingerprints
```

---

## Phase 2: Encoding

### 2.1 Run-Length Encoding for Sparse Data

```python
def rle_encode(values: List[int]) -> List[int]:
    """Run-length encode a list of integers.

    Format: [value, count, value, count, ...]
    Only beneficial for sequences with repeated values.

    Example: [0, 0, 0, 5, 5, 0] -> [0, 3, 5, 2, 0, 1]
    """
    if not values:
        return []

    result = []
    current_value = values[0]
    count = 1

    for v in values[1:]:
        if v == current_value:
            count += 1
        else:
            result.extend([current_value, count])
            current_value = v
            count = 1

    result.extend([current_value, count])
    return result


def rle_decode(encoded: List[int]) -> List[int]:
    """Decode run-length encoded data."""
    result = []
    for i in range(0, len(encoded), 2):
        value = encoded[i]
        count = encoded[i + 1] if i + 1 < len(encoded) else 1
        result.extend([value] * count)
    return result


def rle_encode_if_smaller(values: List[int]) -> Tuple[bool, List[int]]:
    """RLE encode only if it reduces size.

    Returns:
        Tuple of (is_rle_encoded, data)
    """
    encoded = rle_encode(values)
    if len(encoded) < len(values):
        return (True, encoded)
    return (False, values)
```

### 2.2 V3 Encoder

```python
import base64
import msgpack

WRAPPED_VERSION = 3


def encode_wrapped_story_v3(story: 'WrappedStoryV3') -> str:
    """Encode V3 story with RLE compression for sparse heatmap."""
    data = story.to_dict()

    # RLE encode heatmap if beneficial
    if 'hm' in data and data['hm']:
        is_rle, encoded_hm = rle_encode_if_smaller(data['hm'])
        if is_rle:
            data['hm'] = encoded_hm
            data['hm_rle'] = True  # Flag for decoder

    packed = msgpack.packb(data, use_bin_type=True)
    return base64.urlsafe_b64encode(packed).rstrip(b'=').decode('ascii')


def decode_wrapped_story_v3(encoded: str) -> 'WrappedStoryV3':
    """Decode V3 story."""
    # Add padding if needed
    padding = (4 - len(encoded) % 4) % 4
    padded = encoded + '=' * padding

    packed = base64.urlsafe_b64decode(padded)
    data = msgpack.unpackb(packed, raw=False, strict_map_key=False)

    # RLE decode heatmap if flagged
    if data.get('hm_rle') and 'hm' in data:
        data['hm'] = rle_decode(data['hm'])
        del data['hm_rle']

    return WrappedStoryV3.from_dict(data)
```

### 2.3 TypeScript Decoder

```typescript
// decoder.ts

const EVENT_TYPES = [
  'peak_day',
  'streak_start',
  'streak_end',
  'new_project',
  'milestone',
  'gap_start',
  'gap_end',
] as const;

type EventType = typeof EVENT_TYPES[number];

interface WrappedStoryV3 {
  v: 3;
  y: number;
  n?: string;

  p: number;
  s: number;
  m: number;
  h: number;
  d: number;

  hm: number[];
  hm_rle?: boolean;  // Flag indicating RLE encoding
  ma: number[];
  mh: number[];
  ms: number[];

  sd: number[];
  ar: number[];
  ml: number[];

  ts: {
    ad: number;
    sp: number;
    fc: number;
    cc: number;
    wr: number;
    bs: number;
    cs: number;
    mv: number;
    td: number;
    ri: number;
  };

  tp: Array<{
    n: string;
    m: number;
    h: number;
    d: number;
    s: number;
    ar: number;
    fd: number;
    ld: number;
  }>;

  pc: Array<[number, number, number]>;

  te: Array<{
    d: number;
    t: number;
    v?: number;
    p?: number;
  }>;

  sf: Array<{
    id: string;
    d: number;
    m: number;
    a: boolean;
    h: number;
    w: number;
    pi: number;
    fp: number[];
  }>;

  yoy?: {
    pm: number;
    ph: number;
    ps: number;
    pp: number;
    pd: number;
  };
}

function rleDecode(encoded: number[]): number[] {
  const result: number[] = [];
  for (let i = 0; i < encoded.length; i += 2) {
    const value = encoded[i];
    const count = encoded[i + 1] || 1;
    for (let j = 0; j < count; j++) {
      result.push(value);
    }
  }
  return result;
}

function decodeWrappedStoryV3(encoded: string): WrappedStoryV3 {
  const raw = decodeBase64MessagePack(encoded);

  // RLE decode heatmap if flagged
  if (raw.hm_rle && raw.hm) {
    raw.hm = rleDecode(raw.hm);
    delete raw.hm_rle;
  }

  return raw as WrappedStoryV3;
}

function getEventTypeName(typeIndex: number): EventType {
  return EVENT_TYPES[typeIndex] || 'peak_day';
}
```

### 2.4 Helper Functions

```typescript
// helpers.ts

function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - 1) + '…';
}

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return n.toString();
}

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (mins === 0) return `${hours}h`;
  return `${hours}h ${mins}m`;
}
```

---

## Phase 3: Visualization Components

### 3.1 7×24 Activity Heatmap

```typescript
interface HeatmapProps {
  data: number[];  // 168 values
  width?: number;
  height?: number;
  showLabels?: boolean;
}

function renderHeatmap({
  data,
  width = 400,
  height = 140,
  showLabels = true
}: HeatmapProps): string {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const labelWidth = showLabels ? 28 : 0;
  const bottomPadding = showLabels ? 16 : 0;

  const cellW = (width - labelWidth) / 24;
  const cellH = (height - bottomPadding) / 7;
  const max = Math.max(...data, 1);

  let cells = '';
  for (let day = 0; day < 7; day++) {
    for (let hour = 0; hour < 24; hour++) {
      const value = data[day * 24 + hour];
      const intensity = value / max;
      const x = labelWidth + hour * cellW;
      const y = day * cellH;

      cells += `<rect x="${x}" y="${y}" width="${cellW - 1}" height="${cellH - 1}"
                      fill="${intensityToColor(intensity)}" rx="2">
                  <title>${days[day]} ${hour}:00 - ${value} messages</title>
                </rect>`;
    }
  }

  let labels = '';
  if (showLabels) {
    // Day labels
    for (let day = 0; day < 7; day++) {
      labels += `<text x="0" y="${day * cellH + cellH/2 + 4}"
                       font-size="9" fill="var(--text-muted)">${days[day].charAt(0)}</text>`;
    }
    // Hour labels (0, 6, 12, 18)
    for (const hour of [0, 6, 12, 18]) {
      labels += `<text x="${labelWidth + hour * cellW + cellW/2}" y="${height - 4}"
                       font-size="8" fill="var(--text-muted)" text-anchor="middle">${hour}</text>`;
    }
  }

  return `<svg viewBox="0 0 ${width} ${height}" class="heatmap">${cells}${labels}</svg>`;
}

function intensityToColor(intensity: number): string {
  if (intensity === 0) return 'rgba(212, 165, 116, 0.05)';
  const alpha = 0.15 + intensity * 0.85;
  return `rgba(212, 165, 116, ${alpha.toFixed(2)})`;
}
```

### 3.2 Distribution Histograms

```typescript
interface HistogramProps {
  data: number[];
  labels: string[];
  title?: string;
  width?: number;
  height?: number;
}

function renderHistogram({
  data,
  labels,
  title,
  width = 280,
  height = 80
}: HistogramProps): string {
  const titleHeight = title ? 16 : 0;
  const labelHeight = 14;
  const chartHeight = height - titleHeight - labelHeight;

  const max = Math.max(...data, 1);
  const barWidth = width / data.length;

  let bars = '';
  for (let i = 0; i < data.length; i++) {
    const barHeight = (data[i] / max) * chartHeight;
    const x = i * barWidth;
    const y = titleHeight + chartHeight - barHeight;

    bars += `
      <rect x="${x + 1}" y="${y}" width="${barWidth - 2}" height="${barHeight}"
            fill="var(--accent)" rx="1" opacity="0.8">
        <title>${labels[i]}: ${data[i]}</title>
      </rect>`;

    // Labels for first, middle, last
    if (i === 0 || i === data.length - 1 || i === Math.floor(data.length / 2)) {
      bars += `<text x="${x + barWidth/2}" y="${height - 2}"
                     font-size="7" fill="var(--text-muted)" text-anchor="middle">${labels[i]}</text>`;
    }
  }

  const titleSvg = title
    ? `<text x="${width/2}" y="10" font-size="10" fill="var(--text-secondary)" text-anchor="middle">${title}</text>`
    : '';

  return `<svg viewBox="0 0 ${width} ${height}" class="histogram">${titleSvg}${bars}</svg>`;
}

const SESSION_DURATION_LABELS = ['<15m', '15-30', '30m-1h', '1-2h', '2-4h', '4-8h', '8-12h', '12-24h', '24-48h', '>48h'];
const AGENT_RATIO_LABELS = ['0-10%', '10-20%', '20-30%', '30-40%', '40-50%', '50-60%', '60-70%', '70-80%', '80-90%', '90-100%'];
```

### 3.3 Treemap for Projects

```typescript
interface TreemapNode {
  name: string;
  value: number;
  index: number;
}

interface TreemapRect extends TreemapNode {
  x: number;
  y: number;
  w: number;
  h: number;
}

function renderTreemap(
  projects: TreemapNode[],
  width = 400,
  height = 200
): string {
  if (projects.length === 0) return '';

  const total = projects.reduce((sum, p) => sum + p.value, 0);
  const sorted = [...projects].sort((a, b) => b.value - a.value);
  const rects = squarify(sorted, { x: 0, y: 0, w: width, h: height }, total);

  let svgContent = '';
  for (const rect of rects) {
    const fontSize = Math.min(12, Math.max(8, Math.min(rect.w, rect.h) / 6));
    const showLabel = rect.w > 35 && rect.h > 18;
    const showValue = rect.w > 50 && rect.h > 30;

    svgContent += `
      <g class="treemap-node" data-project="${rect.index}">
        <rect x="${rect.x}" y="${rect.y}" width="${rect.w}" height="${rect.h}"
              fill="var(--accent)" opacity="${0.4 + 0.6 * (rect.value / total)}"
              stroke="var(--bg-dark)" stroke-width="2" rx="4">
          <title>${rect.name}: ${formatNumber(rect.value)} messages</title>
        </rect>
        ${showLabel ? `
          <text x="${rect.x + rect.w/2}" y="${rect.y + rect.h/2 - (showValue ? 6 : 0)}"
                font-size="${fontSize}" fill="white" text-anchor="middle"
                dominant-baseline="middle">${truncate(rect.name, Math.floor(rect.w / 7))}</text>
        ` : ''}
        ${showValue ? `
          <text x="${rect.x + rect.w/2}" y="${rect.y + rect.h/2 + 8}"
                font-size="${fontSize - 2}" fill="rgba(255,255,255,0.7)" text-anchor="middle"
                dominant-baseline="middle">${formatNumber(rect.value)}</text>
        ` : ''}
      </g>`;
  }

  return `<svg viewBox="0 0 ${width} ${height}" class="treemap">${svgContent}</svg>`;
}

// Squarified treemap algorithm
function squarify(
  items: TreemapNode[],
  rect: { x: number; y: number; w: number; h: number },
  total: number
): TreemapRect[] {
  if (items.length === 0) return [];
  if (items.length === 1) {
    return [{ ...items[0], x: rect.x, y: rect.y, w: rect.w, h: rect.h }];
  }

  const results: TreemapRect[] = [];
  let remaining = [...items];
  let currentRect = { ...rect };

  while (remaining.length > 0) {
    const isWide = currentRect.w >= currentRect.h;
    const side = isWide ? currentRect.h : currentRect.w;

    // Find optimal row
    let row: TreemapNode[] = [];
    let rowTotal = 0;
    let bestAspect = Infinity;

    for (let i = 0; i < remaining.length; i++) {
      const testRow = remaining.slice(0, i + 1);
      const testTotal = testRow.reduce((s, n) => s + n.value, 0);
      const rowSize = (testTotal / total) * (isWide ? currentRect.w : currentRect.h);

      // Calculate worst aspect ratio in row
      let worstAspect = 0;
      for (const node of testRow) {
        const nodeSize = (node.value / testTotal) * side;
        const aspect = Math.max(rowSize / nodeSize, nodeSize / rowSize);
        worstAspect = Math.max(worstAspect, aspect);
      }

      if (worstAspect < bestAspect) {
        bestAspect = worstAspect;
        row = testRow;
        rowTotal = testTotal;
      } else {
        break;
      }
    }

    // Layout row
    const rowSize = (rowTotal / total) * (isWide ? currentRect.w : currentRect.h);
    let offset = 0;

    for (const node of row) {
      const nodeSize = (node.value / rowTotal) * side;
      if (isWide) {
        results.push({
          ...node,
          x: currentRect.x,
          y: currentRect.y + offset,
          w: rowSize,
          h: nodeSize
        });
      } else {
        results.push({
          ...node,
          x: currentRect.x + offset,
          y: currentRect.y,
          w: nodeSize,
          h: rowSize
        });
      }
      offset += nodeSize;
    }

    // Update remaining rect
    if (isWide) {
      currentRect.x += rowSize;
      currentRect.w -= rowSize;
    } else {
      currentRect.y += rowSize;
      currentRect.h -= rowSize;
    }

    remaining = remaining.slice(row.length);
    total -= rowTotal;
  }

  return results;
}
```

### 3.4 Slope Graph for Year-over-Year

```typescript
interface SlopeGraphProps {
  current: { m: number; h: number; s: number; p: number; d: number };
  previous: { pm: number; ph: number; ps: number; pp: number; pd: number };
  currentYear: number;
  width?: number;
  height?: number;
}

function renderSlopeGraph({
  current,
  previous,
  currentYear,
  width = 280,
  height = 180
}: SlopeGraphProps): string {
  const prevYear = currentYear - 1;
  const metrics = [
    { label: 'Messages', prev: previous.pm, curr: current.m },
    { label: 'Hours', prev: previous.ph, curr: current.h },
    { label: 'Sessions', prev: previous.ps, curr: current.s },
    { label: 'Projects', prev: previous.pp, curr: current.p },
  ];

  const leftX = 55;
  const rightX = width - 55;
  const topY = 28;
  const rowHeight = (height - topY - 10) / metrics.length;

  let lines = '';
  for (let i = 0; i < metrics.length; i++) {
    const m = metrics[i];
    const baseY = topY + i * rowHeight + rowHeight / 2;

    const change = m.curr / Math.max(m.prev, 1);
    const offset = Math.min(15, Math.max(-15, (change - 1) * 30));
    const rightY = baseY - offset;

    const color = change >= 1 ? 'var(--success)' : '#e57373';
    const changeText = change >= 1
      ? `+${Math.round((change - 1) * 100)}%`
      : `${Math.round((change - 1) * 100)}%`;

    lines += `
      <line x1="${leftX}" y1="${baseY}" x2="${rightX}" y2="${rightY}"
            stroke="${color}" stroke-width="2" opacity="0.8"/>
      <circle cx="${leftX}" cy="${baseY}" r="4" fill="${color}"/>
      <circle cx="${rightX}" cy="${rightY}" r="4" fill="${color}"/>
      <text x="${leftX - 6}" y="${baseY + 4}" text-anchor="end" font-size="10" fill="var(--text-muted)">
        ${formatNumber(m.prev)}
      </text>
      <text x="${rightX + 6}" y="${rightY + 4}" text-anchor="start" font-size="10" fill="var(--text-primary)">
        ${formatNumber(m.curr)}
      </text>
      <text x="${width/2}" y="${baseY - 8}" text-anchor="middle" font-size="9" fill="var(--text-secondary)">
        ${m.label}
      </text>
      <text x="${width/2}" y="${baseY + 4}" text-anchor="middle" font-size="8" fill="${color}">
        ${changeText}
      </text>
    `;
  }

  return `
    <svg viewBox="0 0 ${width} ${height}" class="slope-graph">
      <text x="${leftX}" y="14" text-anchor="middle" font-size="11" fill="var(--text-muted)">${prevYear}</text>
      <text x="${rightX}" y="14" text-anchor="middle" font-size="11" fill="var(--text-primary)">${currentYear}</text>
      ${lines}
    </svg>
  `;
}
```

### 3.5 Project Co-occurrence Graph

```typescript
interface CooccurrenceGraphProps {
  projects: string[];
  edges: Array<[number, number, number]>;
  width?: number;
  height?: number;
}

function renderCooccurrenceGraph({
  projects,
  edges,
  width = 300,
  height = 200
}: CooccurrenceGraphProps): string {
  if (projects.length < 2 || edges.length === 0) {
    return '<div class="no-data">Not enough projects for co-occurrence</div>';
  }

  const n = projects.length;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) / 2 - 35;

  // Position nodes in a circle
  const nodes = projects.map((name, i) => ({
    name,
    x: centerX + radius * Math.cos(2 * Math.PI * i / n - Math.PI / 2),
    y: centerY + radius * Math.sin(2 * Math.PI * i / n - Math.PI / 2),
  }));

  // Draw edges
  const maxWeight = Math.max(...edges.map(e => e[2]), 1);
  let edgeSvg = '';
  for (const [a, b, weight] of edges) {
    if (a >= nodes.length || b >= nodes.length) continue;
    const opacity = 0.2 + 0.8 * (weight / maxWeight);
    const strokeWidth = 1 + 2 * (weight / maxWeight);
    edgeSvg += `
      <line x1="${nodes[a].x}" y1="${nodes[a].y}"
            x2="${nodes[b].x}" y2="${nodes[b].y}"
            stroke="var(--accent)" stroke-width="${strokeWidth}" opacity="${opacity}">
        <title>${nodes[a].name} + ${nodes[b].name}: ${weight} days</title>
      </line>`;
  }

  // Draw nodes
  let nodeSvg = '';
  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    // Position label based on angle to avoid overlap
    const angle = 2 * Math.PI * i / n - Math.PI / 2;
    const labelRadius = radius + 18;
    const labelX = centerX + labelRadius * Math.cos(angle);
    const labelY = centerY + labelRadius * Math.sin(angle);
    const anchor = Math.abs(angle) < Math.PI / 2 ? 'start' : 'end';

    nodeSvg += `
      <circle cx="${node.x}" cy="${node.y}" r="5" fill="var(--accent)"/>
      <text x="${labelX}" y="${labelY + 3}" text-anchor="${angle > -Math.PI/2 && angle < Math.PI/2 ? 'start' : 'end'}"
            font-size="9" fill="var(--text-secondary)">${truncate(node.name, 10)}</text>`;
  }

  return `<svg viewBox="0 0 ${width} ${height}" class="cooccurrence-graph">${edgeSvg}${nodeSvg}</svg>`;
}

// Fallback: Adjacency list for mobile
function renderCooccurrenceList(
  projects: string[],
  edges: Array<[number, number, number]>
): string {
  const sorted = [...edges].sort((a, b) => b[2] - a[2]).slice(0, 5);

  let items = '';
  for (const [a, b, weight] of sorted) {
    items += `
      <div class="cooccurrence-item">
        <span class="projects">${truncate(projects[a], 12)} + ${truncate(projects[b], 12)}</span>
        <span class="weight">${weight} days</span>
      </div>`;
  }

  return `<div class="cooccurrence-list">${items}</div>`;
}
```

### 3.6 Trait Radar Chart

```typescript
interface TraitRadarProps {
  scores: WrappedStoryV3['ts'];
  size?: number;
  traits?: (keyof WrappedStoryV3['ts'])[];  // Subset of traits to show
}

const TRAIT_LABELS: Record<keyof WrappedStoryV3['ts'], string> = {
  ad: 'Delegation',
  sp: 'Deep Work',
  fc: 'Focus',
  cc: 'Regularity',
  wr: 'Weekend',
  bs: 'Burst',
  cs: 'Switching',
  mv: 'Verbose',
  td: 'Tools',
  ri: 'Intensity',
};

// 6 key traits for mobile
const MOBILE_TRAITS: (keyof WrappedStoryV3['ts'])[] = ['ad', 'sp', 'fc', 'cc', 'bs', 'ri'];

// All 10 traits for desktop
const ALL_TRAITS: (keyof WrappedStoryV3['ts'])[] = ['ad', 'sp', 'fc', 'cc', 'wr', 'bs', 'cs', 'mv', 'td', 'ri'];

function renderTraitRadar({
  scores,
  size = 260,
  traits = ALL_TRAITS
}: TraitRadarProps): string {
  const n = traits.length;
  const center = size / 2;
  const maxRadius = size / 2 - 35;

  // Concentric circles
  let circles = '';
  for (const pct of [0.25, 0.5, 0.75, 1.0]) {
    circles += `<circle cx="${center}" cy="${center}" r="${maxRadius * pct}"
                        fill="none" stroke="var(--border)" stroke-width="1" opacity="0.5"/>`;
  }

  // Axes and labels
  let axes = '';
  let labels = '';
  for (let i = 0; i < n; i++) {
    const angle = (2 * Math.PI * i / n) - Math.PI / 2;
    const x = center + maxRadius * Math.cos(angle);
    const y = center + maxRadius * Math.sin(angle);
    const labelR = maxRadius + 18;
    const labelX = center + labelR * Math.cos(angle);
    const labelY = center + labelR * Math.sin(angle);

    axes += `<line x1="${center}" y1="${center}" x2="${x}" y2="${y}"
                   stroke="var(--border)" stroke-width="1" opacity="0.5"/>`;

    // Adjust text anchor based on position
    let anchor = 'middle';
    if (Math.cos(angle) > 0.3) anchor = 'start';
    else if (Math.cos(angle) < -0.3) anchor = 'end';

    labels += `<text x="${labelX}" y="${labelY + 3}" text-anchor="${anchor}"
                     font-size="9" fill="var(--text-muted)">${TRAIT_LABELS[traits[i]]}</text>`;
  }

  // Data polygon
  let points = '';
  for (let i = 0; i < n; i++) {
    const angle = (2 * Math.PI * i / n) - Math.PI / 2;
    const value = scores[traits[i]];
    const r = maxRadius * value;
    const x = center + r * Math.cos(angle);
    const y = center + r * Math.sin(angle);
    points += `${x},${y} `;
  }

  return `
    <svg viewBox="0 0 ${size} ${size}" class="trait-radar">
      ${circles}
      ${axes}
      <polygon points="${points.trim()}" fill="rgba(212, 165, 116, 0.25)"
               stroke="var(--accent)" stroke-width="2"/>
      ${labels}
    </svg>
  `;
}

// Fallback: Horizontal bar chart for narrow viewports
function renderTraitBars(
  scores: WrappedStoryV3['ts'],
  traits: (keyof WrappedStoryV3['ts'])[] = MOBILE_TRAITS,
  width = 280
): string {
  const barHeight = 20;
  const labelWidth = 70;
  const height = traits.length * (barHeight + 6) + 10;

  let bars = '';
  for (let i = 0; i < traits.length; i++) {
    const trait = traits[i];
    const value = scores[trait];
    const y = i * (barHeight + 6) + 5;
    const barWidth = (width - labelWidth - 40) * value;

    bars += `
      <text x="${labelWidth - 4}" y="${y + barHeight/2 + 4}"
            text-anchor="end" font-size="10" fill="var(--text-secondary)">${TRAIT_LABELS[trait]}</text>
      <rect x="${labelWidth}" y="${y}" width="${width - labelWidth - 40}" height="${barHeight}"
            fill="var(--border)" rx="3" opacity="0.3"/>
      <rect x="${labelWidth}" y="${y}" width="${barWidth}" height="${barHeight}"
            fill="var(--accent)" rx="3"/>
      <text x="${width - 35}" y="${y + barHeight/2 + 4}"
            text-anchor="start" font-size="10" fill="var(--text-primary)">${value.toFixed(2)}</text>
    `;
  }

  return `<svg viewBox="0 0 ${width} ${height}" class="trait-bars">${bars}</svg>`;
}
```

### 3.7 Timeline with Events

```typescript
interface TimelineProps {
  monthlyActivity: number[];
  events: WrappedStoryV3['te'];
  projectNames: string[];
  width?: number;
  height?: number;
}

function renderTimeline({
  monthlyActivity,
  events,
  projectNames,
  width = 500,
  height = 130
}: TimelineProps): string {
  const margin = { left: 25, right: 15, top: 28, bottom: 22 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;

  const max = Math.max(...monthlyActivity, 1);
  const barWidth = chartWidth / 12;

  // Monthly bars
  let bars = '';
  const months = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
  for (let i = 0; i < 12; i++) {
    const barHeight = (monthlyActivity[i] / max) * chartHeight;
    const x = margin.left + i * barWidth;
    const y = margin.top + chartHeight - barHeight;

    bars += `
      <rect x="${x + 2}" y="${y}" width="${barWidth - 4}" height="${barHeight}"
            fill="var(--accent)" opacity="0.7" rx="2"/>
      <text x="${x + barWidth/2}" y="${height - 6}"
            text-anchor="middle" font-size="9" fill="var(--text-muted)">${months[i]}</text>
    `;
  }

  // Event markers
  const eventIcons: Record<string, string> = {
    'peak_day': '▲',
    'streak_start': '●',
    'streak_end': '○',
    'new_project': '★',
    'milestone': '◆',
    'gap_start': '▽',
    'gap_end': '△',
  };

  let eventMarkers = '';
  const usedPositions: number[] = [];

  for (const event of events) {
    const eventType = EVENT_TYPES[event.t] || 'peak_day';
    // Convert day of year to month (approximate)
    const month = Math.min(11, Math.floor((event.d - 1) / 30.44));
    let x = margin.left + month * barWidth + barWidth / 2;

    // Avoid overlapping markers
    while (usedPositions.some(px => Math.abs(px - x) < 12)) {
      x += 8;
    }
    usedPositions.push(x);

    const projectName = event.p !== undefined ? projectNames[event.p] : undefined;
    const tooltip = `${eventType}${event.v ? `: ${event.v}` : ''}${projectName ? ` (${projectName})` : ''}`;

    eventMarkers += `
      <text x="${x}" y="${margin.top - 8}" text-anchor="middle" font-size="11"
            fill="var(--accent)" class="event-marker">
        ${eventIcons[eventType] || '•'}
        <title>${tooltip}</title>
      </text>`;
  }

  return `<svg viewBox="0 0 ${width} ${height}" class="timeline">${bars}${eventMarkers}</svg>`;
}
```

### 3.8 Session Fingerprints

```typescript
interface SessionFingerprintProps {
  sessions: WrappedStoryV3['sf'];
  projectNames: string[];
  maxVisible?: number;
}

function renderSessionFingerprints({
  sessions,
  projectNames,
  maxVisible = 10
}: SessionFingerprintProps): string {
  const visible = sessions.slice(0, maxVisible);
  const cellSize = 7;
  const fpWidth = cellSize * 4;
  const fpHeight = cellSize * 2;
  const itemWidth = 42;

  const fingerprints = visible.map((s, idx) => {
    let cells = '';
    for (let i = 0; i < 8; i++) {
      const row = Math.floor(i / 4);
      const col = i % 4;
      const intensity = s.fp[i];
      cells += `
        <rect x="${col * cellSize}" y="${row * cellSize}"
              width="${cellSize - 1}" height="${cellSize - 1}"
              fill="rgba(212, 165, 116, ${0.1 + intensity * 0.9})" rx="1"/>`;
    }

    const projectName = projectNames[s.pi] || 'Unknown';
    const tooltip = `${projectName}: ${s.m} msgs, ${formatDuration(s.d)}${s.a ? ' (agent)' : ''}`;

    return `
      <g class="fingerprint" transform="translate(${idx * itemWidth}, 0)">
        <svg x="5" y="0" width="${fpWidth}" height="${fpHeight}">${cells}</svg>
        <text x="${itemWidth/2}" y="${fpHeight + 10}" text-anchor="middle"
              font-size="7" fill="var(--text-muted)">${s.id}</text>
        <title>${tooltip}</title>
      </g>`;
  });

  const totalWidth = visible.length * itemWidth;
  return `
    <div class="session-fingerprints-container">
      <svg viewBox="0 0 ${totalWidth} ${fpHeight + 14}" width="${totalWidth}" height="${fpHeight + 14}">
        ${fingerprints.join('')}
      </svg>
    </div>`;
}
```

---

## Phase 4: Responsive UI Design

### 4.1 Breakpoints

| Breakpoint | Width | Name | Layout Strategy |
|------------|-------|------|-----------------|
| `xs` | 0-374px | Mobile S | Single column, card flow, minimal chrome |
| `sm` | 375-479px | Mobile M | Single column, card flow |
| `md` | 480-767px | Mobile L / Small tablet | Single column, slightly larger viz |
| `lg` | 768-1023px | Tablet | 2-column option, card flow default |
| `xl` | 1024-1439px | Desktop | Dashboard or card toggle |
| `xxl` | ≥1440px | Desktop L | Dashboard with expanded visualizations |

### 4.2 Visualization Scaling

| Visualization | xs-sm (<480) | md-lg (480-1023) | xl+ (≥1024) |
|--------------|--------------|------------------|-------------|
| Heatmap | 290×100, no hour labels | 340×115 | 400×140 |
| Timeline | 100% width, 110px | 100%, 125px | 500×130 |
| Session Histogram | 100%, 70px | 100%, 80px | 280×80 |
| Agent Histogram | 100%, 70px | 100%, 80px | 280×80 |
| Treemap | Top 5 + Other, 100%×150 | Top 8, 100%×180 | All (max 12), 400×200 |
| Trait Radar | **6 traits**, 220×220 | 8 traits, 260×260 | 10 traits, 280×280 |
| Trait Bars | 6 traits, fallback | - | - |
| Co-occurrence | **List view** | Simple graph, 260×180 | Full graph, 300×200 |
| Slope Graph | 260×160 | 280×180 | 300×200 |
| Fingerprints | 5 visible, scroll | 7 visible | 10 visible |

### 4.3 Mobile-Specific Adaptations

**Trait Radar → Bar Chart (xs-sm):**
```css
@media (max-width: 479px) {
  .trait-radar { display: none; }
  .trait-bars { display: block; }
}
@media (min-width: 480px) {
  .trait-radar { display: block; }
  .trait-bars { display: none; }
}
```

**Co-occurrence Graph → List (xs-md):**
```css
@media (max-width: 767px) {
  .cooccurrence-graph { display: none; }
  .cooccurrence-list { display: block; }
}
```

**Fingerprints Horizontal Scroll:**
```css
.session-fingerprints-container {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
```

### 4.4 Card Flow Definition

**Card Sequence (all viewports):**

| # | Card ID | Title | Content | Skip Condition |
|---|---------|-------|---------|----------------|
| 1 | `welcome` | "Your {year}" | Name, core stats summary | Never |
| 2 | `rhythm` | "Your Rhythm" | 7×24 Heatmap + peak time insight | Never |
| 3 | `timeline` | "Your Year" | Monthly timeline + event markers | Never |
| 4 | `sessions` | "Session Patterns" | Duration + Agent ratio histograms | Never |
| 5 | `traits` | "Your Profile" | Radar (desktop) or Bars (mobile) | Never |
| 6 | `projects` | "Your Projects" | Treemap + top project callout | p < 2 |
| 7 | `connections` | "Project Flow" | Co-occurrence graph/list | p < 3 |
| 8 | `growth` | "Year over Year" | Slope graph | No yoy data |
| 9 | `fingerprints` | "Top Sessions" | Session fingerprint grid | s < 3 |
| 10 | `share` | "Share Your Story" | Share buttons, print, copy URL | Never |

**Navigation:**
- **Mobile**: Swipe left/right, dot indicators, edge tap zones
- **Desktop**: Arrow keys, click dots, optional auto-advance
- **Keyboard**: Numbers 1-0 jump to cards

### 4.5 Card Playback Controls

> **STATUS: FUTURE WORK** - Not yet implemented. Current implementation uses manual navigation only.

The card flow supports pause/play functionality for users who want to study visualizations.

**Control States:**
| State | Icon | Behavior |
|-------|------|----------|
| Playing | ▐▐ (pause) | Auto-advance every 5s, tap to pause |
| Paused | ▶ (play) | Manual navigation only, tap to resume |

**Pause Triggers:**
- Tap pause button (bottom center, near dots)
- Any swipe gesture (user taking control)
- Keyboard navigation (←/→ arrows)
- Touch/click on visualization (inspecting detail)

**Resume Triggers:**
- Tap play button
- Press Space key
- 30s idle timeout (optional, configurable)

**Visual Feedback:**
```
Paused state:
┌─────────────────────────┐
│                         │
│   [Card Content]        │
│                         │
│                         │
│   ▶  ● ○ ○ ○ ○ ○       │
│   ↑ Play button         │
└─────────────────────────┘

Playing state:
┌─────────────────────────┐
│                         │
│   [Card Content]        │
│                         │
│        ═══════▶ 3s      │  ← Progress bar (optional)
│   ▐▐ ● ○ ○ ○ ○ ○       │
│   ↑ Pause button        │
└─────────────────────────┘
```

**Implementation:**
```typescript
interface CardFlowState {
  currentIndex: number;
  isPlaying: boolean;
  autoAdvanceDelay: number;  // ms, default 5000
  idleResumeTimeout: number; // ms, default 30000, 0 = disabled
}

function togglePlayback(state: CardFlowState): CardFlowState {
  return { ...state, isPlaying: !state.isPlaying };
}

function handleUserInteraction(state: CardFlowState): CardFlowState {
  // Pause on any user navigation
  return { ...state, isPlaying: false };
}
```

### 4.6 Touch Interactions

| Gesture | Element | Action |
|---------|---------|--------|
| Swipe left | Card | Next card |
| Swipe right | Card | Previous card |
| Tap | Heatmap cell | Show tooltip with value |
| Tap | Treemap rect | Highlight project, show stats |
| Tap | Timeline event | Show event detail |
| Tap | Fingerprint | Show session detail modal |
| Long press | Any stat | Copy value to clipboard |
| Pinch | Heatmap | Zoom in/out (optional) |
| Double tap | Zoomed viz | Reset zoom |

### 4.6 Desktop Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Header: Claude Code Wrapped {year}              [Name]    [Card View] [Print]  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────────────────┐  ┌──────────────────────────────────────────┐│
│  │ CORE STATS                   │  │ ACTIVITY HEATMAP                         ││
│  │ 5,316 messages  312 hours    │  │ [7×24 grid - 400×140]                    ││
│  │ 70 sessions     4 projects   │  │                                          ││
│  │ 45 days active               │  │ Peak: Tuesday 10am                       ││
│  └──────────────────────────────┘  └──────────────────────────────────────────┘│
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────────┤
│  │ TIMELINE + EVENTS                                                           ││
│  │ [Monthly bars with event markers - full width × 130]                        ││
│  └──────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐ ┌─────────────────┐ ┌──────────────────────────────────────┤
│  │ SESSION DIST    │ │ AGENT RATIO     │ │ TRAIT PROFILE (Radar)               ││
│  │ [histogram]     │ │ [histogram]     │ │ [10-axis radar - 280×280]           ││
│  │ 280×80          │ │ 280×80          │ │                                      ││
│  └─────────────────┘ └─────────────────┘ └──────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────────────────────────┐ ┌────────────────────────────────────┤
│  │ ALL PROJECTS (Treemap)               │ │ CO-OCCURRENCE GRAPH                ││
│  │ [squarified treemap - 400×200]       │ │ [circular layout - 300×200]        ││
│  │                                       │ │                                    ││
│  └──────────────────────────────────────┘ └────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────────────────────────┐ ┌────────────────────────────────────┤
│  │ YEAR OVER YEAR (if available)        │ │ TOP SESSIONS (Fingerprints)        ││
│  │ [slope graph - 300×200]              │ │ [10 fingerprints - full width]     ││
│  └──────────────────────────────────────┘ └────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────────┤
│  │ TRAIT SCORES: ad:0.73 sp:0.81 fc:0.45 cc:0.89 wr:0.23 bs:0.62 cs:0.34 ...  ││
│  └──────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Footer: [Share] [Copy URL] [Download PDF] [View as Cards]                      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.7 Mobile Card Layouts

**Card: Welcome (xs-sm)**
```
┌─────────────────────────┐
│                         │
│   CLAUDE CODE WRAPPED   │
│         2025            │
│                         │
│      [User Name]        │
│                         │
│   ┌─────────────────┐   │
│   │    5,316        │   │
│   │   messages      │   │
│   └─────────────────┘   │
│                         │
│   312 hrs · 70 sessions │
│   4 projects · 45 days  │
│                         │
│      [tap to begin]     │
│                         │
│         ○ ○ ○ ○ ○       │
└─────────────────────────┘
```

**Card: Rhythm (xs-sm)**
```
┌─────────────────────────┐
│     YOUR RHYTHM         │
├─────────────────────────┤
│                         │
│  ┌───────────────────┐  │
│  │ [Heatmap 290×100] │  │
│  │ Mon ░░▓▓██▓░░░░░  │  │
│  │ Tue ░░▓▓██▓░░░░░  │  │
│  │ Wed ░░▓███▓▓░░░░  │  │
│  │ Thu ░░▓▓██▓░░░░░  │  │
│  │ Fri ░░░▓▓▓░░░░░░  │  │
│  │ Sat ░░░░░░░░░░░░  │  │
│  │ Sun ░░░░░░░░░░░░  │  │
│  └───────────────────┘  │
│                         │
│  Peak: Tuesday 10am     │
│  You're a morning coder │
│                         │
│       ● ○ ○ ○ ○ ○       │
└─────────────────────────┘
```

**Card: Traits (xs-sm) - Bar Chart Fallback**
```
┌─────────────────────────┐
│     YOUR PROFILE        │
├─────────────────────────┤
│                         │
│  Delegation ████████░ 0.73
│  Deep Work  █████████ 0.81
│  Focus      █████░░░░ 0.45
│  Regularity █████████ 0.89
│  Burst      ██████░░░ 0.62
│  Intensity  █████░░░░ 0.56
│                         │
│  [See all 10 traits →]  │
│                         │
│       ○ ○ ○ ● ○ ○       │
└─────────────────────────┘
```

**Card: Connections (xs-sm) - List Fallback**
```
┌─────────────────────────┐
│     PROJECT FLOW        │
├─────────────────────────┤
│                         │
│  Worked together:       │
│                         │
│  Keyboardia + Auriga    │
│  └─ 12 days             │
│                         │
│  Keyboardia + Lempicka  │
│  └─ 8 days              │
│                         │
│  Auriga + CLI-tools     │
│  └─ 5 days              │
│                         │
│       ○ ○ ○ ○ ○ ● ○     │
└─────────────────────────┘
```

### 4.8 Print Layout (Single Page)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CLAUDE CODE WRAPPED 2025                                        [Name]    │
├─────────────────────────────────────────────────────────────────────────────┤
│  5,316 messages · 312 hours · 70 sessions · 4 projects · 45 days active    │
├───────────────────────────────────┬─────────────────────────────────────────┤
│                                   │                                         │
│  ACTIVITY HEATMAP                 │  YEARLY TIMELINE                        │
│  ┌─────────────────────────────┐  │  ★        ◆            ▲        ●───○  │
│  │ [7×24 grid, grayscale]      │  │  ▂▃▅▇█▆▄▃▂▁▂▃                          │
│  │ 400×120                     │  │  J F M A M J J A S O N D               │
│  └─────────────────────────────┘  │                                         │
│                                   ├─────────────────────────────────────────┤
│  SESSION DISTRIBUTION             │  AGENT RATIO DISTRIBUTION               │
│  ┌─────────────────────────────┐  │  ┌─────────────────────────────────┐   │
│  │ ▁▂▅▇█▅▂▁░░                  │  │  │ ▁▂▅▇██▇▅▂▁                      │   │
│  │ <15m ············· >48h     │  │  │ 0% ················· 100%       │   │
│  └─────────────────────────────┘  │  └─────────────────────────────────┘   │
│                                   │                                         │
├───────────────────────────────────┼─────────────────────────────────────────┤
│                                   │                                         │
│  ALL PROJECTS                     │  TRAIT PROFILE                          │
│  ┌─────────────────────────────┐  │  ┌─────────────────────────────────┐   │
│  │ [Treemap, grayscale]        │  │  │ [10-axis radar]                 │   │
│  │ 340×160                     │  │  │ 240×240                         │   │
│  └─────────────────────────────┘  │  └─────────────────────────────────┘   │
│                                   │                                         │
├───────────────────────────────────┴─────────────────────────────────────────┤
│  TOP SESSIONS: [▓▓░░] [░▓▓░] [▓░░▓] [░▓░▓] [▓▓▓░] [░░▓▓] [▓░▓░] [░▓▓▓]    │
│                abc1    def2    ghi3    jkl4    mno5    pqr6    stu7   vwx8  │
├─────────────────────────────────────────────────────────────────────────────┤
│  SCORES: Delegation 0.73 │ Deep Work 0.81 │ Focus 0.45 │ Regularity 0.89   │
│          Weekend 0.23 │ Burst 0.62 │ Switching 0.34 │ Verbose 0.71 │ ...   │
├─────────────────────────────────────────────────────────────────────────────┤
│  Generated by claude-history-explorer · Data encoded in URL · No server    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.9 Bento Box Layout (Dense 1-Pager)

> **STATUS: FUTURE WORK** - Not yet implemented. Current implementation uses scrollable card flow only.

Inspired by Apple's product page layouts, the Bento Box view presents all visualizations in a dense, information-rich grid that rewards close inspection. This is the **Tufte-optimized** view: maximum data-ink ratio, minimal navigation overhead.

**Design Principles:**
- Every pixel earns its place
- No animation, no auto-advance—static contemplation
- Information hierarchy through size, not sequence
- Accessible via `?view=bento` URL parameter or toggle button

**Grid Structure (12-column base):**

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  CLAUDE CODE WRAPPED 2025                                    [Cards] [Bento] [Print] │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌────────────────────────────────────┐  ┌────────────────────────────────────────┐ │
│  │ ████  5,316                        │  │ ACTIVITY HEATMAP                       │ │
│  │ ████  messages                     │  │ ┌──────────────────────────────────┐   │ │
│  │ ████                               │  │ │ M ░░▓▓██▓▓░░░░░░░░░░░░░░        │   │ │
│  │ ████  312 hours · 70 sessions      │  │ │ T ░░▓▓████▓▓░░░░░░░░░░░░        │   │ │
│  │ ████  4 projects · 45 days         │  │ │ W ░░░▓████▓░░░░░░░░░░░░░        │   │ │
│  │                                    │  │ │ T ░░▓▓██▓▓░░░░░░░░░░░░░░        │   │ │
│  │  "A Deep Diver"                    │  │ │ F ░░░▓▓▓░░░░░░░░░░░░░░░░        │   │ │
│  │                                    │  │ │ S ░░░░░░░░░░░░░░░░░░░░░░        │   │ │
│  └────────────────────────────────────┘  │ │ S ░░░░░░░░░░░░░░░░░░░░░░        │   │ │
│                                          │ └──────────────────────────────────┘   │ │
│  ┌────────────────────────────────────┐  │ Peak: Tuesday 10am                     │ │
│  │ TIMELINE + KEY MOMENTS             │  └────────────────────────────────────────┘ │
│  │ ★        ◆            ▲    ●───○   │                                             │
│  │ █▃▅▇████▇▆▅▄▃▂▁▂▃▄▅▆▇████▇▆▅▄▃▂▁  │  ┌────────────────────────────────────────┐ │
│  │ J  F  M  A  M  J  J  A  S  O  N  D │  │ TRAIT PROFILE                          │ │
│  │                                    │  │        Delegation                       │ │
│  │ 🔥 Peak: Mar 15 (142 msgs)         │  │           ╱╲                            │ │
│  │ 🏆 Milestone: 1K msgs (Feb 3)      │  │      Deep╱  ╲Focus                      │ │
│  │ 🚀 7-day streak (Apr 1-7)          │  │   Work ╱    ╲                           │ │
│  └────────────────────────────────────┘  │       ╲      ╱                          │ │
│                                          │ Burst  ╲____╱  Regularity               │ │
│  ┌─────────────────┐ ┌─────────────────┐ │        Intensity                        │ │
│  │ SESSION LENGTH  │ │ AGENT USAGE     │ │                                         │ │
│  │ ▁▂▅▇█▅▂▁░░      │ │ ▁▂▅▇██▇▅▂▁      │ │ ad:73 sp:81 fc:45 cc:89 bs:62 ri:56   │ │
│  │ <15m····>48h    │ │ 0%·········100% │ └────────────────────────────────────────┘ │
│  └─────────────────┘ └─────────────────┘                                            │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────────┤
│  │ PROJECTS (by messages)                                                           │
│  │ ┌───────────────────────────────┬─────────────────────┬─────────────┬──────────┐│
│  │ │                               │                     │             │          ││
│  │ │    Keyboardia                 │    Auriga           │ Lempicka    │ CLI-tools││
│  │ │    2,341 msgs · 156h          │    1,456 · 89h      │ 823 · 41h   │ 412 · 22h││
│  │ │                               │                     │             │          ││
│  │ └───────────────────────────────┴─────────────────────┴─────────────┴──────────┘│
│  └──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌────────────────────────────────────┐  ┌────────────────────────────────────────┐ │
│  │ PROJECT CO-OCCURRENCE              │  │ TOP SESSIONS                           │ │
│  │                                    │  │                                        │ │
│  │        Keyboardia                  │  │ [▓▓░░][░▓▓░][▓░░▓][░▓░▓][▓▓▓░]       │ │
│  │           ╱╲                       │  │  abc1   def2  ghi3   jkl4  mno5        │ │
│  │    12d╱    ╲8d                     │  │                                        │ │
│  │      ╱        ╲                    │  │ [░░▓▓][▓░▓░][░▓▓▓][▓░░░][░░░▓]       │ │
│  │ Auriga────────Lempicka             │  │  pqr6   stu7  vwx8   yza9  bcd0        │ │
│  │        5d                          │  │                                        │ │
│  └────────────────────────────────────┘  └────────────────────────────────────────┘ │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────────┤
│  │ wrapped-claude-codes.adewale-883.workers.dev · All data encoded in URL · No server│
│  └──────────────────────────────────────────────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Bento Box CSS Grid:**
```css
.bento-grid {
  display: grid;
  gap: 16px;
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;

  /* 12-column base grid */
  grid-template-columns: repeat(12, 1fr);
  grid-template-rows: auto;

  /* Named areas for flexible positioning */
  grid-template-areas:
    "hero   hero   hero   hero   heatmap heatmap heatmap heatmap heatmap heatmap heatmap heatmap"
    "timeline timeline timeline timeline timeline timeline timeline traits traits traits traits traits"
    "sess   sess   sess   agent  agent  agent  traits traits traits traits traits traits"
    "treemap treemap treemap treemap treemap treemap treemap treemap treemap treemap treemap treemap"
    "cooc   cooc   cooc   cooc   cooc   cooc   fingers fingers fingers fingers fingers fingers"
    "footer footer footer footer footer footer footer footer footer footer footer footer";
}

.bento-hero { grid-area: hero; }
.bento-heatmap { grid-area: heatmap; }
.bento-timeline { grid-area: timeline; }
.bento-traits { grid-area: traits; }
.bento-sessions { grid-area: sess; }
.bento-agent { grid-area: agent; }
.bento-treemap { grid-area: treemap; }
.bento-cooccurrence { grid-area: cooc; }
.bento-fingerprints { grid-area: fingers; }
.bento-footer { grid-area: footer; }

/* Dense styling */
.bento-grid .bento-cell {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 16px;
  overflow: hidden;
}

.bento-cell h3 {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  margin-bottom: 8px;
}
```

**Responsive Bento (Tablet):**
```css
@media (max-width: 1024px) {
  .bento-grid {
    grid-template-columns: repeat(6, 1fr);
    grid-template-areas:
      "hero   hero   hero   heatmap heatmap heatmap"
      "timeline timeline timeline timeline timeline timeline"
      "traits traits traits traits traits traits"
      "sess   sess   sess   agent  agent  agent"
      "treemap treemap treemap treemap treemap treemap"
      "cooc   cooc   cooc   fingers fingers fingers";
  }
}
```

**Responsive Bento (Mobile):**
On mobile (< 768px), Bento collapses to a scrollable single-column layout, maintaining density but allowing vertical scroll:

```css
@media (max-width: 767px) {
  .bento-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .bento-cell {
    width: 100%;
  }
}
```

**URL Parameter:**
```
/wrapped?d=...&view=bento    → Bento box layout
/wrapped?d=...&view=cards    → Card flow (default)
/wrapped?d=...&view=print    → Print-optimized
```

**Toggle Button:**
Desktop header includes a view toggle:
```html
<div class="view-toggle">
  <button class="active" data-view="cards">Cards</button>
  <button data-view="bento">Bento</button>
  <button data-view="print">Print</button>
</div>
```

### 4.10 CSS Variables for Theming

```css
:root {
  /* Colors */
  --bg-dark: #0a0a0a;
  --bg-card: #141414;
  --bg-card-hover: #1a1a1a;
  --text-primary: #ffffff;
  --text-secondary: #a0a0a0;
  --text-muted: #666666;
  --accent: #d4a574;
  --accent-light: #e5c9a8;
  --accent-dim: rgba(212, 165, 116, 0.3);
  --border: #2a2a2a;
  --success: #22c55e;
  --warning: #f59e0b;
  --error: #ef4444;

  /* Typography */
  --font-display: 'Space Grotesk', system-ui, sans-serif;
  --font-body: 'Source Sans 3', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  /* Spacing */
  --card-padding: 24px;
  --card-radius: 16px;
  --viz-gap: 16px;
}

@media (max-width: 479px) {
  :root {
    --card-padding: 16px;
    --card-radius: 12px;
    --viz-gap: 12px;
  }
}

@media print {
  :root {
    --bg-dark: #ffffff;
    --bg-card: #ffffff;
    --text-primary: #000000;
    --text-secondary: #333333;
    --text-muted: #666666;
    --accent: #333333;
    --border: #cccccc;
  }
}
```

---

## Phase 5: Implementation Checklist

### 5.1 Python CLI Updates

- [ ] Create `SessionInfoV3` dataclass with `project_name` field
- [ ] Create `ProjectStats` dataclass
- [ ] Add `compute_activity_heatmap()` to history.py
- [ ] Add `compute_distribution()` with `bisect_right`
- [ ] Add `compute_session_duration_distribution()`
- [ ] Add `compute_agent_ratio_distribution()`
- [ ] Add `compute_trait_scores()` with 10 dimensions
- [ ] Add `compute_project_cooccurrence()` with max_edges limit
- [ ] Add `detect_timeline_events()` with priority sorting
- [ ] Add `compute_session_fingerprint()`
- [ ] Add `get_top_session_fingerprints()`
- [ ] Add `rle_encode()`, `rle_decode()`, `rle_encode_if_smaller()`
- [ ] Create `WrappedStoryV3` dataclass with all fields
- [ ] Implement `encode_wrapped_story_v3()` with RLE
- [ ] Implement `decode_wrapped_story_v3()`
- [ ] Update `generate_wrapped_story()` to produce V3
- [ ] Add `--format v2|v3` flag to wrapped command
- [ ] Add `--print` flag for print-optimized output
- [ ] Collect year-over-year comparison data
- [ ] Enforce hard limits (12 projects, 20 edges, 15 events)
- [ ] Write comprehensive unit tests

### 5.2 TypeScript Website Updates

- [ ] Add `WrappedStoryV3` interface to decoder.ts
- [ ] Add `EVENT_TYPES` constant
- [ ] Implement `rleDecode()` function
- [ ] Implement `decodeWrappedStoryV3()` with RLE handling
- [ ] Add helper functions: `truncate()`, `formatNumber()`, `formatDuration()`
- [ ] Create `Heatmap` component with responsive sizing
- [ ] Create `Histogram` component
- [ ] Create `Treemap` component with squarify algorithm
- [ ] Create `SlopeGraph` component
- [ ] Create `CooccurrenceGraph` component
- [ ] Create `CooccurrenceList` fallback for mobile
- [ ] Create `TraitRadar` component with trait subset support
- [ ] Create `TraitBars` fallback for mobile
- [ ] Create `Timeline` component with event markers
- [ ] Create `SessionFingerprints` component with scroll
- [ ] Implement card flow navigation (swipe, keys, dots)
- [ ] Implement card pause/play controls with progress bar
- [ ] Add pause triggers (swipe, keyboard nav, viz interaction)
- [ ] Add idle resume timeout (configurable)
- [ ] Create responsive card layouts for all breakpoints
- [ ] Create dashboard layout for desktop
- [ ] Create Bento Box dense 1-pager layout
- [ ] Implement 12-column CSS Grid for Bento layout
- [ ] Add responsive Bento for tablet (6-column)
- [ ] Add responsive Bento for mobile (single-column scroll)
- [ ] Create print stylesheet
- [ ] Add "Download as PDF" button (browser print)
- [ ] Add view toggle (cards ↔ bento ↔ print) on desktop
- [ ] Support `?view=bento` URL parameter

### 5.3 Testing & Verification

- [ ] Test heatmap with: all zeros, all max, realistic patterns, edge hours
- [ ] Test distribution bucketing with edge cases (0, exactly on threshold, max)
- [ ] Test each trait score independently with synthetic data
- [ ] Test co-occurrence with: 2 projects, 12 projects, 0 overlap, full overlap
- [ ] Test timeline event detection and priority sorting
- [ ] Test RLE: beneficial case, non-beneficial case, empty array
- [ ] Test V3 encode/decode round-trip with all field types
- [ ] Test payload size stays under 2KB with max data
- [ ] Visual regression tests for all components at all breakpoints
- [ ] Test print layout at 100%, 75%, 50% browser zoom
- [ ] Test card navigation: swipe, keyboard, dots
- [ ] Test card pause/play: manual pause, auto-pause on interaction, idle resume
- [ ] Test Bento layout at all breakpoints (desktop, tablet, mobile)
- [ ] Test view toggle persistence and URL parameter
- [ ] Test on: iPhone SE, iPhone 14, iPad, 1080p desktop, 1440p desktop
- [ ] Accessibility: screen reader, keyboard-only, reduced motion

### 5.4 Performance Targets

| Metric | Target | Test Method |
|--------|--------|-------------|
| V3 payload size | < 2KB | Unit test with max data |
| Initial render (mobile) | < 200ms | Lighthouse |
| Card transition | < 100ms | Manual timing |
| Heatmap render | < 16ms | Performance.now() |
| Treemap layout | < 50ms | Performance.now() |
| Total JS bundle | < 50KB gzipped | Build output |

---

## Phase 6: Migration (Completed)

**Status: V3 is now the only supported version.**

V1 and V2 formats have been fully removed from both the Python encoder and TypeScript decoder.
Legacy URLs will show an error message prompting users to regenerate their Wrapped.

### URL Format

The V3 URL format uses a query parameter:

```
https://wrapped-claude-codes.adewale-883.workers.dev/wrapped?d={encoded}
```

Optional view parameter:
- `?view=bento` (default) - Interactive dashboard
- `?view=print` - Print-friendly single page

### Breaking Changes from V2

- URL structure changed from `/{year}/{encoded}` to `/wrapped?d={encoded}`
- V1/V2 encoded data will not decode (error message shown)
- Project name limit increased from 20 to 50 characters
- All trait scores are now integers 0-100 (not floats)
- Story mode view removed (only Bento and Print views remain)

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Data-ink ratio | > 0.8 | Manual audit: pixels of data vs decoration |
| Payload size | < 1.8KB typical, < 2KB max | Automated test |
| Render time (FCP) | < 1.5s on 3G | Lighthouse |
| Information density | 5× V2 | Count distinct data points: V2 ~15, V3 ~75 |
| Mobile usability | Score > 90 | Lighthouse |
| Print quality | Clean at 100% zoom | Manual test |
| Card completion rate | > 80% reach share card | Analytics (if added) |

---

## Appendix: References

- Tufte, E. (2001). *The Visual Display of Quantitative Information*
- Tufte, E. (1997). *Visual Explanations*
- Bremer, N. (2016). "Squarified Treemaps" - https://www.win.tue.nl/~vanwijk/stm.pdf
- Cairo, A. (2012). *The Functional Art*
- WCAG 2.1 Guidelines - https://www.w3.org/WAI/WCAG21/quickref/
- Apple HIG: Touch Targets - https://developer.apple.com/design/human-interface-guidelines/
