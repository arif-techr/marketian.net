"""Reading imported tables (Excel .xlsx or CSV) and applying the column choices made in the import screen.

Each column is used as one of: "phone", "name", "field" (kept on the contact and usable in messages as
{key}, where key comes from the column heading) or "ignore".
"""
import csv
import datetime
import io
import re
import unicodedata

from .phones import _columns, normalize

MAX_ROWS = 50_000
MAX_COLS = 60
USES = ("phone", "name", "field", "ignore")


class TableError(ValueError):
    """The file can't be read. The message is safe to show."""


def _word_char(ch: str) -> bool:
    # Letters, digits and combining marks: Python's \w misses Bangla vowel signs such as া and ্.
    return ch == "_" or unicodedata.category(ch)[0] in "LNM"


def field_key(label: str) -> str:
    """Column heading -> placeholder name: "Exam Score" -> "exam_score". Bangla headings keep their letters."""
    key = "".join(ch if _word_char(ch) else "_" for ch in str(label).strip().lower())
    key = re.sub(r"_+", "_", key).strip("_")
    return key[:40] or "field"


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))  # Excel stores 8801712345678 and 85 as floats
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d %H:%M") if (v.hour, v.minute) != (0, 0) else v.date().isoformat()
    if isinstance(v, datetime.date):
        return v.isoformat()
    return str(v).strip()


def read_xlsx(data: bytes) -> list[list[str]]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as e:  # zip/xml errors: not a real .xlsx
        raise TableError("That doesn't look like an Excel (.xlsx) file. Save it as .xlsx or CSV and try again.") from e
    try:
        ws = wb.worksheets[0]
        rows = []
        for r in ws.iter_rows(values_only=True):
            cells = [_cell(v) for v in r[:MAX_COLS]]
            if any(cells):
                rows.append(cells)
            if len(rows) > MAX_ROWS:
                raise TableError(f"The sheet has more than {MAX_ROWS:,} rows. Split it into smaller files.")
        return rows
    finally:
        wb.close()


def read_csv_text(text: str) -> list[list[str]]:
    text = text.lstrip("﻿")
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    delimiter = max(",;\t", key=first.count) if any(d in first for d in ",;\t") else ","
    rows = [[c.strip() for c in r[:MAX_COLS]] for r in csv.reader(io.StringIO(text), delimiter=delimiter)]
    rows = [r for r in rows if any(r)]
    if len(rows) > MAX_ROWS:
        raise TableError(f"The file has more than {MAX_ROWS:,} rows. Split it into smaller files.")
    return rows


def read_upload(f) -> list[list[str]]:
    name = (f.name or "").lower()
    data = f.read()
    if name.endswith(".xls"):
        raise TableError("Old Excel files (.xls) can't be read. In Excel use Save As → Excel Workbook (.xlsx) or CSV UTF-8.")
    if name.endswith(".xlsx") or data[:2] == b"PK":
        return read_xlsx(data)
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return read_csv_text(data.decode(enc))
        except UnicodeDecodeError:
            continue
    raise TableError("The file's text can't be read. Save it as CSV UTF-8.")


def guess(header: list[str], default_country_code: str = "") -> tuple[bool, list[str]]:
    """(does the first row look like a heading?, suggested use for each column)."""
    width = len(header)
    looks_like_data = any(normalize(c, default_country_code) for c in header)
    cols = None if looks_like_data else _columns(header)
    uses = ["ignore"] * width
    if cols:
        phones, names = cols
        for i in names:
            uses[i] = "name"
        # The first phone-ish column that isn't just a type label ("Mobile") becomes the phone.
        for i in phones:
            if uses[i] == "ignore":
                uses[i] = "phone"
                break
        return True, uses
    return False, uses


def apply_columns(rows: list[list[str]], uses: list[str], has_header: bool, default_country_code: str = ""):
    """Yields (row_number, phone_or_None, name, {field_key: value}, raw_text) using the chosen column uses."""
    header = rows[0] if has_header and rows else [f"Column {i + 1}" for i in range(max(map(len, rows or [[]])))]
    keys = {i: field_key(header[i] if i < len(header) else f"column_{i + 1}") for i, u in enumerate(uses) if u == "field"}
    phone_cols = [i for i, u in enumerate(uses) if u == "phone"]
    name_cols = [i for i, u in enumerate(uses) if u == "name"]
    start = 1 if has_header else 0
    for n, row in enumerate(rows[start:], start=start + 1):
        cell = lambda i: row[i] if i < len(row) else ""  # noqa: E731
        search = [cell(i) for i in phone_cols] if phone_cols else row
        phone = next((p for c in search if (p := normalize(c, default_country_code))), None)
        name = " ".join(cell(i) for i in name_cols if cell(i))
        if not name_cols:
            name = ""
        values = {k: cell(i) for i, k in keys.items() if cell(i) != ""}
        yield n, phone, name[:120], values, ", ".join(row)[:200]


def field_labels(rows, uses, has_header) -> dict[str, str]:
    """{key: column heading} for the columns used as fields."""
    header = rows[0] if has_header and rows else []
    out = {}
    for i, u in enumerate(uses):
        if u == "field":
            label = header[i] if i < len(header) and header[i] else f"Column {i + 1}"
            out[field_key(label)] = label[:80]
    return out


