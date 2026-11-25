# MBCC for iPhone

A native, read-only SwiftUI app and a matching mobile Streamlit interface.
`app.py` follows the iPhone app’s six screens, cards, game details, standings,
season charts, history, trophy cabinet, and Today’s Update blog. The iPhone
project is in `ios/MBCC.xcodeproj`; fresh installations connect to the deployed
Cloud Run backend by default. Both interfaces provide explicitly labeled demo
data through Data Connection.

## Run the Streamlit app

Use Python 3.11 or newer for a new installation:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Streamlit is pinned to the renderer used for the browser checks. Rerun those
checks when upgrading it because the fixed navigation uses custom CSS.

The responsive layout uses a fixed bottom navigation bar for **Live**, **Standings**,
**Bracket**, **Season**, **History**, and **Info**, plus game and blog detail screens. The newest
post appears at the top of Live; **View all updates** shows the complete published
archive. YouTube thumbnails open external video links. Scores display correct
picks with the spreadsheet’s MBCC score in smaller parentheses; ranking keeps
the MBCC score ordering, including shared ranks. The Info screen includes full
and half championship trophies from the same history rules as the iPhone app.

The sidebar also has a **Current players only** filter, enabled by default.
It applies to every tab and game details, including standings, player choices,
season charts and elimination, historical records, all-time playoff standings,
and the trophy cabinet. Turn it off to include former players. Current status
uses `agg_history.Active`, then `basic_history.Current` when no career record
exists; new players without either record use the current season roster.
History keeps its individual player and winner filters. Season-wide historical
totals retain the spreadsheet's original aggregate calculations.

In the sidebar's **Groups** settings, enter a **Group keyword**:

| Keyword | Results shown |
| --- | --- |
| Blank or `default` | Main group from the existing challenge spreadsheet |
| `sub` | Subgroup from the second challenge spreadsheet |
| `default+sub` | Both rosters together, with a shared standings ranking |

Keywords ignore case and surrounding spaces. An unknown keyword shows an error.
The selection applies to every screen, player filter, game pick, chart, history,
and trophy cabinet. Changing groups clears the previous group's saved results
and player selections. A failed subgroup load never displays main-group data
as the subgroup. The bundled demo contains only the main group.

To add the subgroup spreadsheet:

1. Use the same tab names and column layout as the main workbook, with the
   subgroup's players and statistics. For a combined view, use the same season,
   game schedule and row order, and keep scores and tracker rows synchronized.
2. Share the second workbook with the backend's `mbcc-sheet-reader` service
   account as **Viewer**.
3. Set `MBCC_SUB_CHALLENGE_SHEET_ID` in `cloudrun/env.yaml` (or `backend/.env`
   locally) to the second spreadsheet's ID. Its three history tabs are read
   from that workbook by default. Set `MBCC_SUB_HISTORY_SHEET_ID` only if they
   are in a separate subgroup history workbook.
4. Deploy the updated backend using `bash cloudrun/update-live-source.sh`,
   and publish/reboot the updated Streamlit app. Then select `sub` or
   `default+sub` in the sidebar.

The combined view labels player names `[Main]` and `[Sub]`, including matching
names, so each entry retains its own picks and stats. Games appear once and
combine both rosters' picks. Scores and standings values remain those from each
spreadsheet; both spreadsheets must use comparable scoring formulas. Historical
awards stay with their original group, and season aggregate rows are labeled
by group. The main group's updates supply the combined news feed. Incompatible
seasons, schedules, results, or trackers show a message instead of a partial merge.

The subgroup does not track all-time playoff history and needs no
`playoff_history` / `playoff_picks` worksheet. The API skips that read, and both
apps explain that this history is not tracked rather than showing a load error.
In the combined view, all-time playoff standings show main-group history only,
with a caption identifying that scope. Main-group playoff totals are never
copied into the subgroup. Any old `MBCC_SUB_PLAYOFF_HISTORY_SHEET_ID` setting is
ignored. `MBCC_SUB_UPDATES_ENABLED=1` enables a subgroup
`todays_update` tab; it defaults to off. Optional `MBCC_SUB_SEASON` and
`MBCC_SUB_WORKSHEET_TITLES` override the main backend's season and tab mapping.
`MBCC_GROUP_KEYWORD` or `[mbcc].group_keyword` sets Streamlit's initial selection.
The API defaults to the main group and accepts `?group=sub` or
`?group=default%2Bsub`; group choices are display filters, not access controls.

