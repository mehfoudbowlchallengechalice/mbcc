"""Translate the existing Streamlit worksheets into the iPhone JSON contract.

Google's formatted values preserve dates and the spreadsheet's computed scores.
The adapter deliberately does not recompute scoring or write to the spreadsheet.
"""
from datetime import date, datetime, timezone
from math import isfinite
from zoneinfo import ZoneInfo

WORKSHEETS = (
    "current_pick_success", "basic_history", "agg_history", "season_history",
    "picks", "unlive_games", "live_tracker_binary", "live_tracker_complex", "scores",
)
EASTERN = ZoneInfo("America/New_York")
LIVE_COLUMNS = ("game_id", "game_name", "game_date", "game_time", "game_venue", "game_network",
                "game_home_team", "game_away_team", "home_team_score", "away_team_score", "winner",
                "status", "source", "last_fetched_at", "fetch_error", "point_difference")


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(text(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def records(values, *, row_numbers=False):
    if not values:
        return []
    headers = [str(value).strip() for value in values[0]]
    return [{**dict(zip(headers, list(row) + [""] * (len(headers) - len(row)))),
             **({"__sheet_row__": row_number} if row_numbers else {})}
            for row_number, row in enumerate(values[1:], start=2) if any(str(cell).strip() for cell in row)]


def text(value):
    return str(value).strip() if value is not None else ""


def number(value, default=None, *, field=None):
    if value is None or text(value) == "":
        if default is not None:
            return default
        raise ValueError(f"{field + ': ' if field else ''}A required numeric spreadsheet value is blank")
    try:
        value = float(text(value).replace(",", "").replace("$", ""))
    except ValueError as exc:
        raise ValueError(f"{field + ': ' if field else ''}Expected a numeric spreadsheet value") from exc
    if not isfinite(value):
        raise ValueError(f"{field + ': ' if field else ''}Spreadsheet numbers must be finite")
    return value


def integer(value, default=None, *, field=None):
    value = number(value, default, field=field)
    if value != int(value):
        raise ValueError(f"{field + ': ' if field else ''}Expected a whole-number spreadsheet value")
    return int(value)


def percentage(value, *, field=None):
    value = text(value)
    return number(value[:-1], field=field) / 100 if value.endswith("%") else number(value, field=field)


def truth(value):
    return text(value).lower() in {"true", "1", "1.0", "yes"}


def kickoff(date_value, time_value):
    date_value, time_value = text(date_value), text(time_value)
    date = None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d %H:%M:%S",
                "%A, %B %d, %Y", "%B %d, %Y"):
        try:
            date = datetime.strptime(date_value, fmt).date()
            break
        except ValueError:
            pass
    if date is None:
        # Also support ISO timestamps in a date column.
        try:
            date = datetime.fromisoformat(date_value.replace("Z", "+00:00")).date()
        except ValueError as exc:
            raise ValueError(f"Unsupported game date: {date_value!r}") from exc
    time = None
    for fmt in ("%I:%M %p", "%I:%M:%S %p", "%H:%M:%S", "%H:%M",
                "%Y-%m-%d %I:%M %p", "%Y-%m-%d %I:%M:%S %p",
                "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
                "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M %p", "%m/%d/%Y %I:%M:%S %p"):
        try:
            time = datetime.strptime(time_value, fmt).time()
            break
        except ValueError:
            pass
    if time is None:
        raise ValueError(f"Unsupported kickoff time: {time_value!r}")
    return datetime.combine(date, time, tzinfo=EASTERN).isoformat()


def require_columns(tables, sheet, columns):
    values = tables[sheet]
    if not values:
        raise ValueError(f"Worksheet {sheet!r} has no header row")
    missing = set(columns) - {text(x) for x in values[0]}
    if missing:
        raise ValueError(f"Worksheet {sheet!r} is missing columns: {sorted(missing)}")


def named_rows(rows, column):
    result = {}
    for row in rows:
        name = text(row.get(column))
        if not name:
            continue
        if name in result:
            raise ValueError(f"Duplicate {column}: {name!r}")
        result[name] = row
    return result


def normalized_id(value):
    return str(integer(value)) if text(value) else None


def field_value(kind, value):
    if not text(value) or text(value).upper() in {"TBD", "TBA"}:
        return None
    if kind == "score":
        value = integer(value)
        if value < 0:
            raise ValueError("Scores cannot be negative")
        return value
    if kind == "id":
        return normalized_id(value)
    if kind == "flag":
        value = text(value).lower()
        if value in {"true", "1", "1.0", "yes"}:
            return True
        if value in {"false", "0", "0.0", "no"}:
            return False
        raise ValueError("Invalid indicator")
    return text(value)


def value_label(value):
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value) if value is not None else "—"


