import copy
import io
import json
import os
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch

from backend import server
from backend.groups import GroupError, combine_snapshots, normalize_group
from backend.sheets_adapter import build_snapshot
from web_app import data, playoffs
from test_backend import fixture


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.main = build_snapshot(fixture())
        self.sub = copy.deepcopy(self.main)
        self.sub["standings"][0]["correct"] = 0
        self.sub["standings"][0]["overallScore"] = 0
        self.main["playoffStandings"] = [{"player": "Alice", "correctPlayoff": 4, "correctUnknownPlayoff": 0}]
        self.sub["playoffStandings"] = [{"player": "Alice", "correctPlayoff": 2, "correctUnknownPlayoff": 1}]

    def test_keywords_and_url_encoding(self):
        for raw, expected in (("", "default"), ("  ", "default"), ("DEFAULT", "default"),
                              (" Sub ", "sub"), (" DEFAULT+SUB ", "default+sub")):
            self.assertEqual(normalize_group(raw), expected)
            self.assertEqual(data.group_keyword(raw), expected)
        with self.assertRaises(GroupError):
            normalize_group("unknown")
        with self.assertRaises(data.SnapshotError):
            data.group_keyword("unknown")
        endpoint = "https://example.com/api/snapshot?other=&group=sub&other=two"
        parsed = parse_qs(urlsplit(data.group_endpoint(endpoint, "default+sub")).query, keep_blank_values=True)
        self.assertEqual(parsed, {"other": ["", "two"], "group": ["default+sub"]})
        self.assertNotIn("group", parse_qs(urlsplit(data.group_endpoint(endpoint, "default")).query))

    def test_combined_rosters_keep_distinct_stats_and_share_games(self):
        before_main, before_sub = copy.deepcopy(self.main), copy.deepcopy(self.sub)
        merged = combine_snapshots(self.main, self.sub)
        self.assertEqual(merged["group"], "default+sub")
        self.assertEqual(merged["players"], ["Alice [Main]", "Bob [Main]", "Alice [Sub]", "Bob [Sub]"])
        self.assertEqual(len(merged["games"]), len(self.main["games"]))
        self.assertEqual(set(merged["games"][0]["picks"]), set(merged["players"]))
        self.assertEqual(merged["progress"][0]["correct"]["Alice [Sub]"], self.sub["progress"][0]["correct"]["Alice"])
        self.assertEqual([row["correctPlayoff"] for row in merged["playoffStandings"]], [4])
        self.assertEqual(merged["playoffHistoryScope"], "main")
        self.assertEqual(merged["careers"][0]["player"], self.main["careers"][0]["player"] + " [Main]")
        self.assertTrue(merged["history"][-1]["player"].endswith("[Sub]"))
        self.assertTrue(merged["seasons"][0]["season"].endswith("[Main]"))
        self.assertGreater(data.ranked(merged)[0]["overallScore"], data.ranked(merged)[-1]["overallScore"])
        data.filter_current_players(merged)
        self.assertEqual(self.main, before_main)
        self.assertEqual(self.sub, before_sub)

    def test_incompatible_sources_fail_without_partial_merge(self):
        for field in ("season", "games", "progress", "score", "order"):
            broken = copy.deepcopy(self.sub)
            if field == "season":
                broken["season"] = "Different year"
            elif field in ("games", "progress"):
                broken[field].pop()
            elif field == "score":
                broken["games"][0]["homeScore"] = 999
            else:
                broken["games"].reverse()
            with self.subTest(field=field), self.assertRaises(GroupError):
                combine_snapshots(self.main, broken)

    def test_absent_subgroup_playoff_history_is_expected(self):
        self.sub["playoffStandings"] = None
        merged = combine_snapshots(self.main, self.sub)
        self.assertEqual(len(merged["playoffStandings"]), 1)
        self.assertNotIn("playoffStandingsError", merged)

    def test_main_playoff_history_failure_is_still_reported(self):
        self.main["playoffStandings"] = None
        self.main["playoffStandingsError"] = "Couldn’t load all-time playoff standings from the history spreadsheet."
        merged = combine_snapshots(self.main, self.sub)
        self.assertIsNone(merged["playoffStandings"])
        self.assertEqual(merged["playoffStandingsError"], self.main["playoffStandingsError"])

    def test_subgroup_does_not_display_inherited_playoff_totals(self):
        self.sub["group"] = "sub"
        self.assertEqual(playoffs.playoff_standings(self.sub), [])
        self.sub.pop("group")
        self.sub["playoffHistoryScope"] = "none"
        self.assertEqual(playoffs.playoff_standings(self.sub), [])

    def test_sub_workbook_routes_history_without_inheriting_main_history(self):
        env = {"MBCC_CHALLENGE_SHEET_ID": "main", "MBCC_HISTORY_SHEET_ID": "main-history",
               "MBCC_SUB_CHALLENGE_SHEET_ID": "sub", "MBCC_UPDATES_ENABLED": "1"}
        with patch.dict(os.environ, env, clear=True):
            groups = server.spreadsheet_groups("sub")
            self.assertEqual(list(groups), ["sub"])
            self.assertIn("basic_history", groups["sub"])
            self.assertNotIn("todays_update", groups["sub"])
            os.environ["MBCC_SUB_HISTORY_SHEET_ID"] = "sub-history"
            self.assertIn("basic_history", server.spreadsheet_groups("sub")["sub-history"])
            os.environ.pop("MBCC_SUB_CHALLENGE_SHEET_ID")
            with self.assertRaisesRegex(GroupError, "not configured"):
                server.spreadsheet_groups("sub")

    def test_sub_backend_reads_only_its_workbook(self):
        tables = fixture()
        def read(request, timeout):
            self.assertIn("/sub-file/", request.full_url)
            query = parse_qs(urlsplit(request.full_url).query)
            return io.BytesIO(json.dumps({"valueRanges": [{"values": tables[name.strip("'")]}
                                                         for name in query["ranges"]]}).encode())
        env = {"MBCC_SUB_CHALLENGE_SHEET_ID": "sub-file", "MBCC_HISTORY_SHEET_ID": "main-history",
               "MBCC_PLAYOFF_HISTORY_ENABLED": "1", "MBCC_LIVE_SCORES_ENABLED": "0",
               "MBCC_SUB_PLAYOFF_HISTORY_SHEET_ID": "obsolete-setting-must-not-be-read"}
        with patch.dict(os.environ, env, clear=True), \
                patch("google.auth.default", return_value=(Mock(token="test-token"), None)), \
                patch.object(server, "urlopen", side_effect=read) as fetch:
            snapshot = server.fetch_snapshot("sub")
        self.assertEqual(snapshot["group"], "sub")
        self.assertIsNone(snapshot["playoffStandings"])
        self.assertEqual(snapshot["playoffHistoryScope"], "none")
        self.assertNotIn("playoffStandingsError", snapshot)
        self.assertEqual(fetch.call_count, 1)

    def test_group_caches_are_independent_and_combined_reuses_them(self):
        def fetch(group="default"):
            return dict(copy.deepcopy(self.main if group == "default" else self.sub), group=group)
        with patch.object(server, "_cache", {}), patch.object(server, "fetch_snapshot", side_effect=fetch) as upstream:
            main = json.loads(server.snapshot_bytes())
            sub = json.loads(server.snapshot_bytes("sub"))
            both = json.loads(server.snapshot_bytes("default+sub"))
            server.snapshot_bytes("default+sub")
        self.assertEqual(upstream.call_count, 2)
        self.assertEqual(main["group"], "default")
        self.assertEqual(sub["group"], "sub")
        self.assertEqual(len(both["players"]), 4)

    def test_combined_cache_expires_with_its_oldest_source(self):
        with patch.object(server, "_cache", {
                "default": (120, json.dumps(self.main).encode()),
                "sub": (140, json.dumps(self.sub).encode())}), patch.object(server.time, "monotonic", return_value=100):
            server.snapshot_bytes("default+sub")
            self.assertEqual(server._cache["default+sub"][0], 120)

    def call(self, query):
        response = {}
        def start(status, headers):
            response["status"] = status
        body = b"".join(server.application({"PATH_INFO": "/api/snapshot", "REQUEST_METHOD": "GET",
                                           "QUERY_STRING": query}, start))
        return response["status"], json.loads(body)

    def test_api_group_selection_and_rejection(self):
        with patch.object(server, "snapshot_bytes", return_value=b'{}') as fetch:
            self.assertEqual(self.call("group=default%2Bsub")[0], "200 OK")
            fetch.assert_called_once_with("default+sub")
            for query in ("group=bad", "group=sub&group=default", "group=default+sub"):
                self.assertEqual(self.call(query)[0], "400 Bad Request")
        with patch.object(server, "snapshot_bytes", side_effect=GroupError("Subgroup not configured")):
            status, body = self.call("group=sub")
            self.assertEqual(status, "409 Conflict")
            self.assertEqual(body["error"], "Subgroup not configured")

    def test_client_shows_configuration_errors_without_ignoring_group(self):
        error = HTTPError(data.DEFAULT_ENDPOINT, 409, "Conflict", {}, io.BytesIO(b'{"error":"Subgroup not configured"}'))
        with patch.object(data, "urlopen", side_effect=error):
            with self.assertRaisesRegex(data.SnapshotError, "Subgroup not configured"):
                data.fetch_api(data.DEFAULT_ENDPOINT)

    def test_backend_failures_identify_the_requested_group_without_leaking_response_details(self):
        for group, label in data.GROUP_LABELS.items():
            endpoint = data.group_endpoint(data.DEFAULT_ENDPOINT, group)
            error = HTTPError(endpoint, 502, "Bad Gateway", {}, io.BytesIO(b'private upstream details'))
            with self.subTest(group=group), patch.object(data, "urlopen", side_effect=error):
                with self.assertRaises(data.SnapshotError) as caught:
                    data.fetch_api(endpoint)
                self.assertIn(label.lower(), str(caught.exception))
                self.assertIn("HTTP 502", str(caught.exception))
                self.assertNotIn("private", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
