"""
SentinelAI — Incident Log Parser
Parses log files (txt, log, json, csv) and extracts error events.
Classifies severity using pattern matching + AI.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("sentinel.incident.parser")

# ── Log Level Patterns ────────────────────────────────────────────────────────
LEVEL_PATTERNS = {
    "FATAL": re.compile(r"\b(FATAL|CRITICAL|PANIC|EMERG)\b", re.IGNORECASE),
    "ERROR": re.compile(r"\b(ERROR|ERR|EXCEPTION|TRACEBACK|STACKTRACE)\b", re.IGNORECASE),
    "WARN":  re.compile(r"\b(WARN|WARNING|CAUTION)\b", re.IGNORECASE),
    "INFO":  re.compile(r"\b(INFO|NOTICE)\b", re.IGNORECASE),
    "DEBUG": re.compile(r"\b(DEBUG|TRACE|VERBOSE)\b", re.IGNORECASE),
}

# ── Timestamp Patterns ────────────────────────────────────────────────────────
TIMESTAMP_PATTERNS = [
    re.compile(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"),
    re.compile(r"(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})"),  # Apache combined log
    re.compile(r"(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"),  # Syslog
]

# ── Error Indicator Patterns ──────────────────────────────────────────────────
ERROR_INDICATORS = re.compile(
    r"\b(error|exception|fail(ed|ure)?|crash|panic|timeout|refused|unreachable|"
    r"OOM|out.of.memory|killed|5\d{2}|traceback|stack.?trace|null.?pointer|"
    r"connection.?refused|too.?many.?connections|deadlock|circuit.?breaker)\b",
    re.IGNORECASE,
)

SERVICE_PATTERNS = re.compile(
    r"\b(payment|auth|gateway|database|postgres|mysql|redis|cache|api|"
    r"frontend|backend|worker|queue|kafka|rabbitmq|nginx|notification|email)\b",
    re.IGNORECASE,
)


class ParsedLogEntry:
    def __init__(
        self,
        message: str,
        level: str = "INFO",
        timestamp: Optional[datetime] = None,
        service_name: Optional[str] = None,
        raw_line: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.level = level
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.service_name = service_name
        self.raw_line = raw_line
        self.metadata = metadata or {}

    @property
    def is_error(self) -> bool:
        return self.level in ("ERROR", "FATAL") or bool(ERROR_INDICATORS.search(self.message))


def detect_level(line: str) -> str:
    """Detect the log level from a raw log line."""
    for level, pattern in LEVEL_PATTERNS.items():
        if pattern.search(line):
            return level
    if ERROR_INDICATORS.search(line):
        return "ERROR"
    return "INFO"


def extract_timestamp(line: str) -> Optional[datetime]:
    """Extract ISO/common timestamp from a log line."""
    for pattern in TIMESTAMP_PATTERNS:
        m = pattern.search(line)
        if m:
            try:
                ts_str = m.group(1)
                # Normalize
                ts_str = ts_str.replace(" ", "T").rstrip("Z")
                return datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                continue
    return None


def extract_service(line: str) -> Optional[str]:
    """Heuristically extract service name from log line."""
    m = SERVICE_PATTERNS.search(line)
    return m.group(1).lower() if m else None


def parse_plain_log(content: str) -> List[ParsedLogEntry]:
    """Parse plain text / .log files."""
    entries = []
    for raw_line in content.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        entry = ParsedLogEntry(
            message=raw_line[:2000],
            level=detect_level(raw_line),
            timestamp=extract_timestamp(raw_line),
            service_name=extract_service(raw_line),
            raw_line=raw_line,
        )
        entries.append(entry)
    return entries


def parse_json_log(content: str) -> List[ParsedLogEntry]:
    """Parse JSON log files (one JSON object per line, or JSON array)."""
    entries = []
    content = content.strip()

    # Try JSON array first
    if content.startswith("["):
        try:
            records = json.loads(content)
            for record in records:
                entries.append(_json_record_to_entry(record))
            return entries
        except json.JSONDecodeError:
            pass

    # Fallback: JSONL (one object per line)
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            entries.append(_json_record_to_entry(record))
        except json.JSONDecodeError:
            # Treat as plain text
            entries.append(ParsedLogEntry(message=line[:2000], level=detect_level(line), raw_line=line))
    return entries


def _json_record_to_entry(record: Dict[str, Any]) -> ParsedLogEntry:
    """Convert a parsed JSON record to a ParsedLogEntry."""
    msg_keys = ["message", "msg", "text", "body", "log", "event"]
    message = ""
    for k in msg_keys:
        if k in record:
            message = str(record[k])
            break
    if not message:
        message = json.dumps(record)[:500]

    level_keys = ["level", "severity", "loglevel", "log_level"]
    level = "INFO"
    for k in level_keys:
        if k in record:
            level = str(record[k]).upper()
            break

    ts_keys = ["timestamp", "time", "ts", "@timestamp", "datetime"]
    timestamp = None
    for k in ts_keys:
        if k in record:
            try:
                ts_val = str(record[k])
                timestamp = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
            break

    service_keys = ["service", "service_name", "app", "application", "component"]
    service = None
    for k in service_keys:
        if k in record:
            service = str(record[k])
            break

    return ParsedLogEntry(
        message=message[:2000],
        level=level,
        timestamp=timestamp,
        service_name=service or extract_service(message),
        raw_line=json.dumps(record)[:1000],
        metadata={k: v for k, v in record.items() if k not in msg_keys + level_keys + ts_keys + service_keys},
    )


def parse_csv_log(content: str) -> List[ParsedLogEntry]:
    """Parse CSV log files."""
    entries = []
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        row_dict = dict(row)
        entries.append(_json_record_to_entry(row_dict))
    return entries


def parse_file(content: str, file_type: str) -> List[ParsedLogEntry]:
    """Main dispatcher — parse file content based on type."""
    if file_type in ("json", "jsonl"):
        return parse_json_log(content)
    elif file_type == "csv":
        return parse_csv_log(content)
    else:
        return parse_plain_log(content)


def classify_severity_from_entries(entries: List[ParsedLogEntry]) -> str:
    """Determine incident P-level from parsed log entries."""
    fatal_count = sum(1 for e in entries if e.level == "FATAL")
    error_count = sum(1 for e in entries if e.level in ("ERROR", "FATAL"))
    total = len(entries)

    if fatal_count > 0:
        return "P1"
    if error_count > 50 or (total > 0 and error_count / total > 0.3):
        return "P1"
    if error_count > 10 or (total > 0 and error_count / total > 0.1):
        return "P2"
    if error_count > 0:
        return "P3"
    return "P4"


def extract_incident_title(entries: List[ParsedLogEntry]) -> str:
    """Generate a concise incident title from parsed entries."""
    error_entries = [e for e in entries if e.is_error]
    if not error_entries:
        return "Unknown incident from log analysis"

    # Pick the most information-rich error message
    best = max(error_entries, key=lambda e: len(e.message))
    msg = best.message[:200]

    service = best.service_name
    if service:
        return f"{service.capitalize()} failure: {msg[:100]}"
    return f"System failure detected: {msg[:120]}"