def reference_row(live, originals):
    """Names alone must never associate two editions of the same bowl."""
    live_id = normalized_id(live.get("game_id"))
    matches = []
    for original in originals:
        try:
            original_id = normalized_id(original.get("game_id"))
        except ValueError:
            continue
        if live_id and live_id == original_id:
            matches.append(original)
        elif not live_id and not original_id and text(live.get("game_name")) == text(original.get("game_name")):
            try:
                if kickoff(live.get("game_date"), "00:00") == kickoff(original.get("game_date"), "00:00"):
                    matches.append(original)
            except ValueError:
                pass
    return matches[0] if len(matches) == 1 else None


def build_live_games(rows, players, now):
    games, identities = [], set()
    picks = named_rows(rows["picks"], "Game")
    specifications = {
        "homeTeam": ("game_home_team", "text", "unlive_games"),
        "awayTeam": ("game_away_team", "text", "unlive_games"),
        "homeScore": ("home_team_score", "score", "scores"),
        "awayScore": ("away_team_score", "score", "scores"),
        "pointDifference": ("point_difference", "score", "scores"),
    }
    for row_number, live in enumerate(rows["live_scores_and_games"], start=2):
        # Checkbox/formula columns can extend beyond the manually uploaded game list.
        # Only a name, ID or date identifies an intended game row.
        if not any(text(live.get(key)) for key in ("game_id", "game_name", "game_date")):
            continue
        name = text(live.get("game_name"))
        espn_id = normalized_id(live.get("game_id"))
        if not name:
            raise ValueError(f"live_scores_and_games.game_name is required at row {live.get('__sheet_row__', row_number)}")
        identity = "espn:" + espn_id if espn_id else "slot:" + name + ":" + text(live.get("game_date"))
        if identity in identities:
            raise ValueError("Duplicate game in live_scores_and_games")
        identities.add(identity)
        original = reference_row(live, rows["unlive_games"])
        results = [r for r in rows["scores"] if original and text(r.get("game")) == text(original.get("game_name"))]
        result = results[0] if len(results) == 1 else None
        checks, values = {}, {}
        completed = (text(live.get("status")) == "final" and truth(live.get("verified"))
                     and truth(live.get("game_verified")) and not text(live.get("fetch_error")))
        try:
            settled_upcoming = (timestamp(live.get("last_fetched_at")) is not None
                                and field_value("text", live.get("game_home_team")) is not None
                                and field_value("text", live.get("game_away_team")) is not None
                                and datetime.fromisoformat(kickoff(live.get("game_date"), live.get("game_time")))
                                .astimezone(EASTERN).date() > now.astimezone(EASTERN).date())
        except ValueError:
            settled_upcoming = False

        def compare(key, current, expected, sheet, *, current_invalid=False, expected_invalid=False):
            is_score = key in {"homeScore", "awayScore", "pointDifference"}
            fetched = timestamp(live.get("last_fetched_at" if is_score else "schedule_fetched_at"))
            max_age = None if completed or (not is_score and settled_upcoming) else 600 if is_score and text(live.get("status")) != "final" else 48 * 3600
            error = text(live.get("fetch_error")) if is_score else ""
            age = (now - fetched).total_seconds() if fetched else None
            label = value_label(current)
            source = live.get("source" if is_score else "schedule_source")
            status, reason = "verified", "Matches the original entry."
            if current_invalid or expected_invalid:
                status, reason = "unavailable", "This field contains an invalid value."
            elif not text(live.get("last_fetched_at")) and not text(live.get("fetch_error")):
                status, reason = "pending", "Waiting for the first automatic check; imported entries are not verified."
            elif error or not text(source) or age is None or age < -60 or (max_age is not None and age > max_age):
                status, reason = "unavailable", "The source update is unavailable or outdated."
            elif current is None or expected is None:
                status, reason = "pending", "Waiting for this field in the live or original entry."
            elif current != expected:
                status, reason = "mismatch", "Differs from the original entry."
            checks[key] = {"status": status, "value": label, "originalValue": value_label(expected),
                           "source": sheet, "reason": reason,
                           "updatedAt": fetched.isoformat() if fetched else None, "maxAgeSeconds": max_age}

        for key, (column, kind, sheet) in specifications.items():
            expected_row = original if sheet == "unlive_games" else result
            invalid = expected_invalid = False
            try:
                current = field_value(kind, live.get(column))
            except ValueError:
                current, invalid = None, True
            try:
                expected = field_value(kind, (expected_row or {}).get(column))
            except ValueError:
                expected, expected_invalid = None, True
            values[key] = current
            compare(key, current, expected, sheet, current_invalid=invalid, expected_invalid=expected_invalid)

        def start(row):
            return kickoff(row.get("game_date"), row.get("game_time")) if row else None
        try:
            start_time = start(live)
        except ValueError:
            start_time = None
        try:
            expected_start = start(original)
        except ValueError:
            expected_start = None
        compare("startTime", start_time, expected_start, "unlive_games")
        date_only = kickoff(live.get("game_date"), "00:00") if not start_time else start_time

        def focus(row, schedule):
            if not row or not schedule or not text(row.get("team_focus_indicator")):
                return None
            indicator = integer(row["team_focus_indicator"])
            if indicator not in {0, 1}:
                raise ValueError("Invalid focus indicator")
            return field_value("text", schedule.get("game_away_team" if indicator else "game_home_team"))
        # Formula outputs are displayed from the combined tab without verification.
        for key, column in (("upset", "upset_indicator"), ("unanimous", "unanimous_indicator")):
            try:
                values[key] = field_value("flag", live.get(column))
            except ValueError:
                values[key] = None
        try:
            focus_team = focus(live, live)
        except ValueError:
            focus_team = None
        def combined(keys):
            statuses = [checks[key]["status"] for key in keys]
            return next((state for state in ("unavailable", "mismatch", "pending") if state in statuses), "verified")
        verification = combined(("homeScore", "awayScore", "pointDifference"))
        game_verification = combined(("startTime", "homeTeam", "awayTeam"))
        status = text(live.get("status")).lower()
        winner = field_value("text", live.get("winner")) if status == "final" else None
        if winner and winner not in {values["homeTeam"], values["awayTeam"]}:
            winner = None
        game_picks = picks.get(text(original.get("game_name")), {}) if original else {}
        games.append({
            "id": identity, "name": name, "startTime": date_only, "kickoffTimeKnown": start_time is not None,
            "venue": text(live.get("game_venue")), "network": text(live.get("game_network")),
            "homeTeam": text(live.get("game_home_team")) or "TBD", "awayTeam": text(live.get("game_away_team")) or "TBD",
            "homeScore": values["homeScore"], "awayScore": values["awayScore"], "winner": winner,
            "pointDifference": values["pointDifference"],
            "upset": values["upset"], "unanimous": values["unanimous"], "focusTeam": focus_team,
            "espnID": espn_id, "picks": {p: text(game_picks[p]) for p in players if text(game_picks.get(p))},
            "live": {"status": status, "homeScore": values["homeScore"], "awayScore": values["awayScore"],
                     "source": text(live.get("source")), "updatedAt": text(live.get("last_fetched_at")) or None},
            "verification": verification, "verificationReason": "Both scores and point difference match scores." if verification == "verified"
                else "Both scores and point difference must match scores using current data.",
            "gameVerification": game_verification,
            "gameVerificationReason": "Kickoff time and both opponents match unlive_games." if game_verification == "verified"
                else "Kickoff time and both opponents must match unlive_games using current data.",
            "fieldVerification": checks,
        })
    return games


