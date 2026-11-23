import copy
import json
import unittest
from datetime import datetime
from unittest.mock import patch

from backend.sheets_adapter import build_snapshot, kickoff, records
from backend import server


def worksheet(rows):
    headers = list(rows[0])
    return [headers] + [[row.get(key, "") for key in headers] for row in rows]


def fixture():
    return {
        "current_pick_success": worksheet([
            {"Situation": "point_difference", "Alice": -7, "Bob": 7},
            {"Situation": "mbcc_score", "Alice": 0.01, "Bob": 1.02},
            {"Situation": "Correct", "Alice": 0, "Bob": 1},
        ]),
        "unlive_games": worksheet([
            {"game_name": "Bowl", "game_date": "12/20/2025", "game_time": "7:30 PM",
             "game_home_team": "Home", "game_away_team": "Away", "game_id": 401234567,
             "game_network": "ESPN", "game_venue": "Stadium"},
            {"game_name": "Final", "game_date": "1/1/2026", "game_time": "12:00:00",
             "game_home_team": "TBD", "game_away_team": "Other", "game_id": 401234568},
        ]),
        "scores": worksheet([
            {"game": "Bowl", "home_team_score": 14, "away_team_score": 21, "winner": "Away",
             "upset_indicator": 1, "unanimous_indicator": 0, "team_focus_indicator": 1, "point_difference": 7},
            {"game": "Final", "home_team_score": "", "away_team_score": "", "winner": "TBD"},
        ]),
        "picks": worksheet([
            {"Game": "Bowl", "Alice": "Home", "Bob": "Away"},
            {"Game": "Final", "Alice": "Home", "Bob": "Away"},
        ]),
        "live_tracker_binary": worksheet([
            {"gametracker": 1, "Alice": 0, "Bob": 0},
            {"gametracker": 1, "Alice": 0, "Bob": 1},
            {"gametracker": 0, "Alice": "", "Bob": ""},
        ]),
        "live_tracker_complex": worksheet([
            {"gametracker": 1, "Alice": 0, "Bob": 0},
            {"gametracker": 1, "Alice": -7, "Bob": 7},
            {"gametracker": 0, "Alice": "", "Bob": ""},
        ]),
        "basic_history": worksheet([
            {"MBCC": "2024–25", "Player": "Bob", "Picks": 30, "Games": 40,
             "PercentageCorrect": "75%", "Winner": "Winner", "Current": "TRUE"},
        ]),
        "agg_history": worksheet([
            {"Player": "Bob", "LiveWins": 30, "LiveLosses": 10, "LivePercentage": 0.75, "Active": True},
        ]),
        "season_history": worksheet([
            {"Season": "2024–25", "TotalWins": 30, "TotalLosses": 10, "Percentage": 0.75},
        ]),
    }


