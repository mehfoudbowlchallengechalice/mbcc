"""WSGI read-only API. For local use: python3 -m backend.server [--demo]."""
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from wsgiref.simple_server import make_server

from backend.sheets_adapter import WORKSHEETS, build_snapshot, playoff_history_standings

logger = logging.getLogger("mbcc")
_lock = threading.Lock()
_cache = None
_expires = 0
HISTORY_WORKSHEETS = {"basic_history", "agg_history", "season_history"}
OPTIONAL_WORKSHEETS = ("live_scores_and_games",)
UPDATE_WORKSHEETS = ("todays_update",)
PLAYOFF_HISTORY_WORKSHEETS = ("playoff_history",)
DEFAULT_PLAYOFF_HISTORY_SHEET_ID = "1Iwl1WEzLEXu05ZtFcfZovWwQsECNy8LH3II760C-w2E"


def worksheet_titles():
    """Allow Streamlit connection aliases to map to actual Google tab names."""
    try:
        titles = json.loads(os.environ.get("MBCC_WORKSHEET_TITLES", "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("MBCC_WORKSHEET_TITLES must be a JSON object") from exc
    if not isinstance(titles, dict) or any(
        key not in WORKSHEETS + OPTIONAL_WORKSHEETS + UPDATE_WORKSHEETS + PLAYOFF_HISTORY_WORKSHEETS or not isinstance(value, str) or not value.strip()
        for key, value in titles.items()
    ):
        raise ValueError("Worksheet mapping requires known aliases and nonempty tab names")
    return {name: titles.get(name, "playoff_picks" if name == "playoff_history" else name)
            for name in WORKSHEETS + OPTIONAL_WORKSHEETS + UPDATE_WORKSHEETS + PLAYOFF_HISTORY_WORKSHEETS}


def sheet_range(title):
    return "'" + title.replace("'", "''") + "'"


def spreadsheet_groups():
    """Use the Streamlit workbook; optionally route history to another file."""
    challenge_id = os.environ.get("MBCC_CHALLENGE_SHEET_ID") or os.environ.get("GOOGLE_SHEETS_ID")
    history_id = os.environ.get("MBCC_HISTORY_SHEET_ID") or challenge_id
    if not challenge_id:
        raise RuntimeError("MBCC_CHALLENGE_SHEET_ID is required")
    groups = {}
    requested = WORKSHEETS + OPTIONAL_WORKSHEETS if os.environ.get("MBCC_LIVE_SCORES_ENABLED", "1") == "1" else WORKSHEETS
    if os.environ.get("MBCC_UPDATES_ENABLED", "0") == "1":
        requested += UPDATE_WORKSHEETS
    for sheet in requested:
        file_id = history_id if sheet in HISTORY_WORKSHEETS else challenge_id
        groups.setdefault(file_id, []).append(sheet)
    return groups


def fetch_snapshot():
    if os.environ.get("MBCC_DEMO") == "1":
        return json.loads((Path(__file__).resolve().parents[1] / "ios/MBCC/demo.json").read_text())
    groups = spreadsheet_groups()
    titles = worksheet_titles()
    import google.auth
    from google.auth.transport.requests import Request as AuthRequest
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    auth_request = AuthRequest()
    def bounded_auth_request(*args, **kwargs):
        kwargs.setdefault("timeout", 10)
        return auth_request(*args, **kwargs)
    credentials.refresh(bounded_auth_request)
    tables = {}
    def read_worksheets(spreadsheet_id, worksheets, *, top_three=False):
        query = urlencode([("ranges", sheet_range(titles[sheet]) + ("!1:3" if top_three else "")) for sheet in worksheets]
                          + [("valueRenderOption", "FORMATTED_VALUE")])
        request = Request(f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}/values:batchGet?{query}",
                          headers={"Authorization": f"Bearer {credentials.token}"})
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if exc.code == 400:
                # A Sheets API 400 message describes invalid ranges/parameters.
                # Log it only in server logs; public API responses stay generic.
                try:
                    detail = json.loads(exc.read(8192)).get("error", {}).get("message", "")
                except (ValueError, AttributeError):
                    detail = "No structured Google Sheets error details"
                detail = str(detail).replace("\r", " ").replace("\n", " ")[:500]
                label = "playoff history" if worksheets[0] in PLAYOFF_HISTORY_WORKSHEETS else "history" if worksheets[0] in HISTORY_WORKSHEETS else "challenge"
                logger.error("Sheets rejected the %s workbook request (HTTP 400): %s", label, detail)
            raise
        ranges = payload.get("valueRanges", [])
        if len(ranges) != len(worksheets):
            raise ValueError("Google Sheets returned an incomplete response")
        return {name: value.get("values", []) for name, value in zip(worksheets, ranges)}
    for spreadsheet_id, worksheets in groups.items():
        tables.update(read_worksheets(spreadsheet_id, worksheets))
    snapshot = build_snapshot(tables, season=os.environ.get("MBCC_SEASON", "MBCC 15 · 2026–27"))
    if os.environ.get("MBCC_PLAYOFF_HISTORY_ENABLED", "0") == "1":
        try:
            playoff_tables = read_worksheets(os.environ.get("MBCC_PLAYOFF_HISTORY_SHEET_ID") or DEFAULT_PLAYOFF_HISTORY_SHEET_ID,
                                             PLAYOFF_HISTORY_WORKSHEETS, top_three=True)
            snapshot["playoffStandings"] = playoff_history_standings(playoff_tables["playoff_history"])
        except Exception as exc:
            logger.error("Playoff history load failed (%s)", type(exc).__name__)
            snapshot["playoffStandingsError"] = "Couldn’t load all-time playoff standings from the history spreadsheet."
    return snapshot


def snapshot_bytes():
    global _cache, _expires
    with _lock:
        if _cache is None or time.monotonic() >= _expires:
            _cache = json.dumps(fetch_snapshot(), allow_nan=False).encode()
            _expires = time.monotonic() + 60
        return _cache


def application(environ, start_response):
    status = "200 OK"
    if environ.get("REQUEST_METHOD") not in {"GET", "HEAD"}:
        status, body = "405 Method Not Allowed", b'{"error":"Read-only API"}'
    elif environ.get("PATH_INFO") == "/health":
        body = b'{"status":"ok"}'
    elif environ.get("PATH_INFO") == "/api/snapshot":
        try:
            body = snapshot_bytes()
        except Exception as exc:
            # Never expose credentials, spreadsheet contents, or remote error bodies.
            # Our parser's validation errors identify bad columns/dates/numbers.
            # Never log authentication errors or credential/remote error bodies.
            code = getattr(exc, "code", None)
            validation = str(exc).replace("\r", " ").replace("\n", " ")[:500] if isinstance(exc, ValueError) else ""
            logger.error("Snapshot load failed (%s%s)%s", type(exc).__name__,
                         f": {code}" if isinstance(code, int) else "",
                         f": {validation}" if validation else "")
            status, body = "502 Bad Gateway", b'{"error":"MBCC data is temporarily unavailable"}'
    else:
        status, body = "404 Not Found", b'{"error":"Not found"}'
    headers = [("Content-Type", "application/json; charset=utf-8"),
               ("Content-Length", str(len(body))), ("Cache-Control", "no-store"),
               ("X-Content-Type-Options", "nosniff")]
    if status.startswith("405"):
        headers.append(("Allow", "GET, HEAD"))
    start_response(status, headers)
    return [b"" if environ.get("REQUEST_METHOD") == "HEAD" else body]


if __name__ == "__main__":
    if "--demo" in sys.argv:
        os.environ["MBCC_DEMO"] = "1"
    port = int(os.environ.get("PORT", "8000"))
    print(f"MBCC {'DEMO' if os.environ.get('MBCC_DEMO') == '1' else 'SHEETS'} API: http://127.0.0.1:{port}/api/snapshot", flush=True)
    with make_server("127.0.0.1", port, application) as server:
        server.serve_forever()
