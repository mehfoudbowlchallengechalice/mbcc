"""MBCC's Streamlit interface, matching the native iPhone app's screens.

Run: streamlit run app.py
Data: existing gsheets connection or the same read-only snapshot API as iPhone.
"""
import html
import os
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import altair as alt
import pandas as pd
import streamlit as st

from backend.sheets_adapter import WORKSHEETS, build_snapshot
from web_app import data

ROOT = Path(__file__).resolve().parent
PAGES = ["Live", "Standings", "Bracket", "Season", "History", "Info"]
COLORS = ["#387bc4", "#bb612d", "#248363", "#8764ae", "#c2527a", "#248b96", "#5b68af", "#8a674b", "#c34b46", "#4d94ae"]
TROPHY = '<svg viewBox="0 0 24 28" aria-hidden="true"><path d="M6 2h12v8c0 5-2.5 8-6 8s-6-3-6-8V2Zm0 2H2v5c0 4 2 6 6 6M18 4h4v5c0 4-2 6-6 6M12 18v6M7 26h10" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>'


def esc(value):
    return html.escape(str(value), quote=True)


def setting(name, default=None):
    if name.upper() in os.environ:
        return os.environ[name.upper()]
    try:
        return st.secrets.get("mbcc", {}).get(name.removeprefix("mbcc_"), default)
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return default


def has_sheets_connection():
    try:
        return "gsheets" in st.secrets.get("connections", {})
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return False


@st.cache_data(ttl=60, show_spinner=False)
def fetch_snapshot(source, endpoint, season):
    if source == "Demo":
        return data.read_demo()
    if source == "iPhone backend":
        return data.fetch_api(endpoint)
    from streamlit_gsheets import GSheetsConnection
    connection = st.connection("gsheets", type=GSheetsConnection)
    titles = setting("mbcc_worksheet_titles", {})
    if not isinstance(titles, dict):
        titles = dict(titles)
    tables = {}
    for name in WORKSHEETS + ("live_scores_and_games", "todays_update"):
        frame = connection.read(worksheet=titles.get(name, name), ttl=60)
        frame = frame.astype(object).where(pd.notna(frame), None)
        tables[name] = [list(frame.columns)] + frame.values.tolist()
    return data.validate_snapshot(build_snapshot(tables, season=season))


def change_page():
    st.session_state.pop("detail", None)


def open_detail(kind, identifier=None):
    st.session_state.detail = (kind, identifier)


