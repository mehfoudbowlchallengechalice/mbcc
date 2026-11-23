"""Group playoff games from the shared MBCC snapshot into rounds."""
import re

from web_app.data import parse_time

PLAYOFF_ROUNDS = ("First round", "Quarterfinals", "Semifinals", "Championship")


def playoff_round(name):
    # Require a playoff label: ordinary bowl names can change rounds by season.
    name = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    if "college football playoff" not in name and not re.search(r"\bcfp\b", name):
        return None
    if "quarterfinal" in name or "quarter final" in name:
        return 1
    if "semifinal" in name or "semi final" in name:
        return 2
    if "championship" in name:
        return 3
    if "first round" in name or "1st round" in name:
        return 0
    return None


def playoff_games(snapshot):
    rounds = [[] for _ in PLAYOFF_ROUNDS]
    for game in snapshot["games"]:
        index = playoff_round(game["name"])
        if index is not None:
            rounds[index].append(game)
    for games in rounds:
        games.sort(key=lambda game: (parse_time(game["startTime"]), game["id"]))
    return list(zip(PLAYOFF_ROUNDS, rounds))
