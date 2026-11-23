# MBCC Streamlit and iPhone follow up

Saved Page: https://chatgpt.com/space/page_9ba1d1d21fb4819182efefce0a86cf65

Updated November 23, 2026 with a Bracket tab in both interfaces. It shows the existing schedule’s playoff games in four rounds, with scores, winners, player picks, and game details. The live schedule contains 11 labeled playoff games, currently with TBD opponents. No spreadsheet or backend changes are required. Web publication and an iPhone rebuild are still needed to ship this change. On compact iPhone tab bars, History and Info are under More.

Validation: 71 Python checks and Swift model checks passed; the iPhone simulator build passed. Browser checks cover all six tabs and bracket navigation at 320, 390, and 1440 pixels. Native UI tests were compiled but could not launch because the installed iOS 27.0 Simulator runtime path is unavailable. Bracket screenshots are in `outputs/playoff-bracket`.

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
| Game source | Shared backend API, or existing Sheets connection using the same adapter | Shared backend API |
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

The script verifies the game source and blog feed and prints the published post count. This backend workflow does not deploy the Streamlit interface. Web hosting needs the updated `app.py`, `web_app` package, `backend` adapter, requirements, theme, and demo fixture. Existing Google Sheets secrets remain usable, or the web app can use the shared API without Google credentials. See README for configuration and run instructions.

Validation completed: 69 backend, web model, and Streamlit interaction checks passed. Browser checks cover all five tabs, blog archive, external video links, game details, fixed navigation, and horizontal overflow at 320 px, 390 px, and 1440 px. Screenshots are in `outputs/streamlit`. The Google Sheets path was tested with worksheet fixtures; the real shared API was checked directly. The earlier Swift checks and iPhone build passed, but native visual testing still needs a working Simulator or a physical device.

# Checklist for the next session

- [x] Confirm the live backend and published post count.

- [ ] Rebuild and run the iPhone app; verify the newest post, older posts, thumbnails, and external YouTube links.

- [x] Add Today’s Update to Streamlit using the same worksheet and publication ordering.

- [x] Align Streamlit game data through the shared API or the existing Sheets connection with the shared adapter.

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

