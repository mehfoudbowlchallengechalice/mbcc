"""Exercise real Streamlit screens without Google access or a running backend."""
import copy
import importlib.util
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from web_app import data, playoffs
from test_web_models import playoff_fixture

AVAILABLE = importlib.util.find_spec("streamlit") is not None
if AVAILABLE:
    import streamlit as st
    from streamlit.testing.v1 import AppTest


@unittest.skipUnless(AVAILABLE, "Install requirements.txt to run Streamlit interaction checks")
class StreamlitAppTests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()
        self.environment = patch.dict(os.environ, {"MBCC_DEMO": "1"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.snapshot = data.read_demo()
        self.snapshot["updates"] = [
            {"title": "Latest briefing", "publishedDate": "2026-11-19", "message": "First paragraph.\n\nSecond paragraph.", "youtubeURL": "https://youtu.be/dQw4w9WgXcQ"},
            {"title": "Previous briefing", "publishedDate": "2026-11-18", "message": "Earlier news", "youtubeURL": "https://youtu.be/abcdefghijk"},
        ]
        self.demo_patch = patch("web_app.data.read_demo", return_value=self.snapshot)
        self.demo_patch.start()
        self.addCleanup(self.demo_patch.stop)
        self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=15).run()
        self.assert_clean()

    def assert_clean(self):
        self.assertEqual([error.message for error in self.app.exception], [])

    def page(self, name):
        self.app.radio(key="primary_nav_value").set_value(name).run()
        self.assert_clean()

    def text(self):
        return "\n".join(element.value for element in self.app.markdown)

    def test_navigation_scores_charts_filters_history_and_trophy_cabinet(self):
        self.assertIn("Latest briefing", [heading.value for heading in self.app.subheader])
        self.assertIn("DEMO", self.app.info[0].value)
        self.page("Standings")
        self.assertTrue(any("Correct picks are the official score" in item.value for item in self.app.caption))
        self.app.radio(key="standings_metric").set_value("Point difference").run()
        self.assert_clean()
        self.page("Season")
        self.assertTrue(self.app.get("arrow_vega_lite_chart"))
        self.app.radio(key="progress_metric").set_value("Point chaos").run()
        self.app.multiselect(key="season_players").set_value([]).run()
        self.assert_clean()
        self.assertTrue(any("Choose players" in item.value for item in self.app.info))
        self.page("History")
        self.app.toggle(key="history_former").set_value(True).run()
        self.app.toggle(key="history_more").set_value(True).run()
        self.assert_clean()
        self.assertIn("Player career breakdown", [heading.value for heading in self.app.subheader])
        self.page("Info")
        self.assertIn("The trophy cabinet", [heading.value for heading in self.app.subheader])

    def test_blog_archive_and_game_detail_navigation(self):
        self.app.button(key="all_updates").click().run()
        self.assert_clean()
        headings = [heading.value for heading in self.app.subheader]
        self.assertIn("Previous briefing", headings)
        self.assertIn("Previous updates", headings)
        self.assertIn('target="_blank"', self.text())
        self.app.button(key="back_updates").click().run()
        self.assert_clean()
        game = data.filtered_games(self.snapshot["games"], "All")[0]
        self.app.button(key="game_" + game["id"]).click().run()
        self.assert_clean()
        self.assertIn("Everyone’s picks", [heading.value for heading in self.app.subheader])
        self.assertEqual(len(self.app.multiselect(key="game_players").value), len(self.snapshot["players"]))
        self.page("Standings")
        self.assertEqual(self.app.title[0].value, "Standings")

    def test_bracket_results_player_picks_and_return_from_game_details(self):
        self.page("Bracket")
        self.assertIn("isn’t available yet", self.app.info[-1].value)
        self.snapshot.update(playoff_fixture(self.snapshot))
        st.cache_data.clear()
        self.app.run()
        self.assert_clean()
        text = self.text()
        for title in playoffs.PLAYOFF_ROUNDS:
            self.assertIn(title, text)
        self.assertEqual(text.count('<article class="bracket-game">'), 11)
        self.assertIn("<strong>0</strong>", text)
        self.assertIn("TBD", text)
        self.assertNotIn("National champion:", text)
        self.app.selectbox(key="bracket_player").set_value("Christopher").run()
        self.assert_clean()
        self.assertIn("✓ Correct", self.text())
        self.app.selectbox(key="bracket_player").set_value("Elise").run()
        self.assertIn("✕ Incorrect", self.text())
        self.app.selectbox(key="bracket_player").set_value("Emma").run()
        self.assertIn("No pick", self.text())
        self.app.button(key="bracket_details").click().run()
        self.assert_clean()
        self.assertEqual(self.app.title[0].value, "Game details")
        self.assertEqual(self.app.button(key="back_game").label, "← Back to Bracket")
        self.app.button(key="back_game").click().run()
        self.assert_clean()
        self.assertEqual(self.app.title[0].value, "Bracket")
        self.assertEqual(self.app.selectbox(key="bracket_player").value, "Emma")

    def test_failed_live_connection_never_uses_demo_and_switching_clears_saved_data(self):
        with patch("web_app.data.fetch_api", side_effect=OSError("private upstream error")):
            self.app.radio(key="data_source").set_value("iPhone backend").run()
        self.assert_clean()
        self.assertIn("Connect to MBCC", [heading.value for heading in self.app.subheader])
        self.assertFalse(self.app.info)
        self.assertNotIn("private upstream", " ".join(item.value for item in self.app.warning))

    def test_failed_refresh_retains_the_same_connection_and_recomputes_verification(self):
        fresh = copy.deepcopy(self.snapshot)
        fresh["isDemo"] = False
        fresh["gamesSource"] = "live_scores_and_games"
        with patch("web_app.data.fetch_api", return_value=fresh):
            self.app.radio(key="data_source").set_value("iPhone backend").run()
        self.assert_clean()
        st.cache_data.clear()
        with patch("web_app.data.fetch_api", side_effect=OSError("network unavailable")):
            self.app.run()
        self.assert_clean()
        self.assertIn("last saved results", self.app.warning[0].value)
        self.assertIn("The games", [heading.value for heading in self.app.subheader])

    def test_existing_google_sheets_connection_uses_the_shared_adapter(self):
        import pandas as pd
        from test_live_scores import live_fixture
        tables = live_fixture()
        tables["todays_update"] = [
            ["published_date", "title", "message", "youtube_url"],
            ["2026-11-19", "Sheet briefing", "Published from the worksheet", ""],
        ]
        connection = Mock()
        connection.read.side_effect = lambda worksheet, ttl: pd.DataFrame(tables[worksheet][1:], columns=tables[worksheet][0])
        with patch("streamlit.connection", return_value=connection):
            self.app.radio(key="data_source").set_value("Google Sheets").run()
        self.assert_clean()
        self.assertFalse(self.app.warning)
        self.assertIn("Sheet briefing", [heading.value for heading in self.app.subheader])
        self.assertEqual(len(connection.read.call_args_list), 11)
        self.assertIn("Scores", self.text())