Open **Data Connection** using the sidebar control at the upper left:

- **iPhone backend** uses the public read-only snapshot API, requiring no Google
  credentials in Streamlit. All live scores, picks, standings, charts, blog posts,
  history, and playoff totals use this API. It is the default even when old Sheets
  credentials exist. This endpoint was checked on November 23, 2026 with real data,
  48 games, and one published blog post; all-time playoff totals still require
  deployment of the updated backend.
- **Demo** loads the same fictional fixture as iPhone. For a local preview only,
  start with `MBCC_DEMO=1 .venv/bin/streamlit run app.py`. Failed live connections
  never silently switch to demo data.

Optional web settings use environment variables `MBCC_DATA_SOURCE` (`api` or
`demo`) and `MBCC_ENDPOINT`, or the matching `[mbcc]` settings shown in
`.streamlit/secrets.toml.example`. Legacy `sheets` settings and saved Google Sheets
selections now use the API. Old `[connections.gsheets]` credentials are ignored
and can be removed from web hosting. The backend owns season, workbook, and
worksheet settings, including `MBCC_SEASON` and `MBCC_WORKSHEET_TITLES`.
There is no hardcoded end-of-season game filter cutoff.

Live data refreshes every minute while the browser session is open.
The last successful snapshot is retained **for that browser session and
connection** if a refresh fails, with a warning. Changing sources clears it.
Unlike the iPhone app’s on-disk cache, the web copy does not persist after a new
session. The web loader and API may each cache data for up to a minute.
Verification freshness is recomputed on every render, including saved results.
Game-day and publication-date selection use Eastern Time; kickoff times use
the browser time zone when available and can be changed in Data Connection.

This emulates the native app’s content and navigation in a browser; system
controls, browser links, and the connection sidebar remain Streamlit controls.
The web app has its own deployment. Deploying the Cloud Run API ZIP does not
deploy `app.py` or its new `web_app` package. On Streamlit hosting, publish the
updated repository files and reinstall `requirements.txt`.

Streamlit checks, including navigation, shared API loading and legacy settings,
archive behavior, connection failures, and model parity:

```sh
.venv/bin/python -m unittest discover -s tests -q
```

Optional browser checks use Playwright (`pip install playwright` and
`python -m playwright install chromium`). Start the local demo preview first,
then run `.venv/bin/python tools/check_streamlit_browser.py`. It uses a temporary,
explicitly fictional API fixture and saves screenshots for 320 px, 390 px, and
1440 px widths in `outputs/streamlit`.

## Run the iPhone app

1. Open `ios/MBCC.xcodeproj` in Xcode.
2. Select the **MBCC** scheme and an iPhone simulator, then Run.
3. For a physical iPhone, select your Apple development team in Signing & Capabilities and choose your device. Minimum supported version: iOS 17.