class AdapterTests(unittest.TestCase):
    def test_update_feed_keeps_all_posts_in_date_order_using_eastern_time(self):
        tables = fixture()
        tables["todays_update"] = worksheet([
            {"published_date": "2026-11-19", "title": "Earlier briefing", "message": "Earlier", "youtube_url": "https://youtu.be/abcdefghijk"},
            {"published_date": "2026-11-20", "title": "Tomorrow", "message": "Not public yet", "youtube_url": ""},
            {"published_date": "2026-11-19", "title": "Latest briefing", "message": "Go team!", "youtube_url": "https://youtu.be/dQw4w9WgXcQ"},
            {"published_date": "invalid", "title": "Invalid date", "message": "", "youtube_url": ""},
            {"published_date": "2026-11-19", "title": "", "message": "", "youtube_url": ""},
            {"published_date": "2026-11-18", "title": "Oldest briefing", "message": "First paragraph.\n\nSecond paragraph.", "youtube_url": ""},
        ])
        # It is still November 19 in Eastern Time, despite the UTC date.
        now = datetime.fromisoformat("2026-11-20T02:00:00+00:00")
        snapshot = build_snapshot(tables, now=now)
        update = snapshot["todaysUpdate"]
        self.assertEqual(update, {"title": "Latest briefing", "message": "Go team!",
                                 "publishedDate": "2026-11-19", "youtubeURL": "https://youtu.be/dQw4w9WgXcQ"})
        self.assertEqual([post["title"] for post in snapshot["updates"]],
                         ["Latest briefing", "Earlier briefing", "Oldest briefing"])
        self.assertEqual(snapshot["updates"][1]["youtubeURL"], "https://youtu.be/abcdefghijk")
        self.assertEqual(snapshot["updates"][2]["message"], "First paragraph.\n\nSecond paragraph.")
        tomorrow = build_snapshot(tables, now=datetime.fromisoformat("2026-11-20T05:00:00+00:00"))
        self.assertEqual(tomorrow["todaysUpdate"]["title"], "Tomorrow")
        self.assertEqual(len(tomorrow["updates"]), 4)

    def test_missing_blank_and_unpublished_updates_do_not_break_results(self):
        tables = fixture()
        self.assertIsNone(build_snapshot(tables)["todaysUpdate"])
        self.assertEqual(build_snapshot(tables)["updates"], [])
        for values in ([], [["published_date", "title", "message", "youtube_url"]],
                       [["published_date", "title"], ["2099-12-01", "Future"]],
                       [["wrong_header"], ["Invalid"]]):
            tables["todays_update"] = values
            self.assertIsNone(build_snapshot(tables)["todaysUpdate"])
            self.assertEqual(build_snapshot(tables)["updates"], [])
        tables["todays_update"] = [["published_date", "youtube_url"], ["2026-11-19", "https://youtu.be/dQw4w9WgXcQ"]]
        update = build_snapshot(tables)["todaysUpdate"]
        self.assertEqual(update["title"], "Today’s Update")
        self.assertEqual(update["message"], "")

    def test_scores_use_labels_not_row_order_and_preserve_precision(self):
        data = build_snapshot(fixture())
        self.assertEqual(data["standings"][0], {"player": "Alice", "correct": 0, "overallScore": 0.01, "pointDifference": -7.0})
        self.assertFalse(data["isDemo"])
        json.dumps(data, allow_nan=False)

    def test_schedule_picks_flags_and_underdog_are_joined(self):
        game = build_snapshot(fixture())["games"][0]
        self.assertEqual(game["picks"], {"Alice": "Home", "Bob": "Away"})
        self.assertEqual(game["focusTeam"], "Away")
        self.assertTrue(game["upset"])
        self.assertEqual(game["espnID"], "401234567")
        self.assertEqual(game["startTime"], "2025-12-20T19:30:00-05:00")

    def test_blank_scheduled_scores_do_not_become_zero(self):
        game = build_snapshot(fixture())["games"][1]
        self.assertIsNone(game["homeScore"])
        self.assertIsNone(game["winner"])

    def test_missing_final_score_is_an_error(self):
        tables = fixture()
        tables["scores"][1][1] = ""
        with self.assertRaisesRegex(ValueError, "scores.Bowl.home_team_score"):
            build_snapshot(tables)

    def test_history_percentage_and_booleans(self):
        data = build_snapshot(fixture())
        self.assertEqual(data["history"][0]["percentage"], 0.75)
        self.assertTrue(data["history"][0]["current"])
        self.assertTrue(data["careers"][0]["active"])

    def test_tracker_ignores_unfinished_rows_and_keeps_zero_baseline(self):
        points = build_snapshot(fixture())["progress"]
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0]["gameIndex"], 0)
        self.assertEqual(points[1]["pointDifference"]["Alice"], -7)

    def test_incomplete_join_or_schema_fails_instead_of_dropping_games(self):
        for table in ("scores", "picks"):
            tables = fixture()
            tables[table].pop()
            with self.assertRaises(ValueError):
                build_snapshot(tables)
        tables = fixture()
        del tables["basic_history"]
        with self.assertRaises(ValueError):
            build_snapshot(tables)

    def test_duplicate_names_and_nonfinite_scores_are_rejected(self):
        tables = fixture()
        tables["scores"].append(copy.deepcopy(tables["scores"][1]))
        with self.assertRaises(ValueError):
            build_snapshot(tables)
        tables = fixture()
        tables["current_pick_success"][1][1] = "NaN"
        with self.assertRaises(ValueError):
            build_snapshot(tables)

    def test_time_zone_observes_dst(self):
        self.assertTrue(kickoff("2026-07-01", "13:30").endswith("-04:00"))

    def test_google_sheet_combined_date_time_preserves_am_pm(self):
        for value, expected in (
            ("2025-12-13 12:00 PM", "12:00:00"),
            ("2025-12-13 12:00 AM", "00:00:00"),
            ("2025-12-13 6:30 PM", "18:30:00"),
            ("2025-12-13 6:30:15 PM", "18:30:15"),
            ("2025-12-13 18:30", "18:30:00"),
            ("12/13/2025 6:30 PM", "18:30:00"),
        ):
            with self.subTest(value=value):
                self.assertEqual(kickoff("2025-12-13", value), f"2025-12-13T{expected}-05:00")

    def test_schedule_date_is_authoritative_when_time_cell_also_has_a_date(self):
        self.assertEqual(kickoff("2025-12-20", "1899-12-30 12:00 PM"),
                         "2025-12-20T12:00:00-05:00")

    def test_snapshot_accepts_the_reported_live_kickoff_format(self):
        tables = fixture()
        header = tables["unlive_games"][0]
        tables["unlive_games"][1][header.index("game_time")] = "2025-12-13 12:00 PM"
        snapshot = build_snapshot(tables)
        self.assertEqual(snapshot["games"][0]["startTime"], "2025-12-20T12:00:00-05:00")
        self.assertEqual(len(snapshot["games"]), 2)
        json.dumps(snapshot, allow_nan=False)

    def test_invalid_kickoff_is_not_silently_treated_as_midnight(self):
        with self.assertRaisesRegex(ValueError, "Unsupported kickoff time"):
            kickoff("2025-12-13", "not a time")

    def test_records_preserve_trailing_blank_cells(self):
        self.assertEqual(records([["A", "B"], [1]]), [{"A": 1, "B": ""}])