def published_updates(values, now):
    """Return the published blog feed, newest first, retaining every post."""
    posts = []
    today = now.astimezone(EASTERN).date()
    for row in records(values):
        try:
            published = date.fromisoformat(text(row.get("published_date")))
        except ValueError:
            continue
        if published > today or not any(text(row.get(key)) for key in ("title", "message", "youtube_url")):
            continue
        posts.append({
            "title": text(row.get("title")) or "Today’s Update",
            "message": text(row.get("message")),
            "publishedDate": published.isoformat(),
            "youtubeURL": text(row.get("youtube_url")) or None,
        })
    # Reverse row order first so later rows lead when dates match; keep both posts.
    return sorted(reversed(posts), key=lambda post: post["publishedDate"], reverse=True)


def playoff_history_standings(values):
    """Read the users and the two precomputed totals from the top three rows."""
    if not values or not any(text(cell) for row in values[:3] for cell in row):
        return []
    users = values[0]
    totals = {text(row[0]).casefold(): row for row in values[1:3] if row}
    if not {"overall", "overall unknown"}.issubset(totals):
        raise ValueError("playoff_picks needs Overall and Overall Unknown in the first column of rows 2 and 3")
    standings, names = [], set()
    for column, value in enumerate(users[1:], start=1):
        player = text(value)
        if not player:
            continue
        if player in names:
            raise ValueError("playoff_picks contains duplicate users")
        names.add(player)
        entry = {"player": player}
        for label, key in (("overall", "correctPlayoff"), ("overall unknown", "correctUnknownPlayoff")):
            row = totals[label]
            value = row[column] if column < len(row) else None
            count = integer(value, field=f"playoff_picks.{label}.{player}") if text(value) else None
            if count is not None and count < 0:
                raise ValueError("playoff_picks totals must be nonnegative")
            entry[key] = count
        standings.append(entry)
    return standings


