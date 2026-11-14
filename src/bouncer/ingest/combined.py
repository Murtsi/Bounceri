"""Standard Apache/nginx combined lines; missing fields stay explicitly unavailable."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

QUOTED = r'((?:[^"\\]|\\.)*)'
COMBINED = re.compile(
    r'^(\S+) (\S+) (\S+) \[(\d{2})/([A-Za-z]{3})/(\d{4}):'
    r'(\d{2}):(\d{2}):(\d{2}) ([+-])(\d{2})(\d{2})\] "'
    + QUOTED + r'" (\d{3}) (\d+|-) "' + QUOTED + r'" "' + QUOTED + r'"\s*$'
)
MONTHS = {month: index + 1 for index, month in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
)}


def _unquote(value: str) -> str:
    return re.sub(r'\\(["\\])', r"\1", value)


def parse_combined_line(line: str) -> dict:
    match = COMBINED.fullmatch(line)
    if match is None:
        raise ValueError("invalid_record")
    (ip, ident, user, day, month, year, hour, minute, second, sign, offset_h, offset_m,
     request, status, size, referer, agent) = match.groups()
    try:
        if int(offset_h) > 23 or int(offset_m) > 59:
            raise ValueError("invalid_timestamp")
        offset = timedelta(hours=int(offset_h), minutes=int(offset_m))
        zone = timezone(offset if sign == "+" else -offset)
        timestamp = datetime(int(year), MONTHS[month], int(day), int(hour), int(minute),
                             int(second), tzinfo=zone).astimezone(UTC).isoformat()
        method, uri, protocol = _unquote(request).split(" ")
        if not protocol.startswith("HTTP/"):
            raise ValueError("invalid_record")
    except (KeyError, ValueError) as exc:
        raise ValueError("invalid_record") from exc
    record = {
        "ts": timestamp,
        "request": {"client_ip": ip, "method": method, "uri": uri,
                    "headers": {"User-Agent": _unquote(agent)} if agent != "-" else {}},
        "status": int(status),
        "_headers_incomplete": True,
        "resp_headers": {},
        # Authentication identity and referer are intentionally discarded.
        "_unmapped_fields": int(ident != "-") + int(user != "-") + int(referer != "-"),
    }
    if size != "-":
        record["size"] = int(size)
    return record