class APITests(unittest.TestCase):
    def test_updates_are_opt_in_and_read_from_the_challenge_workbook(self):
        with patch.dict("os.environ", {"MBCC_CHALLENGE_SHEET_ID": "challenge", "MBCC_HISTORY_SHEET_ID": "history",
                                      "MBCC_UPDATES_ENABLED": "0"}):
            self.assertNotIn("todays_update", server.spreadsheet_groups()["challenge"])
        with patch.dict("os.environ", {"MBCC_CHALLENGE_SHEET_ID": "challenge", "MBCC_HISTORY_SHEET_ID": "history",
                                      "MBCC_UPDATES_ENABLED": "1"}):
            self.assertIn("todays_update", server.spreadsheet_groups()["challenge"])
            self.assertNotIn("todays_update", server.spreadsheet_groups()["history"])

    def test_single_challenge_workbook_includes_live_games_by_default(self):
        with patch.dict("os.environ", {"MBCC_CHALLENGE_SHEET_ID": "challenge", "MBCC_HISTORY_SHEET_ID": "challenge"}):
            import os
            os.environ.pop("MBCC_LIVE_SCORES_ENABLED", None)
            groups = server.spreadsheet_groups()
        self.assertEqual(list(groups), ["challenge"])
        self.assertEqual(groups["challenge"], list(server.WORKSHEETS + server.OPTIONAL_WORKSHEETS))

    def test_legacy_source_requires_an_explicit_override(self):
        with patch.dict("os.environ", {"MBCC_CHALLENGE_SHEET_ID": "challenge", "MBCC_HISTORY_SHEET_ID": "challenge",
                                      "MBCC_LIVE_SCORES_ENABLED": "0"}):
            self.assertEqual(server.spreadsheet_groups()["challenge"], list(server.WORKSHEETS))

    def test_worksheet_aliases_can_use_actual_tab_titles(self):
        mapping = json.dumps({"current_pick_success": "Current Scores", "basic_history": "All Years"})
        with patch.dict("os.environ", {"MBCC_WORKSHEET_TITLES": mapping}):
            titles = server.worksheet_titles()
        self.assertEqual(titles["current_pick_success"], "Current Scores")
        self.assertEqual(titles["basic_history"], "All Years")
        self.assertEqual(titles["picks"], "picks")
        self.assertEqual(server.sheet_range("Player's picks"), "'Player''s picks'")

    def test_bad_mapping_fails_instead_of_reading_an_unintended_tab(self):
        for value in ('[]', '{"typo":"Scores"}', '{"scores":""}', 'not json'):
            with patch.dict("os.environ", {"MBCC_WORKSHEET_TITLES": value}):
                with self.assertRaises(ValueError):
                    server.worksheet_titles()

    def test_two_files_route_history_and_challenge_separately(self):
        with patch.dict("os.environ", {"MBCC_CHALLENGE_SHEET_ID": "challenge", "MBCC_HISTORY_SHEET_ID": "history"}):
            groups = server.spreadsheet_groups()
        self.assertEqual(set(groups["history"]), {"basic_history", "agg_history", "season_history"})
        self.assertIn("picks", groups["challenge"])
        self.assertNotIn("basic_history", groups["challenge"])

    def call(self, path, method="GET"):
        response = {}
        def start(status, headers):
            response.update(status=status, headers=dict(headers))
        body = b"".join(server.application({"PATH_INFO": path, "REQUEST_METHOD": method}, start))
        return response, body

    def test_read_only_and_unknown_routes(self):
        self.assertTrue(self.call("/api/snapshot", "POST")[0]["status"].startswith("405"))
        self.assertTrue(self.call("/unknown")[0]["status"].startswith("404"))
        self.assertEqual(self.call("/health", "HEAD")[1], b"")

    def test_failure_does_not_leak_remote_errors(self):
        with patch.object(server, "snapshot_bytes", side_effect=RuntimeError("secret token")):
            response, body = self.call("/api/snapshot")
        self.assertTrue(response["status"].startswith("502"))
        self.assertNotIn(b"secret", body)

    def test_validation_details_are_in_server_logs_only(self):
        with patch.object(server, "snapshot_bytes", side_effect=ValueError("Worksheet 'scores' is missing columns: ['winner']")):
            with self.assertLogs("mbcc", level="ERROR") as messages:
                response, body = self.call("/api/snapshot")
        self.assertTrue(response["status"].startswith("502"))
        self.assertIn("missing columns", messages.output[0])
        self.assertNotIn(b"winner", body)

    def test_snapshot_route(self):
        with patch.object(server, "snapshot_bytes", return_value=b'{"players":["Alice"]}'):
            response, body = self.call("/api/snapshot")
        self.assertTrue(response["status"].startswith("200"))
        self.assertEqual(json.loads(body)["players"], ["Alice"])


if __name__ == "__main__":
    unittest.main()