def build_snapshot(tables, season="MBCC 14 · 2025–26", now=None):
    now = now or datetime.now(timezone.utc)
    using_live = "live_scores_and_games" in tables
    missing = set(WORKSHEETS) - set(tables)
    if missing:
        raise ValueError(f"Missing worksheets: {sorted(missing)}")
    required = {
        "current_pick_success": ["Situation"],
        "unlive_games": ["game_name", "game_date", "game_time", "game_home_team", "game_away_team"],
        "scores": ["game", "home_team_score", "away_team_score", "winner"],
        "picks": ["Game"],
        "live_tracker_binary": ["gametracker"],
        "live_tracker_complex": ["gametracker"],
        "basic_history": ["MBCC", "Player", "Picks", "Games", "PercentageCorrect", "Winner", "Current"],
        "agg_history": ["Player", "LiveWins", "LiveLosses", "LivePercentage", "Active"],
        "season_history": ["Season", "TotalWins", "TotalLosses", "Percentage"],
    }
    for sheet, columns in required.items():
        if using_live and sheet in {"scores", "unlive_games"}:
            continue  # Originals are comparison data; malformed fields cannot supply app values.
        require_columns(tables, sheet, columns)
    rows = {name: records(values, row_numbers=name == "live_scores_and_games") for name, values in tables.items()}
    if "live_scores_and_games" in tables:
        require_columns(tables, "live_scores_and_games", LIVE_COLUMNS)
    players = [text(x) for x in tables["current_pick_success"][0]
               if text(x) and text(x) != "Situation" and not text(x).startswith("Unnamed:")]
    if not players:
        raise ValueError("No players in current_pick_success")
    situations = {text(row["Situation"]).lower(): row for row in rows["current_pick_success"]}
    for key in ("correct", "mbcc_score", "point_difference"):
        if key not in situations:
            raise ValueError(f"Missing current_pick_success situation: {key}")
    standings = [{"player": player,
                  "correct": integer(situations["correct"].get(player), field=f"current_pick_success.Correct.{player}"),
                  "overallScore": number(situations["mbcc_score"].get(player), field=f"current_pick_success.mbcc_score.{player}"),
                  "pointDifference": number(situations["point_difference"].get(player), field=f"current_pick_success.point_difference.{player}")}
                 for player in players]
    scores = {} if using_live else named_rows(rows["scores"], "game")
    picks = named_rows(rows["picks"], "Game")
    schedule = {} if using_live else named_rows(rows["unlive_games"], "game_name")
    games = build_live_games(rows, players, now) if using_live else []
    for name, row in schedule.items():
        if name not in scores or name not in picks:
            raise ValueError(f"Game {name!r} needs a matching scores and picks row")
        result = scores[name]
        winner = text(result.get("winner"))
        final = winner not in {"", "TBD"}
        home, away = text(row["game_home_team"]), text(row["game_away_team"])
        focus = result.get("team_focus_indicator", row.get("team_focus_indicator"))
        focus_team = away if text(focus) in {"1", "1.0"} else home if text(focus) in {"0", "0.0"} else None
        espn_id = text(row.get("game_id"))
        if espn_id:
            espn_id = str(integer(espn_id, field=f"unlive_games.{name}.game_id"))
        def score(key):
            # A scheduled game's blank score remains blank, rather than a fake 0–0.
            return integer(result.get(key), field=f"scores.{name}.{key}") if final or text(result.get(key)) else None
        games.append({
            "id": name, "name": name, "startTime": kickoff(row["game_date"], row["game_time"]),
            "venue": text(row.get("game_venue")), "network": text(row.get("game_network")),
            "homeTeam": home, "awayTeam": away,
            "homeScore": score("home_team_score"), "awayScore": score("away_team_score"),
            "winner": winner if final else None,
            "upset": truth(result.get("upset_indicator", row.get("upset_indicator"))),
            "unanimous": truth(result.get("unanimous_indicator", row.get("unanimous_indicator"))),
            "focusTeam": focus_team, "espnID": espn_id or None,
            "picks": {p: text(picks[name][p]) for p in players if text(picks[name].get(p))},
            "live": None, "verification": "unavailable",
            "verificationReason": "Live field comparisons are not enabled.",
        })
    binary, complex_rows = rows["live_tracker_binary"], rows["live_tracker_complex"]
    if len(binary) != len(complex_rows):
        raise ValueError("The binary and complex tracker row counts must match")
    progress = []
    for row_index, (binary_row, complex_row) in enumerate(zip(binary, complex_rows), start=2):
        if truth(binary_row.get("gametracker")) != truth(complex_row.get("gametracker")):
            raise ValueError("The binary and complex tracker flags must match")
        if not truth(binary_row.get("gametracker")):
            continue
        progress.append({
            "gameIndex": len(progress),
            "correct": {p: number(binary_row.get(p), field=f"live_tracker_binary.row{row_index}.{p}") for p in players},
            "pointDifference": {p: number(complex_row.get(p), field=f"live_tracker_complex.row{row_index}.{p}") for p in players},
        })
    history = [{"season": text(r["MBCC"]), "player": text(r["Player"]),
                "correct": integer(r["Picks"], field=f"basic_history.row{i}.Picks"), "games": integer(r["Games"], field=f"basic_history.row{i}.Games"),
                "percentage": percentage(r["PercentageCorrect"], field=f"basic_history.row{i}.PercentageCorrect"), "award": text(r["Winner"]),
                "current": truth(r["Current"])} for i, r in enumerate(rows["basic_history"], start=2) if text(r.get("Player"))]
    careers = [{"player": text(r["Player"]), "wins": integer(r["LiveWins"], field=f"agg_history.row{i}.LiveWins"),
                "losses": integer(r["LiveLosses"], field=f"agg_history.row{i}.LiveLosses"), "percentage": percentage(r["LivePercentage"], field=f"agg_history.row{i}.LivePercentage"),
                "active": truth(r["Active"])} for i, r in enumerate(rows["agg_history"], start=2) if text(r.get("Player"))]
    seasons = [{"season": text(r["Season"]), "wins": integer(r["TotalWins"], field=f"season_history.row{i}.TotalWins"),
                "losses": integer(r["TotalLosses"], field=f"season_history.row{i}.TotalLosses"), "percentage": percentage(r["Percentage"], field=f"season_history.row{i}.Percentage")}
               for i, r in enumerate(rows["season_history"], start=2) if text(r.get("Season"))]
    updates = published_updates(tables.get("todays_update", []), now)
    return {"isDemo": False, "season": season, "updatedAt": now.isoformat(timespec="seconds"),
            "gamesSource": "live_scores_and_games" if using_live else "legacy",
            "todaysUpdate": updates[0] if updates else None,
            "updates": updates,
            "players": players, "standings": standings, "games": games,
            "progress": progress, "history": history, "careers": careers, "seasons": seasons,
            "playoffStandings": playoff_history_standings(tables["playoff_history"]) if "playoff_history" in tables else None}
