import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from web_app import data, playoffs


def playoff_fixture(snapshot):
    snapshot = copy.deepcopy(snapshot)
    names = (["College Football Playoff First Round Game (" + str(i) + ")" for i in range(4)]
             + ["College Football Playoff Quarterfinal at the " + bowl + " Bowl" for bowl in ("Fiesta", "Cotton", "Rose", "Peach")]
             + ["College Football Playoff Semifinal at the " + bowl + " Bowl" for bowl in ("Orange", "Sugar")]
             + ["College Football Playoff National Championship Presented by AT&T"])
    games = []
    for index, name in enumerate(names):
        game = copy.deepcopy(snapshot["games"][0])
        game.update(id="playoff-" + str(index), name=name, startTime=f"2026-12-{index + 1:02d}T20:00:00-05:00",
                    homeTeam="Virginia Tech" if index < 8 else "TBD", awayTeam="Tulane" if index < 8 else "TBD",
                    homeScore=0 if index < 4 else None, awayScore=7 if index < 4 else None,
                    winner="Tulane" if index < 4 else None, picks={"Christopher": "Tulane", "Elise": "Virginia Tech"})
        games.append(game)
    snapshot["games"] += list(reversed(games))
    return snapshot


class WebModelTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = data.read_demo()
        self.now = datetime(2026, 11, 20, 2, tzinfo=timezone.utc)

    def test_group_display_names_remove_only_the_generated_suffix(self):
        self.assertEqual(data.display_name("Alice [Main]"), "Alice")
        self.assertEqual(data.display_name("Alice [Sub]"), "Alice")
        self.assertEqual(data.display_name("2026–27 [Sub]"), "2026–27")
        self.assertEqual(data.display_name("Alice [Other]"), "Alice [Other]")
        self.assertEqual(data.display_name("Alice"), "Alice")

    def test_personal_pick_results_wait_for_final_and_keep_unknown_slots(self):
        game = copy.deepcopy(self.snapshot["games"][0])
        game.update(winner="Home", homeTeam="Home", awayTeam="Away", live=None,
                    picks={"Alice": "Home", "Bob": "Away", "Future": "Unresolved school"})
        self.assertEqual(data.pick_result(game, "Alice"), "correct")
        self.assertEqual(data.pick_result(game, "Bob"), "incorrect")
        self.assertEqual(data.pick_result(game, "Future"), "incorrect")
        self.assertIsNone(data.pick_result(game, "Missing"))
        game["live"] = {"status": "live"}
        self.assertEqual(data.pick_result(game, "Alice"), "pending")
        self.assertEqual(data.pick_result(game, "Bob"), "pending")

    def test_current_player_filter_covers_all_player_data_without_mutating_source(self):
        self.snapshot["careers"][0]["active"] = False
        self.snapshot["playoffStandings"] = [
            {"player": name, "correctPlayoff": 10, "correctUnknownPlayoff": 2}
            for name in ("Christopher", "Elise", "Former")
        ]
        original = copy.deepcopy(self.snapshot)
        filtered = data.filter_current_players(self.snapshot)
        self.assertNotIn("Christopher", filtered["players"])
        for key in ("standings", "history", "careers", "playoffStandings"):
            self.assertNotIn("Christopher", [row["player"] for row in filtered[key]])
            self.assertIn("Elise", [row["player"] for row in filtered[key]])
        self.assertNotIn("Former", [row["player"] for row in filtered["playoffStandings"]])
        for game in filtered["games"]:
            self.assertNotIn("Christopher", game["picks"])
        for point in filtered["progress"]:
            self.assertNotIn("Christopher", point["correct"])
            self.assertNotIn("Christopher", point["pointDifference"])
        self.assertEqual(filtered["seasons"], original["seasons"])
        self.assertEqual(len(filtered["games"]), len(original["games"]))
        self.assertEqual(self.snapshot, original)
        self.assertEqual(data.filter_current_players(self.snapshot, False), original)

    def test_current_player_filter_falls_back_to_history_and_roster(self):
        self.snapshot["careers"] = []
        self.snapshot["history"] = [
            {"player": "Christopher", "current": False},
            {"player": "Elise", "current": True},
        ]
        filtered = data.filter_current_players(self.snapshot)
        self.assertNotIn("Christopher", filtered["players"])
        self.assertIn("Elise", filtered["players"])
        self.assertIn("Emma", filtered["players"])

    def test_shared_scores_and_competition_ranks_are_preserved(self):
        self.snapshot["standings"] = [
            {"player": "Alice", "correct": 3, "overallScore": 3.0002, "pointDifference": -7},
            {"player": "Bob", "correct": 3, "overallScore": 3.0002, "pointDifference": 7},
            {"player": "Carol", "correct": 3, "overallScore": 3.0001, "pointDifference": 0},
        ]
        ranked = data.ranked(self.snapshot)
        self.assertEqual([data.rank_number(ranked, row) for row in ranked], [1, 1, 3])
        self.assertEqual(data.ranked(self.snapshot, True)[0]["player"], "Bob")
        self.assertEqual(ranked[0]["correct"], 3)
        self.assertEqual(ranked[0]["overallScore"], 3.0002)
        self.assertEqual(data.score(3.001), "3.001")

    def test_game_filters_use_eastern_dates_and_next_game_day(self):
        games = [
            {"id": "later", "startTime": "2026-11-22T18:00:00Z"},
            {"id": "utc20_eastern19", "startTime": "2026-11-20T02:00:00Z"},
            {"id": "next", "startTime": "2026-11-21T18:00:00Z"},
        ]
        self.assertEqual([row["id"] for row in data.filtered_games(games, "Today", self.now)], ["utc20_eastern19"])
        next_day = self.now + timedelta(hours=6)
        self.assertEqual([row["id"] for row in data.filtered_games(games, "Today", next_day)], ["next"])
        self.assertEqual(len(data.filtered_games(games, "Future", next_day)), 2)
        self.assertEqual(len(data.filtered_games(games, "All", next_day)), 3)

    def test_blog_keeps_archive_and_same_day_order_but_hides_future(self):
        self.snapshot["updates"] = [
            {"title": "Newer", "publishedDate": "2026-11-19"},
            {"title": "Same day", "publishedDate": "2026-11-19"},
            {"title": "Future Eastern", "publishedDate": "2026-11-20"},
            {"title": "Earlier", "publishedDate": "2026-11-18"},
        ]
        self.assertEqual([row["title"] for row in data.update_posts(self.snapshot, self.now)], ["Newer", "Same day", "Earlier"])
        self.snapshot["todaysUpdate"] = self.snapshot["updates"][0]
        self.snapshot["updates"] = []
        self.assertEqual(data.update_posts(self.snapshot, self.now), [])
        del self.snapshot["updates"]
        self.assertEqual(len(data.update_posts(self.snapshot, self.now)), 1)

    def test_video_links_reject_spoofed_hosts_and_keep_timestamps(self):
        for value in ["https://youtu.be/dQw4w9WgXcQ?t=30", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s",
                      "https://youtube.com/shorts/dQw4w9WgXcQ", "https://youtube.com/live/dQw4w9WgXcQ"]:
            self.assertEqual(data.youtube_video(value)["url"], value)
        for value in ["javascript:alert(1)", "https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
                      "https://user@youtube.com/watch?v=dQw4w9WgXcQ", "http://youtu.be/dQw4w9WgXcQ",
                      "https://youtu.be/short", "https://youtu.be:invalid/dQw4w9WgXcQ"]:
            self.assertIsNone(data.youtube_video(value))

    def test_verification_zero_scores_freshness_and_settled_finals(self):
        check = {"status": "verified", "updatedAt": self.now.isoformat(), "maxAgeSeconds": 600,
                 "value": "0", "originalValue": "0", "source": "scores"}
        game = {"fieldVerification": {key: copy.deepcopy(check) for key in ("homeScore", "awayScore", "pointDifference", "startTime", "homeTeam", "awayTeam")}}
        self.assertEqual(data.verification(game, now=self.now), "verified")
        game["fieldVerification"]["pointDifference"]["status"] = "mismatch"
        self.assertEqual(data.verification(game, now=self.now), "mismatch")
        self.assertEqual(data.verification(game, True, self.now), "verified")
        self.assertEqual(data.verification(game, now=self.now + timedelta(seconds=601)), "unavailable")
        for check in game["fieldVerification"].values():
            check["status"] = "verified"
            check["maxAgeSeconds"] = None
        self.assertEqual(data.verification(game, now=self.now + timedelta(days=30)), "verified")
        self.assertEqual(data.field_status({"status": "pending", "updatedAt": None}, self.now), "pending")
        self.assertEqual(data.score(0), "0")
        self.assertEqual(data.score(None), "—")

    def test_playoff_rounds_use_labels_not_bowl_names_and_sort_games(self):
        rounds = playoffs.playoff_games(playoff_fixture(self.snapshot))
        self.assertEqual([len(games) for _, games in rounds], [4, 4, 2, 1])
        self.assertEqual([game["id"] for game in rounds[0][1]], ["playoff-0", "playoff-1", "playoff-2", "playoff-3"])
        for name in ["Cotton Bowl", "Orange Bowl", "Chalice Championship", "FCS National Championship", "Celebration Bowl"]:
            self.assertIsNone(playoffs.playoff_round(name))
        for name, expected in [("CFP First-Round", 0), ("CFP 1st Round", 0), ("CFP Quarter-final", 1),
                               ("CFP Semi-final", 2), ("CFP National Championship", 3)]:
            self.assertEqual(playoffs.playoff_round(name), expected)
        self.assertTrue(all(not games for _, games in playoffs.playoff_games(self.snapshot)))

    def test_playoff_history_is_optional_and_sorts_historical_totals(self):
        self.assertEqual(playoffs.playoff_standings(self.snapshot), [])
        self.snapshot["playoffStandings"] = [
            {"player": "Zoe", "correctPlayoff": 3, "correctUnknownPlayoff": 1},
            {"player": "Bob", "correctPlayoff": 3, "correctUnknownPlayoff": 2},
            {"player": "Missing", "correctPlayoff": None, "correctUnknownPlayoff": None},
            {"player": "Zero", "correctPlayoff": 0, "correctUnknownPlayoff": 0},
            {"player": "Alice", "correctPlayoff": 3, "correctUnknownPlayoff": 2},
        ]
        self.assertEqual([row["player"] for row in playoffs.playoff_standings(data.validate_snapshot(self.snapshot))],
                         ["Alice", "Bob", "Zoe", "Zero", "Missing"])
        for value in [-1, 1.5, True, "12"]:
            broken = copy.deepcopy(self.snapshot)
            broken["playoffStandings"][0]["correctPlayoff"] = value
            with self.assertRaises(data.SnapshotError):
                data.validate_snapshot(broken)

    def test_elimination_keeps_ties_alive_and_ignores_impossible_picks(self):
        self.snapshot["players"] = ["Alice", "Bob"]
        self.snapshot["standings"] = [{"player": "Alice", "correct": 0}, {"player": "Bob", "correct": 1}]
        game = {"homeTeam": "Home", "awayTeam": "Away", "picks": {"Alice": "Home", "Bob": "Away"}, "winner": None}
        self.snapshot["games"] = [game]
        self.assertFalse(data.elimination(self.snapshot, "Alice")["eliminated"])
        game["picks"]["Bob"] = "Home"
        self.assertTrue(data.elimination(self.snapshot, "Alice")["eliminated"])
        game["picks"]["Alice"] = "Eliminated team"
        self.assertEqual(data.elimination(self.snapshot, "Alice")["best"], 0)
        game["homeTeam"] = "TBD"
        self.assertEqual(data.elimination(self.snapshot, "Alice")["best"], 1)

    def test_championships_count_unique_seasons_and_half_trophies(self):
        self.snapshot["players"] = ["Alice", "Bob", "No wins"]
        self.snapshot["careers"] = []
        self.snapshot["history"] = [
            {"player": "Alice", "season": "1", "award": "Winner"},
            {"player": "Alice", "season": "1", "award": "Winner"},
            {"player": "Bob", "season": "1", "award": " Co-Winner "},
            {"player": "Former", "season": "0", "award": "Winner"},
        ]
        records = {row["player"]: row for row in data.championships(self.snapshot)}
        self.assertEqual(records["Alice"]["trophyCount"], 1)
        self.assertEqual(records["Bob"]["trophyCount"], 0.5)
        self.assertEqual(records["No wins"]["trophyCount"], 0)
        self.assertIn("Former", records)

    def test_live_contract_rejects_old_game_source_and_untrusted_endpoint_forms(self):
        live = dict(self.snapshot, isDemo=False, gamesSource="legacy")
        with self.assertRaisesRegex(data.SnapshotError, "old game list"):
            data.validate_snapshot(live)
        self.assertTrue(data.valid_endpoint("https://example.com/api/snapshot"))
        self.assertTrue(data.valid_endpoint("http://localhost:8000/api/snapshot"))
        for value in ["file:///tmp/data", "http://example.com", "https://user@example.com", "https://example.com/#fragment"]:
            self.assertFalse(data.valid_endpoint(value))
        with patch("web_app.data.urlopen") as request:
            with self.assertRaises(data.SnapshotError):
                data.fetch_api("file:///tmp/data")
            request.assert_not_called()

    def test_malformed_snapshot_cannot_replace_saved_results(self):
        for key, value in [("overallScore", float("nan")), ("correct", "3")]:
            snapshot = copy.deepcopy(self.snapshot)
            snapshot["standings"][0][key] = value
            with self.assertRaises(data.SnapshotError):
                data.validate_snapshot(snapshot)
