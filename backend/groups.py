"""Combine two challenge rosters without merging their player identities."""
from copy import deepcopy
from datetime import datetime

GROUPS = {"default": "Main group", "sub": "Subgroup", "default+sub": "Main group + subgroup"}


class GroupError(ValueError):
    """A group configuration or compatibility error safe to show to readers."""


def normalize_group(value):
    group = (value or "").strip().lower() or "default"
    if group not in GROUPS:
        raise GroupError("Enter default, sub, or default+sub as the group keyword.")
    return group


def combine_snapshots(main, sub):
    """Use one shared schedule, append rosters, and retain each group's stats."""
    if main["season"] != sub["season"] or main.get("isDemo") != sub.get("isDemo"):
        raise GroupError("Both groups must use the same season and data mode to show them together.")

    def game_key(game):
        return ("espn", str(game["espnID"])) if game.get("espnID") else ("name", game["name"].strip().casefold())

    def index_games(snapshot):
        indexed = {game_key(game): game for game in snapshot["games"]}
        if len(indexed) != len(snapshot["games"]):
            raise GroupError("Each group must have unique games before showing them together.")
        return indexed

    main_games, sub_games = index_games(main), index_games(sub)
    if main_games.keys() != sub_games.keys():
        raise GroupError("Both groups must use the same game schedule to show them together.")
    for key, game in main_games.items():
        other = sub_games[key]
        if (datetime.fromisoformat(game["startTime"].replace("Z", "+00:00")) !=
                datetime.fromisoformat(other["startTime"].replace("Z", "+00:00")) or
                any(game.get(field) != other.get(field) for field in
                    ("homeTeam", "awayTeam", "homeScore", "awayScore", "winner")) or
                (game.get("live") or {}).get("status") != (other.get("live") or {}).get("status")):
            raise GroupError("The groups' game results differ. Refresh after both spreadsheets are in sync.")
    # Tracker indices count completed rows; different row orders cannot be safely
    # combined even when the sets of games happen to match.
    if [game_key(game) for game in main["games"]] != [game_key(game) for game in sub["games"]]:
        raise GroupError("Both groups must use the same game order to combine season charts.")
    if [point["gameIndex"] for point in main["progress"]] != [point["gameIndex"] for point in sub["progress"]]:
        raise GroupError("The groups' season trackers differ. Refresh after both spreadsheets are in sync.")

    renamed = []
    for snapshot, label in ((main, "Main"), (sub, "Sub")):
        snapshot = deepcopy(snapshot)
        name = lambda player: f"{player} [{label}]"
        snapshot["players"] = [name(player) for player in snapshot["players"]]
        for collection in ("standings", "history", "careers", "playoffStandings"):
            for row in snapshot.get(collection) or []:
                row["player"] = name(row["player"])
        for game in snapshot["games"]:
            game["picks"] = {name(player): pick for player, pick in game["picks"].items()}
        for point in snapshot["progress"]:
            for field in ("correct", "pointDifference"):
                point[field] = {name(player): value for player, value in point[field].items()}
        renamed.append(snapshot)
    combined, other = renamed
    combined["group"] = "default+sub"
    combined["updatedAt"] = min((main["updatedAt"], sub["updatedAt"]),
                                key=lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")))
    for collection in ("players", "standings", "history", "careers"):
        combined[collection].extend(other[collection])
    for game, other_game in zip(combined["games"], other["games"]):
        game["picks"].update(other_game["picks"])
        # These indicators depend on the roster, unlike the shared game results.
        picks = set(game["picks"].values())
        game["unanimous"] = bool(picks - {"", "TBD"}) and len(picks) == 1 and len(game["picks"]) == len(combined["players"])
        if any(game.get(field) != other_game.get(field) for field in ("upset", "focusTeam")):
            game["upset"], game["focusTeam"] = None, None
    for point, other_point in zip(combined["progress"], other["progress"]):
        for field in ("correct", "pointDifference"):
            point[field].update(other_point[field])
    # Aggregate rows already contain each group's calculated totals. Keep their
    # labels distinct instead of inventing a combined historical championship.
    combined["seasons"] = [dict(row, season=f'{row["season"]} [{label}]')
                           for snapshot, label in ((main, "Main"), (sub, "Sub")) for row in snapshot["seasons"]]
    combined["playoffStandings"] = (combined.get("playoffStandings") or []) + (other.get("playoffStandings") or [])
    missing = [label for snapshot, label in ((main, "Main group"), (sub, "Subgroup"))
               if snapshot.get("playoffStandings") is None or snapshot.get("playoffStandingsError")]
    if missing:
        combined["playoffStandingsError"] = "All-time playoff standings unavailable for: " + ", ".join(missing) + "."
    # The main group's published updates remain the shared news feed.
    return combined
