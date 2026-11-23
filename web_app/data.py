"""The same display rules as ios/MBCC/Models.swift, without UI dependencies."""
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
DEFAULT_ENDPOINT = "https://mbcc-api-jarvycxodq-ue.a.run.app/api/snapshot"
ROOT = Path(__file__).resolve().parents[1]
CHECKED_FIELDS = (
    ("startTime", "Kickoff"), ("awayTeam", "Away team"), ("homeTeam", "Home team"),
    ("awayScore", "Away score"), ("homeScore", "Home score"), ("pointDifference", "Score difference"),
)


class SnapshotError(ValueError):
    pass


def parse_time(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def valid_endpoint(value):
    try:
        parts = urlsplit(value)
        port = parts.port
        return bool(parts.hostname and not parts.username and not parts.password and not parts.fragment
                    and (parts.scheme == "https" or parts.scheme == "http"
                         and parts.hostname in {"localhost", "127.0.0.1", "::1"})
                    and (port is None or 0 < port < 65536))
    except ValueError:
        return False


def validate_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        raise SnapshotError("The connection did not return an MBCC snapshot.")
    for key in ("players", "standings", "games", "progress", "history", "careers", "seasons"):
        if not isinstance(snapshot.get(key), list):
            raise SnapshotError("The connection returned an incomplete MBCC snapshot.")
    if not snapshot["players"]:
        raise SnapshotError("The snapshot has no players.")
    if snapshot.get("isDemo") is not True and snapshot.get("gamesSource") != "live_scores_and_games":
        raise SnapshotError("This connection is serving the old game list. Deploy the updated MBCC backend and try again.")
    if not isinstance(snapshot.get("season"), str) or not parse_time(snapshot.get("updatedAt")):
        raise SnapshotError("The snapshot is missing its season or update time.")
    schemas = {
        "standings": {"player": str, "correct": int, "overallScore": float, "pointDifference": float},
        "games": {"id": str, "name": str, "startTime": str, "homeTeam": str, "awayTeam": str, "picks": dict},
        "progress": {"gameIndex": int, "correct": dict, "pointDifference": dict},
        "history": {"player": str, "season": str, "award": str, "correct": int, "games": int, "percentage": float, "current": bool},
        "careers": {"player": str, "wins": int, "losses": int, "percentage": float, "active": bool},
        "seasons": {"season": str, "wins": int, "losses": int, "percentage": float},
    }
    if any(not isinstance(player, str) or not player for player in snapshot["players"]):
        raise SnapshotError("The snapshot contains an invalid player.")
    for collection, fields in schemas.items():
        for row in snapshot[collection]:
            if not isinstance(row, dict):
                raise SnapshotError("The snapshot contains an invalid record.")
            for key, kind in fields.items():
                value = row.get(key)
                if kind is float:
                    valid = type(value) in (int, float) and math.isfinite(value)
                elif kind in (int, bool):
                    valid = type(value) is kind
                else:
                    valid = isinstance(value, kind)
                if not valid:
                    raise SnapshotError("The snapshot contains incomplete or invalid results.")
    if any(not parse_time(game["startTime"]) for game in snapshot["games"]):
        raise SnapshotError("The snapshot contains an invalid kickoff time.")
    return snapshot


def fetch_api(endpoint):
    if not valid_endpoint(endpoint):
        raise SnapshotError("Enter an HTTPS snapshot URL (local HTTP is supported for development).")
    request = Request(endpoint, headers={"Accept": "application/json", "User-Agent": "MBCC-Streamlit/1.0"})
    with urlopen(request, timeout=20) as response:
        payload = response.read(16 * 1024 * 1024 + 1)
    if len(payload) > 16 * 1024 * 1024:
        raise SnapshotError("The snapshot is too large to load.")
    return validate_snapshot(json.loads(payload))


def read_demo():
    return validate_snapshot(json.loads((ROOT / "ios/MBCC/demo.json").read_text()))


def is_final(game):
    live = game.get("live")
    return (live is None or live.get("status") == "final") and game.get("winner") not in (None, "", "TBD")


def ranked(snapshot, margin=False):
    metric = "pointDifference" if margin else "overallScore"
    return sorted(snapshot["standings"], key=lambda row: (-row[metric], row["player"]))


def rank_number(standings, entry, margin=False):
    metric = "pointDifference" if margin else "overallScore"
    return 1 + sum(row[metric] > entry[metric] for row in standings)


def filtered_games(games, mode, now=None):
    today = (now or datetime.now(timezone.utc)).astimezone(EASTERN).date()
    ordered = sorted(games, key=lambda game: parse_time(game["startTime"]) or datetime.min.replace(tzinfo=timezone.utc))
    if mode == "All":
        return ordered
    future = [game for game in ordered if parse_time(game["startTime"]) and
              parse_time(game["startTime"]).astimezone(EASTERN).date() >= today]
    if mode == "Future" or not future:
        return future
    first = parse_time(future[0]["startTime"]).astimezone(EASTERN).date()
    return [game for game in future if parse_time(game["startTime"]).astimezone(EASTERN).date() == first]


def update_posts(snapshot, now=None):
    # An explicit empty array clears an older single-post response.
    posts = snapshot.get("updates")
    if posts is None:
        posts = [snapshot["todaysUpdate"]] if snapshot.get("todaysUpdate") else []
    today = (now or datetime.now(timezone.utc)).astimezone(EASTERN).date()
    published = []
    for post in posts:
        try:
            if date.fromisoformat(post["publishedDate"]) <= today:
                published.append(post)
        except (KeyError, ValueError, TypeError):
            continue
    # Keep the backend's ordering for posts published on the same day.
    return sorted(published, key=lambda post: post["publishedDate"], reverse=True)


def youtube_video(value):
    try:
        parts = urlsplit((value or "").strip())
        if parts.scheme.lower() != "https" or parts.username is not None or parts.password is not None or parts.port not in (None, 443):
            return None
        host = (parts.hostname or "").lower()
        path = [part for part in parts.path.split("/") if part]
        video_id = None
        if host in {"youtu.be", "www.youtu.be"} and len(path) == 1:
            video_id = path[0]
        elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
            if path == ["watch"]:
                video_id = parse_qs(parts.query).get("v", [None])[0]
            elif len(path) == 2 and path[0] in {"shorts", "embed", "live"}:
                video_id = path[1]
        if not video_id or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            return None
        return {"url": value.strip(), "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"}
    except ValueError:
        return None


def field_status(check, now=None):
    now = now or datetime.now(timezone.utc)
    if check.get("status") == "pending" and check.get("updatedAt") is None:
        return "pending"
    fetched = parse_time(check.get("updatedAt"))
    if fetched is None or (now - fetched).total_seconds() < -60:
        return "unavailable"
    max_age = check.get("maxAgeSeconds")
    if max_age is not None and (now - fetched).total_seconds() > max_age:
        return "unavailable"
    return check.get("status") if check.get("status") in {"verified", "pending", "mismatch"} else "unavailable"


def verification(game, for_game=False, now=None):
    now = now or datetime.now(timezone.utc)
    checks = game.get("fieldVerification")
    if checks is not None:
        keys = ("startTime", "homeTeam", "awayTeam") if for_game else ("homeScore", "awayScore", "pointDifference")
        statuses = [field_status(checks[key], now) if key in checks else "unavailable" for key in keys]
        return next((status for status in ("unavailable", "mismatch", "pending") if status in statuses), "verified")
    live = game.get("live") or {}
    fetched = parse_time(live.get("updatedAt"))
    if for_game or fetched is None:
        return "unavailable"
    age = (now - fetched).total_seconds()
    settled = live.get("status") == "final" and game.get("verification") == "verified" and game.get("gameVerification") == "verified"
    if age < -60 or not settled and age > (48 * 3600 if live.get("status") == "final" else 600):
        return "unavailable"
    return game.get("verification", "unavailable")


def verification_label(status, for_game=False):
    if status == "verified":
        return "Game matches" if for_game else "Scores match"
    if status == "mismatch":
        return "Game mismatch" if for_game else "Score mismatch"
    return "Game not verified" if for_game else "Scores not verified"


def elimination(snapshot, player):
    possible = [game for game in snapshot["games"] if not is_final(game)
                and game.get("picks", {}).get(player) and
                (game["homeTeam"] == "TBD" or game["awayTeam"] == "TBD"
                 or game["picks"][player] in (game["homeTeam"], game["awayTeam"]))]
    comparisons = []
    for other in snapshot["players"]:
        current = next((row["correct"] for row in snapshot["standings"] if row["player"] == other), 0)
        shared = sum(game.get("picks", {}).get(other) == game["picks"][player] for game in possible)
        comparisons.append({"player": other, "correct": current + shared})
    own = next((row["correct"] for row in comparisons if row["player"] == player), 0)
    return {"best": own, "comparisons": comparisons, "eliminated": any(row["correct"] > own for row in comparisons)}


def is_winner(entry):
    return entry.get("award", "").strip().lower() in {"winner", "co-winner"}


def championships(snapshot):
    names = set(snapshot["players"]) | {row["player"] for row in snapshot["history"] + snapshot["careers"]}
    records = []
    for player in names:
        seasons = defaultdict(list)
        for entry in snapshot["history"]:
            if entry["player"] == player and is_winner(entry):
                seasons[entry["season"]].append(entry)
        full = sum(any(row["award"].strip().lower() == "winner" for row in rows) for rows in seasons.values())
        records.append({"player": player, "fullWins": full, "sharedWins": len(seasons) - full,
                        "trophyCount": full + (len(seasons) - full) * 0.5})
    return sorted(records, key=lambda row: (-row["trophyCount"], row["player"].casefold()))


def score(value):
    if value is None:
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number:,.0f}" if number.is_integer() else f"{number:,.3f}".rstrip("0").rstrip(".")


def kickoff_label(game, time_zone="America/New_York"):
    moment = parse_time(game.get("startTime"))
    if moment is None:
        return "Kickoff TBD"
    local = moment.astimezone(ZoneInfo(time_zone))
    if game.get("kickoffTimeKnown") is False:
        return local.strftime("%b %d, %Y") + " · Time TBD"
    return local.strftime("%b %d · %I:%M %p %Z").replace(" 0", " ")
