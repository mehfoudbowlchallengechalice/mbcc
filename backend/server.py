"""WSGI read-only API. For local use: python3 -m backend.server [--demo]."""
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, quote
from urllib.request import Request, urlopen
from wsgiref.simple_server import make_server

from backend.sheets_adapter import WORKSHEETS, build_snapshot, playoff_history_standings
from backend.groups import GroupError, combine_snapshots, normalize_group

logger = logging.getLogger("mbcc")
_lock = threading.Lock()
_cache = {}
HISTORY_WORKSHEETS = {"basic_history", "agg_history", "season_history"}
OPTIONAL_WORKSHEETS = ("live_scores_and_games",)
UPDATE_WORKSHEETS = ("todays_update",)
PLAYOFF_HISTORY_WORKSHEETS = ("playoff_history",)
DEFAULT_PLAYOFF_HISTORY_SHEET_ID = "1Iwl1WEzLEXu05ZtFcfZovWwQsECNy8LH3II760C-w2E"


def worksheet_titles(group="default"):
    """Allow Streamlit connection aliases to map to actual Google tab names."""
    mapping = os.environ.get("MBCC_WORKSHEET_TITLES", "{}")
    if group == "sub":
        mapping = os.environ.get("MBCC_SUB_WORKSHEET_TITLES", mapping)
    try:
        titles = json.loads(mapping)
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


def spreadsheet_groups(group="default"):
    """Use the Streamlit workbook; optionally route history to another file."""
    if group == "sub":
        challenge_id = os.environ.get("MBCC_SUB_CHALLENGE_SHEET_ID", "").strip()
        history_id = os.environ.get("MBCC_SUB_HISTORY_SHEET_ID") or challenge_id
        if not challenge_id:
            raise GroupError("The subgroup is not configured. Set MBCC_SUB_CHALLENGE_SHEET_ID on the backend and share that spreadsheet with its reader service account.")
    else:
        challenge_id = os.environ.get("MBCC_CHALLENGE_SHEET_ID") or os.environ.get("GOOGLE_SHEETS_ID")
        history_id = os.environ.get("MBCC_HISTORY_SHEET_ID") or challenge_id
    if not challenge_id:
        raise RuntimeError("MBCC_CHALLENGE_SHEET_ID is required")
    groups = {}
    requested = WORKSHEETS + OPTIONAL_WORKSHEETS if os.environ.get("MBCC_LIVE_SCORES_ENABLED", "1") == "1" else WORKSHEETS
    updates_setting = "MBCC_SUB_UPDATES_ENABLED" if group == "sub" else "MBCC_UPDATES_ENABLED"
    if os.environ.get(updates_setting, "0") == "1":
        requested += UPDATE_WORKSHEETS
    for sheet in requested:
        file_id = history_id if sheet in HISTORY_WORKSHEETS else challenge_id
        groups.setdefault(file_id, []).append(sheet)
    return groups


def fetch_snapshot(group="default"):
    if os.environ.get("MBCC_DEMO") == "1":
        if group != "default":
            raise GroupError("The bundled demo has only the main group. Use default or connect to a configured live subgroup.")
        snapshot = json.loads((Path(__file__).resolve().parents[1] / "ios/MBCC/demo.json").read_text())
        return dict(snapshot, group=group)
    groups = spreadsheet_groups(group)
    titles = worksheet_titles(group)
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
    season = os.environ.get("MBCC_SEASON", "MBCC 15 · 2026–27")
    snapshot = build_snapshot(tables, season=os.environ.get("MBCC_SUB_SEASON", season) if group == "sub" else season)
    snapshot["group"] = group
    if group == "sub":
        playoff_id = os.environ.get("MBCC_SUB_PLAYOFF_HISTORY_SHEET_ID", "").strip()
        playoff_enabled = bool(playoff_id)
    else:
        playoff_id = os.environ.get("MBCC_PLAYOFF_HISTORY_SHEET_ID") or DEFAULT_PLAYOFF_HISTORY_SHEET_ID
        playoff_enabled = os.environ.get("MBCC_PLAYOFF_HISTORY_ENABLED", "0") == "1"
    if playoff_enabled:
        try:
            playoff_tables = read_worksheets(playoff_id,
                                             PLAYOFF_HISTORY_WORKSHEETS, top_three=True)
            snapshot["playoffStandings"] = playoff_history_standings(playoff_tables["playoff_history"])
        except Exception as exc:
            logger.error("Playoff history load failed (%s)", type(exc).__name__)
            snapshot["playoffStandingsError"] = "Couldn’t load all-time playoff standings from the history spreadsheet."
    return snapshot


def snapshot_bytes(group="default"):
    def cached(selected):
        entry = _cache.get(selected)
        if entry is None or time.monotonic() >= entry[0]:
            expires = None
            if selected == "default+sub":
                # Reuse independently cached sources; a failed merge cannot
                # replace either group's last successful cached response.
                snapshot = combine_snapshots(json.loads(cached("default")), json.loads(cached("sub")))
                expires = min(_cache["default"][0], _cache["sub"][0])
            else:
                snapshot = fetch_snapshot() if selected == "default" else fetch_snapshot(selected)
            _cache[selected] = (expires if expires is not None else time.monotonic() + 60,
                                json.dumps(snapshot, allow_nan=False).encode())
        return _cache[selected][1]
    with _lock:
        return cached(group)


def application(environ, start_response):
    status = "200 OK"
    if environ.get("REQUEST_METHOD") not in {"GET", "HEAD"}:
        status, body = "405 Method Not Allowed", b'{"error":"Read-only API"}'
    elif environ.get("PATH_INFO") == "/health":
        body = b'{"status":"ok"}'
    elif environ.get("PATH_INFO") == "/api/snapshot":
        try:
            values = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True).get("group", [""])
            if len(values) != 1:
                raise GroupError("Supply only one group keyword.")
            group = normalize_group(values[0])
        except GroupError as exc:
            status, body = "400 Bad Request", json.dumps({"error": str(exc)}).encode()
        else:
            try:
                body = snapshot_bytes() if group == "default" else snapshot_bytes(group)
            except GroupError as exc:
                status, body = "409 Conflict", json.dumps({"error": str(exc)}).encode()
            except Exception as exc:
                # Never expose credentials, spreadsheet contents, or remote error bodies.
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