def settings():
    default = setting("mbcc_data_source", "sheets" if has_sheets_connection() else "api")
    if os.environ.get("MBCC_DEMO") == "1":
        default = "demo"
    sources = ["iPhone backend", "Google Sheets", "Demo"]
    defaults = {"api": 0, "sheets": 1, "demo": 2}
    with st.sidebar:
        st.header("Data Connection")
        source = st.radio("Data source", sources, index=defaults.get(default, 0), key="data_source")
        endpoint = setting("mbcc_endpoint", data.DEFAULT_ENDPOINT)
        season = setting("mbcc_season", "MBCC 15 · 2026–27")
        if source == "iPhone backend":
            endpoint = st.text_input("Snapshot URL", value=endpoint, key="snapshot_url")
            st.caption("Uses the same results and posts as the iPhone app.")
        elif source == "Google Sheets":
            season = st.text_input("Season", value=season, key="sheet_season")
            st.caption("Uses your existing Google Sheets connection. The live_scores_and_games and todays_update tabs are required.")
        else:
            st.caption("Fictional sample results. Demo data is never used automatically when a live connection fails.")
        st.divider()
        try:
            browser_zone = getattr(st.context, "timezone", None) or "America/New_York"
            ZoneInfo(browser_zone)
        except (AttributeError, ZoneInfoNotFoundError):
            browser_zone = "America/New_York"
        zones = list(dict.fromkeys([browser_zone, "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "UTC"]))
        zone = st.selectbox("Kickoff time zone", zones, key="time_zone")
        st.caption("Game days and post publication dates always use Eastern Time.")
        if st.button("Refresh now", width="stretch"):
            fetch_snapshot.clear()
        st.caption("Results refresh every minute while this page is open.")
    return source, endpoint.strip(), season, zone


def load_data(source, endpoint, season):
    identity = (source, endpoint if source == "iPhone backend" else season if source == "Google Sheets" else "demo")
    if st.session_state.get("source_identity") != identity:
        st.session_state.source_identity = identity
        st.session_state.pop("last_snapshot", None)
        st.session_state.pop("detail", None)
        for key in ("game_filter", "season_players", "game_players", "elimination_player", "history_player", "bracket_player", "bracket_saved_player", "bracket_game"):
            st.session_state.pop(key, None)
    try:
        snapshot = fetch_snapshot(source, endpoint, season)
        st.session_state.last_snapshot = snapshot
        return snapshot, None
    except Exception as error:
        message = str(error) if isinstance(error, data.SnapshotError) else "Couldn’t refresh MBCC. Check Data Connection and try again."
        saved = st.session_state.get("last_snapshot")
        if saved:
            message += " Showing the last saved results for this connection."
        return saved, message


def date_label(value):
    try:
        return date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")
    except (ValueError, TypeError):
        return value or ""


def card(key):
    return st.container(border=False, key="mbcc_card_" + key)


def avatar(player):
    return f'<span class="avatar" aria-hidden="true">{esc(player[:1])}</span>'


def post(update, latest=False):
    if latest:
        st.markdown('<p class="eyebrow">LATEST UPDATE</p>', unsafe_allow_html=True)
    st.caption(date_label(update.get("publishedDate")))
    st.subheader(update.get("title") or "Today’s Update")
    if update.get("message"):
        message = esc(update["message"]).replace("\n", "<br>")
        st.markdown(f'<div class="post-copy">{message}</div>', unsafe_allow_html=True)
    video = data.youtube_video(update.get("youtubeURL"))
    if video:
        label = esc(f'Watch {update.get("title", "the update")} on YouTube')
        st.markdown(f'''<a class="video-card" href="{esc(video['url'])}" target="_blank" rel="noopener noreferrer" aria-label="{label}">
<div class="video-picture"><img src="{esc(video['thumbnail'])}" alt="YouTube video thumbnail" loading="lazy"><span class="play" aria-hidden="true">▶</span></div>
<div class="video-footer"><span>Watch on YouTube</span><span aria-hidden="true">↗</span></div></a>''', unsafe_allow_html=True)
        st.caption("Opens in YouTube or your browser.")
    elif update.get("youtubeURL"):
        st.caption("The video is unavailable right now. Check back soon.")


def updates_view(snapshot):
    if st.button("← Back to Live", key="back_updates"):
        st.session_state.pop("detail", None)
        st.rerun()
    st.title("Today’s Update")
    posts = data.update_posts(snapshot)
    if not posts:
        st.info("No update yet. Check back for the latest MBCC news and videos.")
    for index, update in enumerate(posts):
        if index == 1:
            st.subheader("Previous updates")
        with card(f"post_{index}"):
            post(update, latest=index == 0)


def verification_badge(game, for_game=False):
    status = data.verification(game, for_game)
    symbol = "☑" if status == "verified" else "□"
    return f'<span class="verification {esc(status)}">{symbol} {esc(data.verification_label(status, for_game))}</span>'


def game_card(game, zone):
    status = (game.get("live") or {}).get("status", "final" if data.is_final(game) else "scheduled").upper()
    lines = [f'<div class="game-heading"><strong>{esc(game["name"])}</strong><span class="game-status">{esc(status)}</span></div>']
    for side in ("away", "home"):
        team = game[f"{side}Team"]
        winner = game.get("winner") == team
        focus = team == game.get("focusTeam") and game.get("upset") is True
        lines.append(f'<div class="team-row {"team-focus" if focus else ""}"><span class="team-name">{esc(team)}{" <span aria-label=Winner>🏆</span>" if winner else ""}</span><strong>{esc(data.score(game.get(side + "Score")))}</strong></div>')
    if game.get("pointDifference") is not None:
        lines.append(f'<p class="small muted">Score difference: {esc(data.score(game["pointDifference"]))}</p>')
    lines.append(verification_badge(game))
    lines.append(f'<p class="game-meta"><span>{esc(data.kickoff_label(game, zone))}</span><span>{esc(game.get("network", ""))}</span></p>')
    lines.append(verification_badge(game, for_game=True))
    flags = []
    if game.get("upset") is True:
        flags.append("⚡ Upset pick game")
    if game.get("unanimous") is True:
        flags.append("Unanimous pick")
    if game.get("focusTeam"):
        flags.append("Focus: " + game["focusTeam"])
    if flags:
        lines.append('<p class="small muted">' + ' · '.join(esc(flag) for flag in flags) + '</p>')
    st.markdown(''.join(lines), unsafe_allow_html=True)
    fetched = data.parse_time((game.get("live") or {}).get("updatedAt"))
    if fetched:
        st.caption(f'{(game.get("live") or {}).get("source", "Live")} updated {fetched.astimezone(ZoneInfo(zone)).strftime("%b %d, %I:%M %p %Z")}')


def player_filter(snapshot, key):
    players = snapshot["players"]
    if key in st.session_state:
        st.session_state[key] = [name for name in st.session_state[key] if name in players]
    return st.multiselect("Players", players, default=players, key=key)


def game_view(snapshot, identifier, zone):
    origin = st.session_state.get("primary_nav_value", "Live")
    if st.button(f"← Back to {origin}", key="back_game"):
        st.session_state.pop("detail", None)
        st.rerun()
    st.title("Game details")
    game = next((item for item in snapshot["games"] if item["id"] == identifier), None)
    if game is None:
        st.info("This game is no longer in the current schedule.")
        return
    with card("game_detail"):
        game_card(game, zone)
    checks = game.get("fieldVerification")
    if checks:
        with st.expander("Compare with original entries", expanded=True):
            st.caption("Game verification checks kickoff and both opponents. Score verification checks both scores and their absolute difference.")
            for key, label in data.CHECKED_FIELDS:
                check = checks.get(key)
                if not check:
                    continue
                st.markdown(f'**{label}**')
                st.text(f'Live: {check["value"]}\n{check["source"]}: {check["originalValue"]}')
                if data.field_status(check) != "verified":
                    st.caption("Not verified: invalid, unavailable or outdated data." if data.field_status(check) == "unavailable" else check["reason"])
    if game.get("venue"):
        st.caption(game["venue"])
    espn_id = str(game.get("espnID") or "")
    if espn_id and espn_id.isascii() and espn_id.isdigit():
        st.link_button("Open ESPN Gamecast ↗", f"https://www.espn.com/college-football/game?gameId={espn_id}")
    st.subheader("Everyone’s picks")
    selected = player_filter(snapshot, "game_players")
    if not selected:
        st.info("Choose players to see their picks.")
    with card("game_picks"):
        for player in selected:
            pick = game.get("picks", {}).get(player)
            result = ""
            if data.is_final(game) and pick:
                correct = pick == game["winner"]
                result = f'<span class="pick-result {"correct" if correct else "incorrect"}">{"✓ Correct" if correct else "✕ Incorrect"}</span>'
            st.markdown(f'<div class="list-row">{avatar(player)}<strong>{esc(player)}</strong><div class="row-value">{esc(pick or "No pick")}{result}</div></div>', unsafe_allow_html=True)


def live_view(snapshot, zone):
    posts = data.update_posts(snapshot)
    with card("latest_update"):
        st.markdown('<p class="eyebrow">◖ TODAY’S UPDATE</p>', unsafe_allow_html=True)
        if posts:
            post(posts[0], latest=True)
        else:
            st.subheader("No update yet")
            st.write("Check back here for the latest MBCC news and videos.")
        st.button("View all updates →", key="all_updates", on_click=open_detail, args=("updates",), width="stretch")
    completed = sum(data.is_final(game) for game in snapshot["games"])
    total = len(snapshot["games"])
    progress = 100 * completed / max(total, 1)
    st.markdown(f'''<section class="season-hero"><div class="hero-top"><span>BOWL SEASON</span>{TROPHY}</div>
<h2>{esc(snapshot['season'])}</h2><p>Every game. Every pick. One chalice.</p>
<div class="season-totals"><span><strong>{completed}</strong> games in</span><span>{total - completed} to go</span></div>
<div class="season-progress" role="progressbar" aria-label="Season completion" aria-valuenow="{completed}" aria-valuemin="0" aria-valuemax="{max(total, 1)}"><span style="width:{progress}%"></span></div></section>''', unsafe_allow_html=True)
    standings = data.ranked(snapshot)
    if standings:
        leader = standings[0]
        with card("leader"):
            st.markdown(f'<div class="list-row">{avatar(leader["player"])}<div><p class="eyebrow">SETTING THE PACE</p><strong>{esc(leader["player"])}</strong></div><div class="row-value"><strong class="large-score">{leader["correct"]}</strong> <span class="muted">({esc(data.score(leader["overallScore"]))})</span><small>correct picks</small></div></div>', unsafe_allow_html=True)
    st.subheader("The games")
    st.caption("Scores and everyone’s picks, in one place.")
    if "game_filter" not in st.session_state:
        st.session_state.game_filter = "Today" if data.filtered_games(snapshot["games"], "Today") else "All"
    mode = st.radio("Show games", ["Today", "Future", "All"], horizontal=True, key="game_filter", label_visibility="collapsed")
    if mode == "Today":
        st.caption("Today shows the next game day when there are no games today.")
    st.caption(f"Game days use Eastern Time. Kickoff times use {zone.replace('_', ' ')}.")
    games = data.filtered_games(snapshot["games"], mode)
    if not games:
        st.info("No upcoming games. Switch to All to see this season’s results and picks.")
    for game in games:
        with card(f'game_{game["id"]}'):
            game_card(game, zone)
            st.button("Everyone’s picks →", key=f'game_{game["id"]}', on_click=open_detail, args=("game", game["id"]), width="stretch")


def bracket_view(snapshot, zone):
    st.subheader("The road to the championship")
    st.caption(snapshot["season"])
    rounds = data.playoff_games(snapshot)
    games = [game for _, entries in rounds for game in entries]
    if not games:
        st.info("The playoff bracket isn’t available yet. Games will appear here when the schedule includes playoff rounds.")
        return
    players = snapshot["players"]
    if "bracket_player" not in st.session_state:
        st.session_state.bracket_player = st.session_state.get("bracket_saved_player", "")
    if st.session_state.get("bracket_player") not in [""] + players:
        st.session_state.pop("bracket_player", None)
    player = st.selectbox("Show picks for", [""] + players, format_func=lambda value: value or "Results only", key="bracket_player")
    st.session_state.bracket_saved_player = player
    completed = sum(data.is_final(game) for game in games)
    st.caption(f"{completed} of {len(games)} playoff games complete · Swipe or scroll sideways to see every round.")
    # The source has rounds, but no seed or feeder-game relationships. Keep
    # games in kickoff order; do not draw invented game-to-game connections.
    columns = []
    for index, (title, entries) in enumerate(rounds):
        cards = []
        for game in entries:
            status = (game.get("live") or {}).get("status", "final" if data.is_final(game) else "scheduled").upper()
            lines = [f'<article class="bracket-game"><p class="eyebrow">{esc(status)}</p><h3>{esc(game["name"])}</h3>']
            for side in ("away", "home"):
                team = game[side + "Team"]
                won = data.is_final(game) and team == game.get("winner")
                lines.append(f'<div class="bracket-team {"bracket-winner" if won else ""}"><span>{esc(team)}{" <span aria-label=Winner>✓</span>" if won else ""}</span><strong>{esc(data.score(game.get(side + "Score")))}</strong></div>')
            lines.append(f'<p class="small muted">{esc(data.kickoff_label(game, zone))}</p>')
            lines.append(verification_badge(game))
            if player:
                pick = game.get("picks", {}).get(player)
                result, style = "", ""
                if pick and data.is_final(game):
                    correct = pick == game["winner"]
                    result, style = (" · ✓ Correct", "correct") if correct else (" · ✕ Incorrect", "incorrect")
                lines.append(f'<p class="bracket-pick {style}">Pick: <strong>{esc(pick or "No pick")}</strong>{result}</p>')
            lines.append('</article>')
            cards.append(''.join(lines))
        if not entries:
            cards.append('<div class="bracket-game muted">Awaiting the schedule</div>')
        columns.append(f'<section class="bracket-round"><div class="bracket-round-heading" role="heading" aria-level="2"><p class="eyebrow">ROUND {index + 1}</p><p class="bracket-round-title">{esc(title)}</p></div><div class="bracket-matchups">{"".join(cards)}</div></section>')
    st.markdown(f'<div class="bracket-scroll" role="region" aria-label="Playoff bracket by round" tabindex="0"><div class="playoff-bracket">{"".join(columns)}</div></div>', unsafe_allow_html=True)
    st.caption("Matchups update with the published schedule. Games are shown in kickoff order within each round.")
    final = rounds[-1][1]
    if len(final) == 1 and data.is_final(final[0]):
        st.success(f'🏆 National champion: {final[0]["winner"]}')
    st.subheader("Explore a game")
    by_id = {game["id"]: game for game in games}
    if st.session_state.get("bracket_game") not in by_id:
        st.session_state.pop("bracket_game", None)
    identifier = st.selectbox("Playoff game", list(by_id), format_func=lambda value: by_id[value]["name"], key="bracket_game")
    st.button("Game details and everyone’s picks →", key="bracket_details", on_click=open_detail, args=("game", identifier), width="stretch")


def standings_view(snapshot):
    st.subheader("The race for the chalice")
    completed = sum(data.is_final(game) for game in snapshot["games"])
    st.caption(f'{len(snapshot["players"])} players · {completed} of {len(snapshot["games"])} games complete')
    margin = st.radio("Leaderboard", ["Correct picks", "Point difference"], horizontal=True, key="standings_metric", label_visibility="collapsed") == "Point difference"
    standings = data.ranked(snapshot, margin)
    with card("standings"):
        for entry in standings:
            rank = data.rank_number(standings, entry, margin)
            if margin:
                value = esc(data.score(entry["pointDifference"]))
                subtitle = f'{entry["correct"]} correct picks'
            else:
                value = f'{entry["correct"]} <span class="secondary-score">({esc(data.score(entry["overallScore"]))})</span>'
                subtitle = "Correct picks"
            st.markdown(f'<div class="list-row"><span class="rank {"leading" if rank == 1 else ""}">{rank}</span>{avatar(entry["player"])}<div><strong>{esc(entry["player"])}</strong><small>{subtitle}</small></div><div class="row-value large-score">{value}</div></div>', unsafe_allow_html=True)
    st.caption("Points gained in wins, minus points lost in losses, for each player’s picks." if margin else "Correct picks are the official score. The smaller value in parentheses is the MBCC score from the spreadsheet.")


def chart_theme(chart):
    return chart.configure_view(strokeWidth=0).configure_axis(gridColor="#e5e3df", labelColor="#6b7280", titleColor="#6b7280").configure_legend(orient="bottom", title=None)


def season_view(snapshot):
    st.subheader("How the season unfolds")
    selected = player_filter(snapshot, "season_players")
    color = alt.Color("player:N", scale=alt.Scale(domain=snapshot["players"], range=COLORS), legend=alt.Legend(title=None))
    with card("correct_chart"):
        st.subheader("Correct picks")
        rows = [row for row in snapshot["standings"] if row["player"] in selected]
        if rows:
            chart = alt.Chart(pd.DataFrame(rows)).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X("player:N", title=None, sort=selected), y=alt.Y("correct:Q", title="Correct picks", axis=alt.Axis(tickMinStep=1)),
                color=color, tooltip=[alt.Tooltip("player:N", title="Player"), alt.Tooltip("correct:Q", title="Correct picks")]).properties(height=240)
            st.altair_chart(chart_theme(chart), use_container_width=True)
        else:
            st.info("Choose players to see the charts.")
    metric = st.radio("Progress metric", ["Correct picks", "Point chaos"], horizontal=True, key="progress_metric")
    field = "pointDifference" if metric == "Point chaos" else "correct"
    with card("progress_chart"):
        st.subheader("Point Chaos Argyle" if field == "pointDifference" else "Argyle chart")
        st.caption("Progress after each completed game")
        points = [{"player": player, "game": point["gameIndex"], "value": point[field][player]}
                  for point in snapshot["progress"] for player in selected if player in point[field]]
        if points:
            chart = alt.Chart(pd.DataFrame(points)).mark_line(point=True).encode(
                x=alt.X("game:Q", title="Games completed", axis=alt.Axis(tickMinStep=1)),
                y=alt.Y("value:Q", title=metric), color=color,
                tooltip=[alt.Tooltip("player:N", title="Player"), alt.Tooltip("game:Q", title="Game"), alt.Tooltip("value:Q", title=metric)]).properties(height=280)
            st.altair_chart(chart_theme(chart), use_container_width=True)
        else:
            st.info("Choose players to see the charts." if not selected else "Charts appear after the first result.")
    st.subheader("Elimination check")
    st.caption("Who can still reach the top?")
    with card("elimination"):
        player = st.selectbox("Player", snapshot["players"], key="elimination_player")
        result = data.elimination(snapshot, player)
        (st.warning if result["eliminated"] else st.success)("Eliminated" if result["eliminated"] else "Not yet eliminated")
        st.write(f'{result["best"]} correct picks in {player}’s best case')
        for comparison in result["comparisons"]:
            st.markdown(f'<div class="comparison-row"><span>{esc(comparison["player"])}</span><strong>{comparison["correct"]}</strong></div>', unsafe_allow_html=True)
        st.caption("Assumes this player wins every remaining possible pick, then compares the shared picks others would also win. Ties remain alive. Like the iPhone app, this check does not solve every possible playoff bracket.")
    with st.expander("Full elimination matrix"):
        matrix = {name: {row["player"]: row["correct"] for row in data.elimination(snapshot, name)["comparisons"]} for name in snapshot["players"]}
        st.dataframe(pd.DataFrame.from_dict(matrix, orient="index").rename_axis("Best case for ↓"), width="stretch")


def history_view(snapshot):
    st.subheader("A tradition worth keeping")
    st.caption("Mehfoud Bowl Challenge Chalice")
    with card("history_filters"):
        player = st.selectbox("Player", ["All Players"] + sorted({row["player"] for row in snapshot["history"]}), key="history_player")
        former = st.toggle("Include former players", key="history_former")
        more = st.toggle("Show more than winners", key="history_more")
    st.subheader("Player season breakdown")
    entries = [row for row in snapshot["history"] if (former or row["current"]) and (more or data.is_winner(row)) and (player == "All Players" or row["player"] == player)]
    if not entries:
        st.info("No matching results. Try including former players or more than winners.")
    for index, row in enumerate(sorted(entries, key=lambda row: row["season"], reverse=True)):
        with card(f"history_{index}"):
            st.markdown(f'<div class="comparison-row"><span class="eyebrow">{esc(row["season"])}</span><span class="small muted">{esc(row["award"])}</span></div><div class="list-row"><strong>{esc(row["player"])}</strong><strong class="row-value">{row["percentage"]:.1%}</strong></div><p class="small muted">{row["correct"]} correct of {row["games"]} picks</p>', unsafe_allow_html=True)
    st.subheader("Player career breakdown")
    with card("careers"):
        for row in snapshot["careers"]:
            if (former or row["active"]) and (player == "All Players" or row["player"] == player):
                st.markdown(f'<div class="list-row"><strong>{esc(row["player"])}</strong><div class="row-value"><strong>{row["percentage"]:.1%}</strong><small>{row["wins"]} W · {row["losses"]} L</small></div></div>', unsafe_allow_html=True)
    st.subheader("MBCC season breakdown")
    with card("seasons"):
        for row in sorted(snapshot["seasons"], key=lambda row: row["season"], reverse=True):
            st.markdown(f'<div class="list-row"><div><strong>{esc(row["season"])}</strong><small>{row["wins"]} W · {row["losses"]} L</small></div><strong class="row-value">{row["percentage"]:.1%}</strong></div>', unsafe_allow_html=True)


def info_view(snapshot):
    with card("info_intro"):
        st.markdown(f'<div class="info-trophy">{TROPHY}</div>', unsafe_allow_html=True)
        st.subheader("One chalice. All the bragging rights.")
        st.write("Pick the most games correctly to win. Root for your teams to win big—or lose by as little as possible—to build your point difference.")
    st.subheader("Tiebreakers")
    st.caption("In order, to decide first versus second")
    rules = ["Point spread", "Correct upset picks", "Correct playoff bracket picks", "Potential upset picks attempted", "Point spread of correct upset picks", "Point spread of playoff bracket picks", "Point spread of all attempted upset picks", "MBCC commemorative coin flip"]
    with card("tiebreakers"):
        for index, rule in enumerate(rules, 1):
            st.markdown(f'<div class="rule-row"><strong>{index}</strong><span>{rule}</span></div>', unsafe_allow_html=True)
    st.subheader("The winnings")
    st.caption("Rules carried over from the 2025–26 app")
    with card("winnings"):
        for title, amount, detail in [("First place", "$300", "Most correct picks, tiebreakers if needed, and a name on the trophy."), ("Second place", "~$150", "Best point difference; prize is whatever is in the change jar."), ("Hokie Prize", "$300", "Split between those who beat Papa Smurf’s number of wins.")]:
            st.markdown(f'<div class="comparison-row"><strong>{title}</strong><strong class="prize">{amount}</strong></div>', unsafe_allow_html=True)
            st.write(detail)
    with card("trophies"):
        st.subheader("The trophy cabinet")
        st.caption("Every player, past and present")
        for record in data.championships(snapshot):
            trophies = TROPHY * record["fullWins"] + ''.join(f'<span class="half-trophy">{TROPHY}</span>' for _ in range(record["sharedWins"]))
            description = f'{record["fullWins"]} outright championships, {record["sharedWins"]} shared championships'
            st.markdown(f'<div class="list-row"><strong>{esc(record["player"])}</strong><span class="trophy-row row-value" role="img" aria-label="{esc(description)}">{trophies}</span></div>', unsafe_allow_html=True)
        st.caption("Half trophies mark shared championships. Nicholas and Joseph shared the first MBCC.")
    with card("about_data"):
        st.subheader("About the data")
        st.write("You’re exploring fictional sample results." if snapshot.get("isDemo") is True else "The app refreshes every minute while open. Games, scores, and verification use the same snapshot contract as the iPhone app. Standings and history retain their spreadsheet calculations.")
        st.caption("Game days and post publication dates use Eastern Time. Choose your kickoff time zone in Data Connection.")


@st.fragment(run_every=60)
def current_screen(source, endpoint, season, zone):
    snapshot, error = load_data(source, endpoint, season)
    page = st.session_state.get("primary_nav_value", "Live")
    detail = st.session_state.get("detail")
    if not detail:
        st.title("MBCC" if page == "Live" else page)
    if error:
        st.warning(error)
    if snapshot is None:
        st.subheader("Connect to MBCC")
        st.write("Open Data Connection in the sidebar to configure results or explicitly choose Demo.")
        return
    if snapshot.get("isDemo") is True:
        st.info("DEMO · Sample results, not real standings")
    if detail and detail[0] == "updates":
        updates_view(snapshot)
    elif detail and detail[0] == "game":
        game_view(snapshot, detail[1], zone)
    elif page == "Live":
        live_view(snapshot, zone)
    elif page == "Standings":
        standings_view(snapshot)
    elif page == "Bracket":
        bracket_view(snapshot, zone)
    elif page == "Season":
        season_view(snapshot)
    elif page == "History":
        history_view(snapshot)
    else:
        info_view(snapshot)
    updated = data.parse_time(snapshot["updatedAt"])
    st.caption(f'Updated {updated.astimezone(ZoneInfo(zone)).strftime("%b %d, %Y · %I:%M %p %Z")}')


def main():
    st.set_page_config(page_title="MBCC", page_icon="🏆", layout="centered", initial_sidebar_state="collapsed")
    st.markdown('<style>' + (ROOT / "web_app/styles.css").read_text() + '</style>', unsafe_allow_html=True)
    source, endpoint, season, zone = settings()
    with st.container(key="primary_nav"):
        st.radio("Main navigation", PAGES, horizontal=True, key="primary_nav_value", label_visibility="collapsed", on_change=change_page, width="stretch")
    current_screen(source, endpoint, season, zone)


if __name__ == "__main__":
    main()
