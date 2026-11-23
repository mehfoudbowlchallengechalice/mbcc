# MBCC Streamlit and iPhone follow up

Saved Page: https://chatgpt.com/space/page_9ba1d1d21fb4819182efefce0a86cf65

November 23 connection update: all live web data now goes through the iPhone
backend. The direct Google Sheets option and web Sheets dependency have been
removed. Existing `sheets` settings and saved selections migrate to the API;
old web Google credentials are ignored. Season and worksheet settings belong on
the backend. Demo remains an explicit local preview option. A live API check
returned 48 games, one blog post, and overall history, but no `playoffStandings`.
Deploy the updated backend/configuration for those totals, and publish/reboot the
web app for the shared connection change. Earlier validation notes below describe
the previous two-source implementation.

Connection validation: all 85 Python checks passed, including API-backed screens,
legacy settings and saved-selection migration, and refresh-failure behavior.
The real hosted snapshot also passed the web loader's validation. Deployment was
not performed; the local Google Cloud CLI is unavailable.

Updated November 23, 2026 with a Bracket tab in both interfaces. It shows the existing schedule’s playoff games in four rounds, with scores, winners, player picks, and game details. An all-time playoff standings table now appears below it, using only the first three rows of `playoff_picks` in the separate history workbook: users, `Overall`, and `Overall Unknown`. The snapshot includes optional `playoffStandings`; old backends remain readable. Existing overall history stays in the challenge workbook. Publish/reboot the web app, deploy the updated API/configuration, and rebuild the iPhone app to ship this change. On compact iPhone tab bars, History and Info are under More.

Validation: 78 Python checks and Swift model checks passed; the iPhone simulator build passed. Browser checks cover all six tabs, bracket navigation, and the all-time table at 320, 390, and 1440 pixels. Live private-sheet access could not be verified in this session; source mapping is tested with the user-confirmed three-row layout. Native UI tests remain blocked by the unavailable iOS 27.0 Simulator runtime. New screenshots are in `outputs/playoff-history`.

`app.py` follows the current iPhone app’s navigation, cards, blog feed, game details, scores, charts, elimination, history, and trophy cabinet. Remaining work is deployment of the web interface and final comparison with the native app on a device.

# Agreed Today’s Update design

Today’s Update is a blog feed. The newest post appears first, followed by earlier posts with their publication dates, messages, and optional YouTube thumbnails. Tapping a thumbnail opens YouTube or the browser. Playback is external rather than embedded.

The content source is a `todays_update` tab in the existing MBCC Google workbook. Each row is one post, using `published_date`, `title`, `message`, and `youtube_url` headers. The user confirmed the worksheet is set up. Enter dates as plain text in `YYYY-MM-DD` form. Append rows to preserve history; edit rows to revise posts and delete rows to remove posts. Future dates stay hidden until that day in Eastern Time. Multiple posts on one date remain visible, with later worksheet rows first.

# Current differences

| Area | Streamlit web app | iPhone app source |
| --- | --- | --- |
| Layout | Responsive cards, bottom navigation, and detail views in the browser | Native SwiftUI cards and navigation |
| Standings | Correct picks, smaller MBCC score, competition ranks, metric switch | Same score presentation and ranking rules |
| Games and picks | Cards open game details, player filters, verification, and ESPN links | Same content in native detail screens |
| Charts and elimination | Both under Season, with the shared pairwise logic | Both under Season |
| Playoff bracket | Bracket tab; four scrolling rounds, player picks, and game details | Same round classification and content; tap a matchup for details |
| Today’s Update | Latest post at the top of Live; full blog archive and external YouTube thumbnails | Same content and ordering |
| Live data source | Shared backend API for all live content | Same shared backend API |
| Verification | Freshness and field comparisons match the iPhone rules | Game and score matching statuses and field comparisons |
| Refreshing | Every minute while active; last successful results retained in the current session | Every minute while active, foreground refresh, pull to refresh, and on-disk saved results |
| Season | Configured MBCC 15 and 2026–27; no fixed end-of-season cutoff | Configured for MBCC 15 and 2026–27 |

