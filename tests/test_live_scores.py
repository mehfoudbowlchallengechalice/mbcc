import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from backend.sheets_adapter import LIVE_COLUMNS, build_snapshot
from backend import server
from test_backend import fixture, worksheet

NOW = datetime(2026, 10, 29, 18, tzinfo=timezone.utc)


def live_fixture(status="final", home=14, away=21):
    tables = fixture()
    tables["live_scores_and_games"] = worksheet([{
        "game_id": "401234567", "game_name": "Bowl", "game_date": "2025-12-20", "game_time": "7:30 PM",
        "game_venue": "Stadium", "game_network": "ESPN", "game_home_team": "Home", "game_away_team": "Away",
        "home_team_score": home, "away_team_score": away, "status": status,
        "point_difference": abs(home - away) if isinstance(home, int) and isinstance(away, int) else "",
        "winner": "Away" if status == "final" else "TBD",
        "upset_indicator": 1, "unanimous_indicator": 0, "team_focus_indicator": 1,
        "source": "ESPN", "last_fetched_at": NOW.isoformat(), "fetch_error": "",
        "schedule_source": "ESPN", "schedule_fetched_at": NOW.isoformat(),
        "verified": False, "game_verified": False,
    }])
    return tables


def set_cell(tables, sheet, key, value):
    tables[sheet][1][tables[sheet][0].index(key)] = value
    if key in {"home_team_score", "away_team_score"} and "point_difference" in tables[sheet][0]:
        row = dict(zip(tables[sheet][0], tables[sheet][1]))
        home, away = row.get("home_team_score"), row.get("away_team_score")
        difference = abs(home - away) if isinstance(home, int) and isinstance(away, int) else ""
        tables[sheet][1][tables[sheet][0].index("point_difference")] = difference


