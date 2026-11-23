import copy
import io
import json
import os
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch

from backend import server
from backend.sheets_adapter import build_snapshot, playoff_history_standings
from test_backend import fixture


ROWS = [["User", "Alice", "Bob", "Former", "Missing"],
        ["Overall", "1,234", 12, 0, ""],
        ["Overall Unknown", 8, 3, 0, ""],
        ["2025 season", 99, 99, 99, 99]]


class PlayoffHistoryTests(unittest.TestCase):
    def test_actual_workbook_count_percentage_pairs_and_leading_spacers(self):
        users = "Christopher Nicholas Gregory Joseph Sara Emma Elise Kramer Laura Brent Lauren Hannah Hokie Doc DLT P_Smurf Jen".split()
        users[15] = "P Smurf"
        overall = [28, 26, 25, 26, 1, 22, 18, 3, 29, 4, 28, 5, 2, 1, 2, 21, 10]
        unknown = [9, 10, 9, 8, 0, 4, 5, 0, 8, 0, 8, 1, 1, 0, 0, 7, 3]
        header = [cell for user in users for cell in [user, ""]]
        totals = ["Overall", "", ""] + [cell for count in overall for cell in [count, f"{count / 52:.2%}"]]
        unknown_totals = ["Overall Unknown", "", ""] + [cell for count in unknown for cell in [count, f"{count / 24:.2%}"]]
        for prefix in ([], ["", "", ""]):
            entries = playoff_history_standings([prefix + header, totals, unknown_totals])
            self.assertEqual([entry["player"] for entry in entries], users)
            self.assertEqual([entry["correctPlayoff"] for entry in entries], overall)
            self.assertEqual([entry["correctUnknownPlayoff"] for entry in entries], unknown)
        totals[3] = ""
        entries = playoff_history_standings([header, totals, unknown_totals])
        self.assertIsNone(entries[0]["correctPlayoff"])
        self.assertEqual(entries[1]["correctPlayoff"], 26)

    def test_only_top_three_rows_supply_totals_without_dropping_former_users_or_zero(self):
        tables = fixture()
        tables["playoff_history"] = ROWS
        standings = build_snapshot(tables)["playoffStandings"]
        self.assertEqual(standings, [
            {"player": "Alice", "correctPlayoff": 1234, "correctUnknownPlayoff": 8},
            {"player": "Bob", "correctPlayoff": 12, "correctUnknownPlayoff": 3},
            {"player": "Former", "correctPlayoff": 0, "correctUnknownPlayoff": 0},
            {"player": "Missing", "correctPlayoff": None, "correctUnknownPlayoff": None},
        ])
        self.assertIsNone(build_snapshot(fixture())["playoffStandings"])

    def test_blank_trailing_columns_and_short_rows_preserve_alignment(self):
        self.assertEqual(playoff_history_standings([
            ["", "Alice", "", "Bob"], [" Overall Unknown ", 0], ["Overall", 2, 99, 5]]), [
                {"player": "Alice", "correctPlayoff": 2, "correctUnknownPlayoff": 0},
                {"player": "Bob", "correctPlayoff": 5, "correctUnknownPlayoff": None}])
        self.assertEqual(playoff_history_standings([]), [])

    def test_invalid_totals_or_labels_do_not_turn_into_fake_zero_counts(self):
        for value in [-1, "invalid", "1.5", "NaN"]:
            broken = copy.deepcopy(ROWS)
            broken[1][1] = value
            with self.assertRaises(ValueError):
                playoff_history_standings(broken)
        with self.assertRaisesRegex(ValueError, "Overall Unknown"):
            playoff_history_standings([["User", "Alice"], ["Overall", 4], ["Wrong", 2], ["Overall Unknown", 2]])
        with self.assertRaisesRegex(ValueError, "duplicate users"):
            playoff_history_standings([["User", "Alice", "Alice"], ["Overall", 4, 5], ["Overall Unknown", 2, 3]])

    def test_backend_reads_separate_history_workbook_and_only_three_rows(self):
        self.check_backend()

    def test_failed_history_access_keeps_the_main_snapshot_without_leaking_details(self):
        with self.assertLogs("mbcc", level="ERROR"):
            self.check_backend(fail=True)

    def check_backend(self, fail=False):
        tables = fixture()
        urls = []
        def read(request, timeout):
            urls.append(request.full_url)
            query = parse_qs(urlsplit(request.full_url).query)
            if "/history-file/" in request.full_url:
                self.assertEqual(query["ranges"], ["'playoff_picks'!1:3"])
                if fail:
                    raise OSError("private upstream token details")
                values = [{"values": ROWS[:3]}]
            else:
                self.assertIn("/challenge-file/", request.full_url)
                values = [{"values": tables[name.strip("'")]} for name in query["ranges"]]
            return io.BytesIO(json.dumps({"valueRanges": values}).encode())

        credentials = Mock(token="fixture-token")
        environment = {"MBCC_CHALLENGE_SHEET_ID": "challenge-file", "MBCC_HISTORY_SHEET_ID": "challenge-file",
                       "MBCC_PLAYOFF_HISTORY_SHEET_ID": "history-file", "MBCC_PLAYOFF_HISTORY_ENABLED": "1",
                       "MBCC_LIVE_SCORES_ENABLED": "0", "MBCC_UPDATES_ENABLED": "0", "MBCC_DEMO": "0",
                       "MBCC_WORKSHEET_TITLES": "{}"}
        with patch.dict(os.environ, environment), patch("google.auth.default", return_value=(credentials, None)), \
                patch.object(server, "urlopen", side_effect=read):
            snapshot = server.fetch_snapshot()
        self.assertEqual(len(urls), 2)
        self.assertEqual(snapshot["players"], ["Alice", "Bob"])
        if fail:
            self.assertIsNone(snapshot["playoffStandings"])
            self.assertIn("playoffStandingsError", snapshot)
            self.assertNotIn("private upstream", json.dumps(snapshot))
        else:
            self.assertEqual(snapshot["playoffStandings"][0]["correctPlayoff"], 1234)