Both versions include the core standings, picks, correct picks chart, Argyle metrics, elimination checks, history, and rules. Their interfaces can remain different while their content and data behavior are aligned.

# Implementation and deployment status

The iPhone blog feed and Python backend support are implemented locally. The backend returns the published `updates` array and retains `todaysUpdate` for compatibility with the earlier single post response. The iPhone model also accepts that earlier response.

The existing live backend was verified on November 20, 2026: real data, `gamesSource: live_scores_and_games`, 48 games, and one published post. The Streamlit loader accepts this response. `MBCC_UPDATES_ENABLED` remains `1` in Cloud Run configuration. The earlier local CLI Python blocker does not prevent using the now-running API.

For a future backend update, upload `mbcc-cloudrun.zip` to Cloud Shell and run:

```sh
unzip -o ~/mbcc-cloudrun.zip -d ~/mbcc-cloudrun
cd ~/mbcc-cloudrun
bash cloudrun/update-live-source.sh
```

The script verifies the game source, blog feed, and playoff totals. This backend workflow does not deploy the Streamlit interface. Web hosting needs the updated `app.py`, `web_app` package, requirements, theme, and demo fixture. All live content uses the shared API; web hosting needs no Google credentials or backend adapter. See README for configuration and run instructions.

Validation completed: 69 backend, web model, and Streamlit interaction checks passed. Browser checks cover all five tabs, blog archive, external video links, game details, fixed navigation, and horizontal overflow at 320 px, 390 px, and 1440 px. Screenshots are in `outputs/streamlit`. The Google Sheets path was tested with worksheet fixtures; the real shared API was checked directly. The earlier Swift checks and iPhone build passed, but native visual testing still needs a working Simulator or a physical device.

# Checklist for the next session

- [x] Confirm the live backend and published post count.

- [ ] Rebuild and run the iPhone app; verify the newest post, older posts, thumbnails, and external YouTube links.

- [x] Add Today’s Update to Streamlit using the same worksheet and publication ordering.

- [x] Route all live Streamlit data through the same backend API as the iPhone app.

- [x] Add game and score verification displays to Streamlit.

- [x] Replace Streamlit’s hardcoded season labels and January 2026 filter cutoff with season aware behavior.

- [x] Align refresh behavior and Eastern Time date handling where practical.

- [ ] Deploy the rewritten Streamlit app with the new supporting files and requirements.

- [ ] Compare both interfaces against the same spreadsheet data for standings, picks, charts, elimination, and history.

- [ ] Resolve the Simulator version mismatch or complete visual checks on a physical iPhone.

# Project references

Project root: `/Users/chrism/Documents/MBCCA/mbcc`

- Streamlit interface: `/Users/chrism/Documents/MBCCA/mbcc/app.py`

- iPhone screens: `/Users/chrism/Documents/MBCCA/mbcc/ios/MBCC/Views.swift`

- iPhone models: `/Users/chrism/Documents/MBCCA/mbcc/ios/MBCC/Models.swift`

- Worksheet adapter: `/Users/chrism/Documents/MBCCA/mbcc/backend/sheets_adapter.py`

- Backend API: `/Users/chrism/Documents/MBCCA/mbcc/backend/server.py`

- Deployment configuration: `/Users/chrism/Documents/MBCCA/mbcc/cloudrun/env.yaml`

- Deployment package: `/Users/chrism/Documents/MBCCA/mbcc/mbcc-cloudrun.zip`

- Setup and validation instructions: `/Users/chrism/Documents/MBCCA/mbcc/README.md`

Suggested restart request: “Continue the MBCC Streamlit and iPhone follow up. Check deployment first, then align Today’s Update, game data, verification, and season handling.”