The live endpoint is [MBCC Cloud Run](https://mbcc-api-jarvycxodq-ue.a.run.app/api/snapshot).
It was verified on October 29, 2026 with `isDemo: false`, 10 players, 48 games,
133 history rows, and 14 seasons. Existing saved connection/demo preferences
remain in effect; the gear button lets you change them.

The updated app requires `live_scores_and_games` for real game data and ignores
cached game lists from the previous source. Deploy the current backend using
`cloudrun/update-live-source.sh`, then build/run this Xcode project. Until that
deployment, the hosted service still returns its previous game list. Freshly
imported games show “Game not verified” and “Scores not verified” until a
successful automatic feed check supplies the comparison data.

The app has Live, Standings, Bracket, Season, History, and Info tabs. On compact iPhone tab bars, History and Info are accessible through More. Tap a game to see everyone’s picks and its ESPN link when an ESPN game ID exists. Season includes player filters, the correct-picks bar chart, both Argyle charts, the elimination check, and a horizontally scrolling elimination matrix. History keeps the player and winner filters, career totals, and season totals. The gear button opens Data Connection, where **Current players only** matches the web sidebar: enabled by default and applied immediately across every tab and game details, including all-time playoff standings. The iPhone app saves this preference between launches and retains the complete snapshot so turning the filter off restores former players and their historical totals. There is no pick submission or sign-in flow.

The **Bracket** tab shows playoff games in four horizontally scrolling rounds:
First round, Quarterfinals, Semifinals, and Championship. Both interfaces reuse
the existing snapshot, scores, verification, refresh, and game-detail screens.
Choose a player to see their picks and final pick results; Results only hides
the picks. Missing opponents remain TBD and missing scores display a dash.
The champion appears only after a completed championship game. With no playoff
games, the tab shows an empty state (including the older bundled demo season).

Games must include `College Football Playoff` or `CFP` and a round name in their
existing game title. Ordinary bowl names are excluded because bowl assignments
change by season. Within each round games are in kickoff order. The current
snapshot does not supply seeds or feeder-game relationships, so the view does
not invent those connections. Displaying the bracket games uses the existing
schedule and does not require a new worksheet.

At the bottom of Bracket, **All-time playoff standings** lists every historical
user, correct playoff games all time, and correct unknown playoff games all
time. The source is the **`playoff_picks`** tab in the separate history workbook
(`1Iwl1WEzLEXu05ZtFcfZovWwQsECNy8LH3II760C-w2E`). Only its first three rows are
read: user names across row 1, and rows labeled `Overall` and `Overall Unknown`
below them. The sheet uses a count/percentage column pair for each user; only
the counts are displayed. Leading spacer columns and names centered across the
pairs are supported, as is the compact one-count-column-per-user layout.
Those totals are used
directly; season rows below them are not added again. All users are included,
independent of the current season or selected pick filter. Rows sort by correct
playoff games, then correct unknown playoff games, then name. Missing totals
remain unavailable, and zero remains zero. The table appears even without a
current bracket. Streamlit uses a native interactive dataframe with two-tier
headers; click a column heading to sort, and use its built-in fullscreen or
resize controls as needed. The iPhone table fits all three columns to the screen
with wrapping headers and names. Tap a heading to sort; tap it again to reverse
the order.

Both apps receive these totals through the shared API. Existing overall history
remains in the challenge workbook. The API reads the separate playoff workbook when
`MBCC_PLAYOFF_HISTORY_ENABLED=1`, using `MBCC_PLAYOFF_HISTORY_SHEET_ID`. Both are
set in the supplied Cloud Run configuration. Use `MBCC_WORKSHEET_TITLES` to override
the `playoff_history` tab alias if needed. The API's `mbcc-sheet-reader` service
account needs Viewer access to the history workbook. A failed playoff-history
read leaves the other app content available
and displays an unavailable message rather than invented standings.

Publish and reboot the web app, deploy the updated backend with
`bash cloudrun/update-live-source.sh`, and rebuild the iPhone app to ship the
table. Older API responses remain readable and display a playoff-history
unavailable state until the backend is updated.

Info includes a trophy cabinet for every current and former player, ordered by championship total. Each winning season earns one trophy, and a shared championship earns half a trophy, including Nicholas and Joseph’s first-season win. Players without championships appear by name without trophies. Totals come from the history records, counting each player’s winning season once.

The Live leader card and Standings show correct picks as the official score, with the spreadsheet’s calculated MBCC score in smaller parentheses beside it. Standings preserve the spreadsheet’s MBCC score ordering and point difference. The elimination check ports the original pairwise best-case logic, including still-possible picks for unresolved bracket slots and ties that remain alive. It is not an exhaustive playoff scenario solver.

## Today’s Update

The **Live** tab starts with a **Today’s Update** card showing the newest post
in full, including its date, headline, message, and optional video thumbnail.
**View all updates** opens a dedicated page with a blog feed: the newest post
at the top, followed by previous posts. Each
post has its own publication date, headline, message, and optional YouTube
thumbnail with a play button. Messages preserve paragraph breaks.
Tapping the thumbnail opens the original link in YouTube or the browser. No
YouTube API key is needed. A failed thumbnail still leaves a working play button.

To publish updates from the existing challenge workbook:

1. Add a worksheet named **`todays_update`** with these headers in row 1:
   `published_date`, `title`, `message`, `youtube_url`.
2. Add an update row. Format `published_date` as **plain text** in `YYYY-MM-DD`
   form (for example, `2026-11-20`), then enter your headline, optional message,
   and the full HTTPS YouTube video link. Regular watch links, `youtu.be` share
   links, Shorts, and live video links are supported. Message and URL cells can
   be blank; a blank title defaults to “Today’s Update”.
3. Set **`MBCC_UPDATES_ENABLED: "1"`** in `cloudrun/env.yaml` and deploy the backend
   using `bash cloudrun/update-live-source.sh`. For local development, set
   `MBCC_UPDATES_ENABLED=1` in `backend/.env` instead. Build/run the updated app.

After that one-time setup, **append a row for each new post** to retain the
earlier posts. No app rebuild or backend redeployment is needed for content
changes. All published posts appear in reverse date order, with their original
dates and thumbnails. Dates use **Eastern Time**; future rows stay hidden until
their date arrives. For multiple posts on the same date, later worksheet rows
appear first and all posts remain visible. Worksheet row order otherwise does
not affect date sorting. Blank or invalid date rows are ignored. Edit an
existing row to revise a post, or delete its row to remove it from the feed.

The blog feed requires the updated backend and app. The app can also read the
earlier single-update response until the new backend is deployed.

Changes appear on a subsequent refresh, normally within about two minutes while
the app is active, allowing for the server cache. With no published update,
the page shows “No update yet”. The supplied Cloud Run configuration now enables
updates because the worksheet has been set up. For another workbook, create
the tab before enabling updates; the local `.env.example` leaves them off. An old backend without
this feature also shows the empty state. Unavailable or invalid video links show
an availability message while retaining the briefing text.

## Connect the challenge spreadsheet

For the hosted setup, follow [the Cloud Run deployment guide](cloudrun/README.md).
Cloud Run can use its assigned service account without copying a private key
from Streamlit. The instructions below are for local development.

The supplied files are:

- **Challenge:** `1jKYvXmWIB39FPGsEIGatP_KTY_VK53TnDxNSBVokfVs`
- **Separate history file:** `1Iwl1WEzLEXu05ZtFcfZovWwQsECNy8LH3II760C-w2E`

The owner confirmed that **all worksheets read by Streamlit are in the challenge
file**, including `basic_history`, `agg_history`, and `season_history`. Both
spreadsheet variables in `backend/.env.example` and `cloudrun/env.yaml` therefore
point to the challenge file. The separate history file is now queried only for
`playoff_picks`; the three existing overall history tabs stay in the challenge
file.

The backend reads the private challenge file using the dedicated runtime service
account. The owner granted it Viewer access. All nine required tab names were
confirmed by the owner, and the live snapshot was successfully loaded after
correcting workbook routing and the kickoff date/time format.

The server reads the files through the Google Sheets API with a read-only scope. Credentials remain on the server and never go into the iPhone app.

1. Enable the Google Sheets API in your Google Cloud project.
2. Use the existing Streamlit service account if appropriate, or a dedicated service account. Give that account **Viewer** access to the challenge spreadsheet. Configure its credentials locally using Application Default Credentials; do not paste a private key into chat or commit it.
3. Create a virtual environment and install the backend dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

4. Edit `backend/.env` to set `GOOGLE_APPLICATION_CREDENTIALS` to your local credential file. The example routes all required tabs to the challenge workbook. Then load the environment and run the local server:

```sh
set -a
source backend/.env
set +a
.venv/bin/python -m backend.server
```

5. In the simulator, open **Data Connection** using the gear button, turn off **Explore demo data**, and enter `http://localhost:8000/api/snapshot`. Local HTTP is accepted only in Debug builds. A physical iPhone or Release build should use an HTTPS backend URL.

You can test the HTTP bridge without any Google credentials using:

```sh
python3 -m backend.server --demo
```

This endpoint also marks its payload as demo data, so connecting to it cannot make fictional results look real.

For hosted use, run the WSGI app behind HTTPS, for example `gunicorn backend.server:application`. The built-in local server binds only to localhost and is for development. The owner deployed the backend to Cloud Run with a public, read-only endpoint and no player sign-in. A private deployment would need a deliberate authentication design; a shared secret embedded in an app is not sufficient.

## Worksheet mapping

For live scores and automatic checked/unchecked comparison against human-entered
scores (including ongoing games), see [score updater instructions](sheets/README.md).
Manually upload the supplied `live_scores_and_games` tab into the existing
spreadsheet. The updater starts checking on December 5, 2026, and leaves
`scores` and `unlive_games` unchanged. Once enabled, the combined tab supplies
every game detail, score and winner in the iPhone app. Two checkboxes verify each
game: kickoff and both opponents against `unlive_games`, and both scores plus
`point_difference` against `scores`. Upset, unanimous and team-focus indicators display
their formula results without verification; the updater preserves those formulas.
Standings, progress and history keep their existing
summary sources. The backend now enables the combined tab by default. The updater
contains no spreadsheet creation or schedule import functions. ESPN's HTTP 403
issue still requires resolution before automatic score updates can succeed.
Upcoming games' kickoff times and opponents are checked every two hours from
December 5 until each schedule is set. That game's pregame checks then stop.
ESPN score polling runs every five minutes for that day's games, with ongoing games
carrying over past midnight. Finals stop polling when both verification checks
pass, retain verification without an expiry countdown, and reopen for checking
if a later reference edit creates a mismatch.

| File | Worksheet | Data used |
| --- | --- | --- |
| Challenge | `current_pick_success` | `Situation`, one column per player; `Correct`, `mbcc_score`, `point_difference` rows |
| Challenge | `unlive_games` | `game_name`, `game_date`, `game_time`, `game_home_team`, `game_away_team`, optional `game_id`, `game_venue`, `game_network` |
| Challenge | `scores` | `game`, `home_team_score`, `away_team_score`, `winner`, optional upset/unanimous/focus indicators |
| Challenge | `live_scores_and_games` | Primary game list/details/scores/winner and calculated `point_difference`, with game and score verification against the original two tabs |
| Challenge | `picks` | `Game`, one column per player |
| Challenge | `live_tracker_binary` | `gametracker`, one column per player; initial zero baseline then cumulative correct picks |
| Challenge | `live_tracker_complex` | Same rows/flags, cumulative point difference |
| Challenge | `basic_history` | `MBCC`, `Player`, `Picks`, `Games`, `PercentageCorrect`, `Winner`, `Current` |
| Challenge | `agg_history` | `Player`, `LiveWins`, `LiveLosses`, `LivePercentage`, `Active` |
| Challenge | `season_history` | `Season`, `TotalWins`, `TotalLosses`, `Percentage` |

In live mode, games join reference schedules by ESPN ID, then use the reference
game name to find human scores and picks. New games remain visible without
reference entries or picks, with unchecked verification. Game and score groups
are independent; blank live values never fall back to originals. Without live
mode, the earlier name-based mapping remains available during setup. Malformed
calculated summary numbers still produce errors instead of inventing standings.
Sheet dates/times are Eastern, and the app displays kickoff in device-local time.

The server caches one snapshot for 60 seconds. The iPhone app refreshes on launch, foregrounding, pull-to-refresh, and every minute while active. A failed refresh retains the last successful snapshot for the same endpoint, with a warning; switching sources clears the displayed data. There is no automatic fallback to demo data.

The rules, prize amounts, and winner photo are carried over from the original **2025–26** app. Update these before a new season, along with `MBCC_SEASON` and the source worksheet data. Demo games intentionally have no ESPN IDs, since they are fictional.

## Validation

Backend adapter/API tests (no Google access required):

```sh
python3 -m unittest discover -s tests -v
```

Swift model checks (macOS with Xcode):

```sh
swiftc ios/MBCC/Models.swift tests/ModelChecks.swift -o /tmp/mbcc-model-checks
/tmp/mbcc-model-checks ios/MBCC/demo.json
```

Xcode simulator build:

```sh
xcodebuild -project ios/MBCC.xcodeproj -scheme MBCC \
  -configuration Debug -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/MBCCDerivedData CODE_SIGNING_ALLOWED=NO build
```

Run the **MBCCUITests** target using Product → Test to check navigation, game picks, standings, history, charts/elimination, URL validation, failed connections, and the deployed backend. The Debug-only `--ui-testing` launch argument resets the test app’s source preferences and uses demo data for repeatable UI checks; adding `--live-data` tests the real backend.

The app icon uses diagonal MBCC lettering and the app’s `trophy.fill` SF Symbol. Regenerate its 1024-pixel asset from the repository root with `swift tools/generate_app_icon.swift`.

This is a working first version for review, not an App Store release. Remaining release work includes Apple signing, testing on a physical device, and TestFlight/App Store preparation.