class LiveScoreTests(unittest.TestCase):
    def game(self, tables):
        return build_snapshot(tables, now=NOW)["games"][0]

    def test_unused_rows_with_checkboxes_and_formula_results_are_not_games(self):
        tables = live_fixture()
        headers = tables["live_scores_and_games"][0]
        for output in ({"verified": "FALSE", "game_verified": "FALSE"},
                       {"verified": False, "game_verified": False, "point_difference": 0,
                        "upset_indicator": 0, "unanimous_indicator": 0, "team_focus_indicator": 0,
                        "status": "scheduled", "source": "ESPN", "winner": "TBD"}):
            tables["live_scores_and_games"].append([output.get(key, "") for key in headers])
        snapshot = build_snapshot(tables, now=NOW)
        self.assertEqual(len(snapshot["games"]), 1)
        self.assertEqual(snapshot["games"][0]["name"], "Bowl")
        tables["live_scores_and_games"] = [headers] + tables["live_scores_and_games"][2:]
        self.assertEqual(build_snapshot(tables, now=NOW)["games"], [])

    def test_real_game_rows_with_missing_names_still_report_the_problem(self):
        for identity in ("game_id", "game_date"):
            tables = live_fixture()
            headers = tables["live_scores_and_games"][0]
            bad = {identity: "401999999" if identity == "game_id" else "2026-12-12"}
            tables["live_scores_and_games"].append([bad.get(key, "") for key in headers])
            with self.assertRaisesRegex(ValueError, r"game_name is required at row 3"):
                self.game(tables)
            tables["live_scores_and_games"].insert(1, [""] * len(headers))
            with self.assertRaisesRegex(ValueError, r"game_name is required at row 4"):
                self.game(tables)

    def test_verified_automatically_for_matching_ongoing_or_final_scores(self):
        self.assertEqual(self.game(live_fixture())["verification"], "verified")
        for status in ("live", "delayed", "suspended"):
            tables = live_fixture(status=status)
            set_cell(tables, "scores", "winner", "TBD")
            game = self.game(tables)
            self.assertEqual(game["verification"], "verified")
            self.assertIsNone(game["winner"])

    def test_missing_feed_never_inherits_legacy_final_as_verification(self):
        self.assertEqual(self.game(fixture())["verification"], "unavailable")

    def test_any_score_difference_is_a_mismatch(self):
        self.assertEqual(self.game(live_fixture(home=17))["verification"], "mismatch")
        self.assertEqual(self.game(live_fixture(away=24))["verification"], "mismatch")
        tables = live_fixture()
        set_cell(tables, "scores", "winner", "Home")
        self.assertEqual(self.game(tables)["verification"], "verified")

    def test_human_score_edits_automatically_change_verification(self):
        tables = live_fixture(home=17)
        self.assertEqual(self.game(tables)["verification"], "mismatch")
        set_cell(tables, "scores", "home_team_score", 17)
        self.assertEqual(self.game(tables)["verification"], "verified")

    def test_live_tab_supplies_scores_without_changing_originals_or_summary_tabs(self):
        tables = live_fixture(status="live", home=28, away=21)
        original_tables = copy.deepcopy(tables)
        snapshot = build_snapshot(tables, now=NOW)
        game = snapshot["games"][0]
        self.assertEqual((game["homeScore"], game["awayScore"], game["winner"]), (28, 21, None))
        self.assertEqual(game["live"]["homeScore"], 28)
        self.assertEqual(snapshot["standings"], build_snapshot(fixture(), now=NOW)["standings"])
        self.assertEqual(tables, original_tables)
        self.assertEqual(snapshot["gamesSource"], "live_scores_and_games")

    def test_final_without_human_scores_is_not_verified(self):
        tables = live_fixture()
        for key, value in (("home_team_score", ""), ("away_team_score", ""), ("winner", "TBD")):
            set_cell(tables, "scores", key, value)
        game = self.game(tables)
        self.assertEqual(game["verification"], "pending")
        self.assertEqual(game["homeScore"], 14)
        self.assertEqual(game["winner"], "Away")
        self.assertEqual(game["live"]["homeScore"], 14)

    def test_zero_is_a_real_score_but_blank_live_scores_are_not_zero(self):
        tables = live_fixture(home=0)
        self.assertEqual(self.game(tables)["live"]["homeScore"], 0)
        set_cell(tables, "scores", "home_team_score", 0)
        self.assertEqual(self.game(tables)["verification"], "verified")
        set_cell(tables, "live_scores_and_games", "home_team_score", "")
        self.assertIsNone(self.game(tables)["homeScore"])
        self.assertEqual(self.game(tables)["fieldVerification"]["homeScore"]["status"], "pending")

    def test_stale_or_failed_feed_retains_values_but_never_verifies(self):
        for status, age in (("live", timedelta(minutes=11)), ("final", timedelta(hours=49))):
            tables = live_fixture(status=status)
            set_cell(tables, "live_scores_and_games", "last_fetched_at", (NOW - age).isoformat())
            game = self.game(tables)
            self.assertEqual(game["verification"], "unavailable")
            self.assertEqual(game["live"]["awayScore"], 21)
        tables = live_fixture()
        set_cell(tables, "live_scores_and_games", "fetch_error", "Request failed")
        self.assertEqual(self.game(tables)["verification"], "unavailable")

    def test_missing_bad_future_and_naive_timestamps_do_not_verify(self):
        for value in ("", "bad", "2026-10-29T18:00:00", (NOW + timedelta(minutes=2)).isoformat()):
            tables = live_fixture()
            set_cell(tables, "live_scores_and_games", "last_fetched_at", value)
            self.assertEqual(self.game(tables)["verification"], "pending" if value == "" else "unavailable")

    def test_malformed_score_does_not_supply_a_fake_zero_or_affect_other_fields(self):
        for key, value, field in (("home_team_score", -1, "homeScore"), ("away_team_score", "NaN", "awayScore")):
            tables = live_fixture()
            set_cell(tables, "live_scores_and_games", key, value)
            self.assertEqual(self.game(tables)["verification"], "unavailable")
            self.assertEqual(self.game(tables)["fieldVerification"][field]["status"], "unavailable")
            self.assertEqual(self.game(tables)["gameVerification"], "verified")

    def test_invalid_or_duplicate_primary_identity_fails_explicitly(self):
        tables = live_fixture()
        set_cell(tables, "live_scores_and_games", "game_id", "other")
        with self.assertRaises(ValueError):
            self.game(tables)
        tables = live_fixture()
        tables["live_scores_and_games"].append(tables["live_scores_and_games"][1][:])
        with self.assertRaisesRegex(ValueError, "Duplicate game"):
            self.game(tables)
        for feed in ([], [["bad"]]):
            tables["live_scores_and_games"] = feed
            with self.assertRaises(ValueError):
                self.game(tables)
        tables["live_scores_and_games"] = [list(LIVE_COLUMNS)]
        self.assertEqual(build_snapshot(tables, now=NOW)["games"], [])

    def test_entire_game_list_and_metadata_come_from_live_tab(self):
        tables = live_fixture()
        for key, value in (("game_name", "New name"), ("game_date", "2026-12-12"), ("game_time", "12:00 PM"),
                           ("game_venue", "New venue"), ("game_network", "ABC"), ("game_home_team", "New home"),
                           ("upset_indicator", 0), ("unanimous_indicator", 1), ("team_focus_indicator", 0)):
            set_cell(tables, "live_scores_and_games", key, value)
        snapshot = build_snapshot(tables, now=NOW)
        self.assertEqual(len(snapshot["games"]), 1)  # Original has two; it cannot supply the game list.
        game = snapshot["games"][0]
        self.assertEqual((game["name"], game["venue"], game["network"], game["homeTeam"]),
                         ("New name", "New venue", "ABC", "New home"))
        self.assertEqual(game["startTime"], "2026-12-12T12:00:00-05:00")
        self.assertFalse(game["upset"])
        self.assertTrue(game["unanimous"])
        self.assertEqual(game["focusTeam"], "New home")
        self.assertEqual(game["picks"], {"Alice": "Home", "Bob": "Away"})  # Joined by original event ID.
        for field in ("homeTeam", "startTime"):
            self.assertEqual(game["fieldVerification"][field]["status"], "mismatch", field)

    def test_each_field_is_verified_independently(self):
        game = self.game(live_fixture(home=17))
        checks = game["fieldVerification"]
        self.assertEqual(checks["homeScore"]["status"], "mismatch")
        self.assertEqual(checks["homeScore"]["originalValue"], "14")
        self.assertEqual(checks["homeScore"]["value"], "17")
        self.assertEqual(checks["awayScore"]["status"], "verified")
        self.assertEqual(game["gameVerification"], "verified")
        for field in ("upset", "unanimous", "focusTeam"):
            self.assertNotIn(field, checks)  # Formula outputs do not have verification.

    def test_formula_indicators_display_without_comparing_to_originals(self):
        tables = live_fixture()
        for key, value in (("upset_indicator", 0), ("unanimous_indicator", 1), ("team_focus_indicator", 0)):
            set_cell(tables, "live_scores_and_games", key, value)
        game = self.game(tables)
        self.assertEqual((game["upset"], game["unanimous"], game["focusTeam"]), (False, True, "Home"))
        self.assertEqual(game["verification"], "verified")
        for field in ("upset", "unanimous", "focusTeam"):
            self.assertNotIn(field, game["fieldVerification"])

    def test_winner_displays_from_live_tab_without_a_separate_check(self):
        tables = live_fixture()
        set_cell(tables, "scores", "winner", "Home")
        game = self.game(tables)
        self.assertEqual(game["winner"], "Away")
        self.assertNotIn("winner", game["fieldVerification"])
        self.assertEqual(game["verification"], "verified")  # Scores themselves match.

    def test_new_season_games_are_visible_without_old_season_picks_or_verification(self):
        tables = live_fixture()
        set_cell(tables, "live_scores_and_games", "game_id", "401999999")
        game = self.game(tables)
        self.assertEqual(game["name"], "Bowl")
        self.assertEqual(game["homeScore"], 14)
        self.assertEqual(game["picks"], {})
        self.assertEqual(game["gameVerification"], "pending")
        self.assertEqual(game["verification"], "pending")

    def test_blank_primary_values_never_fall_back_to_originals(self):
        tables = live_fixture(status="scheduled", home="", away="")
        for key in ("game_venue", "game_network", "upset_indicator", "unanimous_indicator", "team_focus_indicator"):
            set_cell(tables, "live_scores_and_games", key, "")
        game = self.game(tables)
        self.assertEqual(game["venue"], "")
        self.assertEqual(game["network"], "")
        self.assertIsNone(game["homeScore"])
        self.assertIsNone(game["upset"])
        self.assertIsNone(game["focusTeam"])

    def test_schedule_freshness_is_independent_of_score_freshness(self):
        tables = live_fixture(status="live")
        set_cell(tables, "live_scores_and_games", "last_fetched_at", (NOW - timedelta(minutes=11)).isoformat())
        checks = self.game(tables)["fieldVerification"]
        self.assertEqual(checks["homeScore"]["status"], "unavailable")
        self.assertEqual(self.game(tables)["gameVerification"], "verified")
        set_cell(tables, "live_scores_and_games", "schedule_fetched_at", (NOW - timedelta(hours=49)).isoformat())
        self.assertEqual(self.game(tables)["gameVerification"], "unavailable")

    def test_five_minute_polling_has_a_freshness_buffer(self):
        tables = live_fixture(status="live")
        set_cell(tables, "live_scores_and_games", "last_fetched_at", (NOW - timedelta(minutes=6)).isoformat())
        game = self.game(tables)
        self.assertEqual(game["verification"], "verified")
        self.assertEqual(game["fieldVerification"]["homeScore"]["maxAgeSeconds"], 600)

    def test_settled_upcoming_schedule_remains_comparable_after_checks_stop(self):
        tables = live_fixture(status="scheduled", home="", away="")
        for sheet in ("unlive_games", "live_scores_and_games"):
            set_cell(tables, sheet, "game_date", "2026-12-12")
        for key in ("last_fetched_at", "schedule_fetched_at"):
            set_cell(tables, "live_scores_and_games", key, (NOW - timedelta(days=7)).isoformat())
        game = self.game(tables)
        self.assertEqual(game["gameVerification"], "verified")
        self.assertIsNone(game["fieldVerification"]["startTime"]["maxAgeSeconds"])
        self.assertNotEqual(game["verification"], "verified")
        set_cell(tables, "unlive_games", "game_home_team", "Other")
        self.assertEqual(self.game(tables)["gameVerification"], "mismatch")
        for column, value in (("game_time", "TBD"), ("game_home_team", "TBD"), ("last_fetched_at", "")):
            incomplete = copy.deepcopy(tables)
            set_cell(incomplete, "live_scores_and_games", column, value)
            self.assertEqual(self.game(incomplete)["gameVerification"], "pending" if column == "last_fetched_at" else "unavailable")

    def test_imported_games_and_scores_are_unverified_until_the_first_automatic_check(self):
        tables = live_fixture()
        set_cell(tables, "live_scores_and_games", "last_fetched_at", "")
        # Even matching imported values and manually checked cells cannot verify an unchecked feed.
        set_cell(tables, "live_scores_and_games", "verified", True)
        set_cell(tables, "live_scores_and_games", "game_verified", True)
        game = self.game(tables)
        self.assertEqual((game["gameVerification"], game["verification"]), ("pending", "pending"))
        self.assertTrue(all(check["status"] == "pending" for check in game["fieldVerification"].values()))
        self.assertEqual(build_snapshot(tables, now=NOW)["gamesSource"], "live_scores_and_games")

    def test_confirmed_finals_stay_verified_without_polling_but_still_compare_references(self):
        tables = live_fixture()
        for key in ("verified", "game_verified"):
            set_cell(tables, "live_scores_and_games", key, True)
        for key in ("last_fetched_at", "schedule_fetched_at"):
            set_cell(tables, "live_scores_and_games", key, (NOW - timedelta(days=30)).isoformat())
        game = self.game(tables)
        self.assertEqual((game["verification"], game["gameVerification"]), ("verified", "verified"))
        self.assertTrue(all(check["maxAgeSeconds"] is None for check in game["fieldVerification"].values()))
        set_cell(tables, "scores", "point_difference", 8)
        self.assertEqual(self.game(tables)["verification"], "mismatch")
        set_cell(tables, "unlive_games", "game_home_team", "Other")
        self.assertEqual(self.game(tables)["gameVerification"], "mismatch")
        set_cell(tables, "live_scores_and_games", "fetch_error", "HTTP 403")
        self.assertEqual(self.game(tables)["verification"], "unavailable")

    def test_point_difference_is_included_in_the_existing_score_check(self):
        tables = live_fixture(status="live")
        self.assertEqual(self.game(tables)["pointDifference"], 7)
        set_cell(tables, "scores", "point_difference", 8)
        game = self.game(tables)
        self.assertEqual(game["verification"], "mismatch")
        self.assertEqual(game["gameVerification"], "verified")
        for bad, expected in (("", "pending"), ("NaN", "unavailable"), (-1, "unavailable")):
            set_cell(tables, "scores", "point_difference", bad)
            self.assertEqual(self.game(tables)["verification"], expected)
        set_cell(tables, "scores", "point_difference", 7)
        set_cell(tables, "live_scores_and_games", "point_difference", 8)
        self.assertEqual(self.game(tables)["verification"], "mismatch")

    def test_only_kickoff_and_opponents_affect_game_verification(self):
        for column, value in (("game_time", "8:30 PM"), ("game_date", "2025-12-21"),
                              ("game_home_team", "Other"), ("game_away_team", "Other")):
            tables = live_fixture()
            set_cell(tables, "live_scores_and_games", column, value)
            game = self.game(tables)
            self.assertEqual(game["gameVerification"], "mismatch", column)
            self.assertEqual(game["verification"], "verified", column)
        tables = live_fixture()
        for column in ("game_name", "game_venue", "game_network"):
            set_cell(tables, "live_scores_and_games", column, "Changed")
        game = self.game(tables)
        self.assertEqual(game["gameVerification"], "verified")
        self.assertEqual(set(game["fieldVerification"]),
                         {"startTime", "homeTeam", "awayTeam", "homeScore", "awayScore", "pointDifference"})

    def test_tbd_kickoff_stays_unknown_and_does_not_fake_a_midnight_match(self):
        tables = live_fixture(status="scheduled", home="", away="")
        set_cell(tables, "live_scores_and_games", "game_time", "TBD")
        game = self.game(tables)
        self.assertFalse(game["kickoffTimeKnown"])
        self.assertEqual(game["fieldVerification"]["startTime"]["status"], "pending")

    def test_invalid_duplicate_or_absent_originals_do_not_replace_live_values(self):
        tables = live_fixture()
        tables["scores"].append(tables["scores"][1][:])
        game = self.game(tables)
        self.assertEqual(game["homeScore"], 14)
        self.assertEqual(game["fieldVerification"]["homeScore"]["status"], "pending")
        tables["unlive_games"] = [["bad"]]
        self.assertEqual(self.game(tables)["picks"], {})

    def test_live_tab_opt_in_and_alias(self):
        with patch.dict("os.environ", {"MBCC_CHALLENGE_SHEET_ID": "challenge", "MBCC_HISTORY_SHEET_ID": "challenge",
                                      "MBCC_LIVE_SCORES_ENABLED": "1"}):
            self.assertIn("live_scores_and_games", server.spreadsheet_groups()["challenge"])
        with patch.dict("os.environ", {"MBCC_WORKSHEET_TITLES": '{"live_scores_and_games":"Live"}'}):
            self.assertEqual(server.worksheet_titles()["live_scores_and_games"], "Live")


if __name__ == "__main__":
    unittest.main()
