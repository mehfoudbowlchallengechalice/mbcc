"""Check Streamlit at phone and desktop widths using isolated test responses.

Install optional tooling with: python -m pip install playwright
Then: python -m playwright install chromium
Fixture mode starts its own local test app. Use --live with an existing preview.
No external services are modified.
"""
import argparse
import copy
import json
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8501")
    parser.add_argument("--output", default="outputs/streamlit")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--live", action="store_true", help="Read and inspect the real API source instead of selecting the fictional fixture")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    fixture = json.loads((Path(__file__).resolve().parents[1] / "ios/MBCC/demo.json").read_text())
    fixture["updates"] = [
        {"title": "The chase for the chalice begins.", "publishedDate": "2026-11-20",
         "message": "Bowl season is around the corner. Your daily briefing starts here.\n\nThis is a fictional preview post with a sample YouTube link.",
         "youtubeURL": "https://www.youtube.com/watch?v=M7lc1UVf-VE"},
        {"title": "A new season, a familiar tradition.", "publishedDate": "2026-11-19",
         "message": "An earlier sample post, preserved in the archive.", "youtubeURL": "https://youtu.be/M7lc1UVf-VE"},
    ]
    fixture["isDemo"] = False
    fixture["gamesSource"] = "live_scores_and_games"
    fixture["playoffStandings"] = [
        {"player": player, "correctPlayoff": 20 + index, "correctUnknownPlayoff": index}
        for index, player in enumerate(fixture["players"])
    ] + [{"player": "Former player", "correctPlayoff": 0, "correctUnknownPlayoff": None}]
    fixture["playoffStandings"][0]["correctPlayoff"] = 2
    fixture["playoffStandings"][1]["correctPlayoff"] = 10
    fixture["playoffStandings"][2]["correctPlayoff"] = 9
    # An explicitly fictional bracket exercises all rounds, final/live scores,
    # pending teams, and player picks without changing the bundled demo season.
    names = ([f"College Football Playoff First Round Game ({i + 1})" for i in range(4)]
             + [f"College Football Playoff Quarterfinal at the {bowl} Bowl" for bowl in ("Fiesta", "Cotton", "Rose", "Peach")]
             + [f"College Football Playoff Semifinal at the {bowl} Bowl" for bowl in ("Orange", "Sugar")]
             + ["College Football Playoff National Championship"])
    for index, name in enumerate(names):
        game = copy.deepcopy(fixture["games"][0])
        game.update(id=f"playoff-{index}", name=name, startTime=f"2026-12-{index + 1:02d}T20:00:00-05:00",
                    homeTeam="Virginia Tech" if index < 8 else "TBD", awayTeam="Tulane" if index < 8 else "TBD",
                    homeScore=0 if index < 4 else None, awayScore=7 if index < 4 else None,
                    winner="Tulane" if index < 4 else None, picks={player: "Tulane" for player in fixture["players"]})
        fixture["games"].append(game)
    temporary = tempfile.TemporaryDirectory(prefix="mbcc-browser-checks-")
    process = None
    if not args.live:
        root = Path(__file__).resolve().parents[1]
        runner = Path(temporary.name) / "app.py"
        runner.write_text(
            "import sys, json, copy, runpy\n"
            + f"sys.path.insert(0, {str(root)!r})\n"
            + "from web_app import data\n"
            + f"fixture = json.loads({json.dumps(fixture)!r})\n"
            + "data.fetch_api = lambda endpoint, keyword='': copy.deepcopy(fixture)\n"
            + f"runpy.run_path({str(root / 'app.py')!r}, run_name='__main__')\n"
        )
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        args.url = f"http://127.0.0.1:{port}"
        process = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(runner),
                                    "--server.port", str(port), "--server.address", "127.0.0.1",
                                    "--server.headless", "true"], cwd=root,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        if process:
            for attempt in range(200):
                if process.poll() is not None:
                    raise RuntimeError("The isolated Streamlit preview failed to start.")
                try:
                    with urlopen(args.url + "/_stcore/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("The isolated Streamlit preview did not become ready.")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for label, width, height in [("iphone", 390, 844), ("small-phone", 320, 720), ("desktop", 1440, 1000)]:
                page = browser.new_page(viewport={"width": width, "height": height}, timezone_id="America/New_York",
                                        permissions=["clipboard-read", "clipboard-write"])
                page.goto(args.url)
                if args.live:
                    page.locator(".season-hero").wait_for()
                    assert not page.get_by_test_id("stException").count()
                    assert not page.get_by_text("DEMO · Sample results, not real standings", exact=True).count()
                    page.screenshot(path=str(output / f"real-live-{label}.png"))
                    page.locator(".st-key-primary_nav").get_by_text("Standings", exact=True).click()
                    page.get_by_role("heading", name="The race for the chalice", exact=True).wait_for()
                    page.screenshot(path=str(output / f"real-standings-{label}.png"))
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    print(f"Passed live backend {label}: real Live and Standings screens, no demo fallback, no horizontal overflow")
                    page.close()
                    continue
                page.get_by_role("heading", name="The chase for the chalice begins.", exact=True).wait_for()
                if args.inspect:
                    page.screenshot(path=str(output / "inspect.png"), full_page=True)
                    print(page.locator("button").evaluate_all("items => items.map(item => ({text:item.innerText, label:item.getAttribute('aria-label'), title:item.getAttribute('title')}))"))
                    print(page.locator(".st-key-primary_nav").bounding_box())
                    print(page.locator('[data-testid="stVerticalBlock"]').evaluate_all("items => items.slice(0,8).map(item=>({tag:item.tagName,style:item.getAttribute('style'),classes:item.className,testid:item.parentElement.getAttribute('data-testid')}))"))
                    print(page.locator('.st-key-primary_nav [role="radiogroup"]').evaluate("item => ({width:item.clientWidth,html:item.outerHTML.slice(0,3500)})"))
                    return
                page.locator("button").filter(has_text="keyboard_double_arrow_right").click()
                sidebar = page.get_by_test_id("stSidebar")
                sidebar.get_by_text("Current players only", exact=True).click()
                assert not sidebar.get_by_role("textbox", name="Snapshot URL").count()
                assert not sidebar.get_by_text("Demo", exact=True).count()
                assert not sidebar.get_by_text("Data source", exact=True).count()
                page.get_by_role("heading", name="The chase for the chalice begins.").wait_for()
                page.locator("button").filter(has_text="keyboard_double_arrow_left").click()
                page.wait_for_function("() => { const sidebar = document.querySelector('[data-testid=stSidebar]'); return !sidebar || sidebar.getBoundingClientRect().right <= 1; }")
                nav = page.locator(".st-key-primary_nav")
                page.screenshot(path=str(output / f"live-{label}.png"), full_page=True)
                page.get_by_role("button", name="View all updates →").click()
                page.get_by_role("heading", name="Previous updates", exact=True).wait_for()
                assert page.locator("a.video-card").count() == 2
                assert page.locator("a.video-card").first.get_attribute("target") == "_blank"
                page.screenshot(path=str(output / f"updates-{label}.png"), full_page=True)
                for screen in ["Standings", "Bracket", "Season", "History", "Info", "Live"]:
                    nav.get_by_text(screen, exact=True).click()
                    heading = "MBCC" if screen == "Live" else screen
                    page.get_by_role("heading", name=heading, exact=True).wait_for()
                    assert not page.get_by_test_id("stException").count()
                    bounds = nav.bounding_box()
                    assert bounds["x"] >= -1 and bounds["x"] + bounds["width"] <= width + 1, bounds
                    assert bounds["y"] + bounds["height"] <= height + 1, bounds
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), screen
                    if screen == "Bracket":
                        page.locator(".bracket-game").first.wait_for()
                        page.get_by_test_id("stDataFrame").wait_for()
                        assert page.locator(".bracket-game").count() == 11
                        assert page.locator(".bracket-round").count() == 4
                        page.get_by_test_id("stSelectbox").filter(has_text="Show picks for").get_by_text("Results only", exact=True).wait_for()
                        assert page.locator(".bracket-round-title").first.evaluate("el => getComputedStyle(el).fontSize") == "19px"
                        region = page.get_by_role("region", name="Playoff bracket by round")
                        assert region.evaluate("el => el.scrollWidth > el.clientWidth")
                        for name in ["Live", "Standings", "Bracket", "Season", "History", "Info"]:
                            item = nav.get_by_text(name, exact=True).bounding_box()
                            assert item and item["x"] >= 0 and item["x"] + item["width"] <= width, item
                        region.focus()
                        page.keyboard.press("ArrowRight")
                        region.evaluate("el => el.scrollLeft = 0")
                        page.get_by_test_id("stMain").evaluate("el => el.scrollTop = 0")
                        page.locator("h1").first.scroll_into_view_if_needed()
                        page.screenshot(path=str(output / f"bracket-{label}.png"), full_page=True)
                        table_region = page.get_by_test_id("stDataFrame")
                        table_region.scroll_into_view_if_needed()
                        assert table_region.count() == 1
                        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                        canvas = table_region.get_by_test_id("data-grid-canvas")
                        canvas.wait_for()
                        if label == "desktop":
                            grid = table_region.locator(".dvn-scroller")
                            bounds = grid.bounding_box()
                            def copied_user(row):
                                grid.click(position={"x": 60, "y": 54 + row * 38})
                                page.keyboard.press("ControlOrMeta+c")
                                page.wait_for_function("() => navigator.clipboard.readText().then(text => text.length > 0)")
                                return page.evaluate("navigator.clipboard.readText()").strip()
                            grid.click(position={"x": 60, "y": 18})
                            assert copied_user(0) == "Christopher", "User column did not sort ascending"
                            grid.click(position={"x": bounds["width"] / 2, "y": 18})
                            assert copied_user(0) == "Former player", "Numeric column did not sort ascending"
                            assert copied_user(1) == "Christopher", "Counts sorted as text instead of numbers"
                            grid.click(position={"x": bounds["width"] / 2, "y": 18})
                            assert copied_user(0) == "Poppi", "Numeric column did not sort descending"
                        page.get_by_role("heading", name="All-time playoff standings", exact=True).scroll_into_view_if_needed()
                        page.screenshot(path=str(output / f"playoff-standings-{label}.png"), full_page=True)
                        page.get_by_role("button", name="Game details and everyone’s picks →").click()
                        page.get_by_role("heading", name="Game details", exact=True).wait_for()
                        page.get_by_role("button", name="← Back to Bracket").click()
                        page.get_by_role("heading", name="Bracket", exact=True).wait_for()
                    if screen in {"Standings", "Season", "Info"}:
                        page.screenshot(path=str(output / f"{screen.lower()}-{label}.png"), full_page=True)
                page.get_by_role("button", name="Everyone’s picks →").first.click()
                page.get_by_role("heading", name="Game details", exact=True).wait_for()
                page.get_by_role("heading", name="Everyone’s picks", exact=True).wait_for()
                page.screenshot(path=str(output / f"game-{label}.png"), full_page=True)
                print(f"Passed {label}: six tabs, playoff bracket and sortable standings, blog archive, external video links, game details, fixed navigation, no page overflow")
                page.close()
            browser.close()
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        temporary.cleanup()


if __name__ == "__main__":
    main()
