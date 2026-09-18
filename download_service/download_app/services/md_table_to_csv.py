"""Extract the first pipe-table from markdown and convert it to CSV."""

import csv
import io
import re


_SEPARATOR_RE = re.compile(
    r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$"
)


def _parse_row(line: str) -> list[str]:
    """Split a pipe-delimited row into stripped cell values."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def extract_first_table_as_csv(md_content: str) -> str | None:
    """Return CSV text for the first markdown pipe-table, or None if no table found."""
    lines = md_content.splitlines()

    for i, line in enumerate(lines):
        if not _SEPARATOR_RE.match(line):
            continue

        if i == 0:
            continue

        header_line = lines[i - 1]
        if "|" not in header_line:
            continue

        headers = _parse_row(header_line)

        body_rows: list[list[str]] = []
        for row_line in lines[i + 1:]:
            row_stripped = row_line.strip()
            if not row_stripped or "|" not in row_stripped:
                break
            body_rows.append(_parse_row(row_stripped))

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        writer.writerows(body_rows)
        return buf.getvalue()

    return None
