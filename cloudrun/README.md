# Cloud Run deployment

Project: `project-72f15f51-cfef-4c90-b6e`  
Service: `mbcc-api`  
Region: `us-east1`  
Runtime identity: `mbcc-sheet-reader@project-72f15f51-cfef-4c90-b6e.iam.gserviceaccount.com`

The owner deployed this service successfully. Its live endpoint is
[the MBCC snapshot API](https://mbcc-api-jarvycxodq-ue.a.run.app/api/snapshot).
On October 29, 2026 it returned real results (`isDemo: false`) for 10 players,
48 games, 133 player-season history rows, and 14 seasons. The iPhone app uses
this endpoint by default for new installations.

The owner chose public, read-only results without player sign-in. Anyone with the
API URL can read the fields returned by `/api/snapshot`. The service account gets
Viewer access to the challenge workbook, with no project-level data roles
and no downloadable service-account keys. Streamlit remains separate.

## Deployment steps

Always name the deployment archive `mbcc-cloudrun.zip`, replacing the previous
package when preparing an update. Do not add dates or feature names to the filename.

Private group values belong only in the service's `MBCC_SUB_KEYWORD` and
`MBCC_COMBINED_KEYWORD` environment variables (or Secret Manager references).
Keep them out of source files and the ZIP. `config_updates.py` prepares additive
updates for the non-secret settings in `env.yaml`, so the deployment scripts
preserve container-only variables and existing secret references.

Player keywords use the same runtime-only configuration: add one distinct
`MBCC_[NAME]_KEYWORD` variable for each of the nine players, such as
`MBCC_CHRISTOPHER_KEYWORD` or `MBCC_NICHOLAS_KEYWORD`. The name must match a
unique main-group roster entry, ignoring case, spaces, punctuation, and accents.
The API returns the full main group with that player's `viewerPlayer` metadata;
both apps highlight their picks while retaining everyone in standings. Correct
final picks have a solid green underline, incorrect final picks a dotted gray
underline, and pending picks are bold without a result line. Use one keyword
at a time. Player variables are preserved during source deployment too.

Both apps send the masked entry in `X-MBCC-Keyword` (base64-encoded UTF-8).
The API resolves it, and blank or unmatched values return the main group.
Legacy query-string group selectors do not bypass this lookup. Deploy the API
first, then publish/reboot Streamlit and rebuild the iPhone app.

For the existing service, upload the current `mbcc-cloudrun.zip` to Cloud Shell,
extract it over `~/mbcc-cloudrun`, and run `bash cloudrun/update-live-source.sh`.
This deploys the updated backend with `MBCC_LIVE_SCORES_ENABLED=1` and the
2026–27 season label, then verifies that the response declares
`gamesSource: live_scores_and_games`. It prints game and score verification
counts separately. The existing public endpoint and service identities are reused.
The configuration also enables the `todays_update` worksheet for the blog feed.
Create that tab with `published_date`, `title`, `message`, and `youtube_url`
headers before deploying. The script verifies that the feed is present and
prints the number of published posts; zero posts is valid for an empty worksheet
or one containing only future dates. The iPhone app shows the newest post first
and keeps previous posts below it.
The iPhone project also needs a new build for the updated source/cache handling
and the “Game not verified” / “Scores not verified” labels.

The current configuration also sets `MBCC_PLAYOFF_HISTORY_ENABLED=1` and
`MBCC_PLAYOFF_HISTORY_SHEET_ID=1Iwl1WEzLEXu05ZtFcfZovWwQsECNy8LH3II760C-w2E`.
The API reads only rows 1–3 of `playoff_picks`: user names, `Overall`, and
`Overall Unknown`, and returns the two per-user counts in `playoffStandings`.
The runtime reader account needs Viewer access to this separate workbook.
Existing overall history tabs keep their current challenge-workbook routing.
A failed read of the separate workbook leaves the main snapshot available and
returns a playoff-history availability message. The deployment check reports
whether the new table loaded.

The subgroup has no all-time playoff history worksheet. The API skips that
read, and Streamlit and iPhone explain that subgroup playoff history is not
tracked. Combined views show only main-group all-time playoff totals. A missing
subgroup history worksheet is expected and does not produce a load warning.

The October 29 snapshot described above was the original source check. It did
not yet use the combined live tab. The switch is not applied remotely merely
by updating the local configuration or ZIP; run the update script to deploy it.

For the browser-only workflow, upload `mbcc-cloudrun.zip` using the Cloud Shell
three-dot menu, extract it to `~/mbcc-cloudrun`, and run
`bash cloudrun/deploy.sh` from that directory. See `cloudrun/START-HERE.txt`.
The script enables the required APIs, uses a separate build identity with the
Cloud Run Builder role, deploys the service, and checks both health and real data.
The runtime Sheets-reader account is expected to exist already and have Viewer
access to the challenge workbook. No private key is uploaded.

1. Authenticate the Google Cloud CLI with the Google account that manages the
   existing project, and confirm billing is enabled.
2. Enable Cloud Run, Cloud Build, Artifact Registry, and Google Sheets APIs.
3. Create the runtime service account named above. The deployer/build account
   needs the standard Google source-deployment permissions; the runtime account
   does not need Editor or Owner.
4. In the challenge Google Sheet's Share dialog, add the runtime service-account email
   as a **Viewer**. Turn off the notification checkbox if it is shown. Leave
   each file's general access setting unchanged.
5. Deploy from the repository root:

```sh
gcloud run deploy mbcc-api \
  --project=project-72f15f51-cfef-4c90-b6e \
  --region=us-east1 \
  --source=. \
  --service-account=mbcc-sheet-reader@project-72f15f51-cfef-4c90-b6e.iam.gserviceaccount.com \
  --update-env-vars="$(python3 cloudrun/config_updates.py cloudrun/env.yaml)" \
  --allow-unauthenticated \
  --cpu=1 --memory=512Mi \
  --min=0 --max=1 \
  --concurrency=8 --timeout=60 \
  --cpu-throttling
```

The Dockerfile includes just the API and its runtime dependencies. The source
upload allowlist excludes credential files, the `.env` file, and the Streamlit
and iPhone source code. A small demo fixture is bundled for explicit testing;
`MBCC_DEMO` is absent from the production configuration, so a live-data error
cannot silently turn the service into a demo.

Cloud Run supplies Application Default Credentials for the assigned service
account. **Do not set `GOOGLE_APPLICATION_CREDENTIALS` on Cloud Run.**

Request-based billing and zero minimum instances let the service scale down when
idle. One maximum instance limits scaling; it is not a hard spending cap. Cloud
Build, image storage, and networking can have separate charges. A billing budget
can alert you, but does not automatically stop charges.

## Verify before using the app

All nine worksheet names used by Streamlit—including `basic_history`,
`agg_history`, and `season_history`—are in the challenge workbook
`1jKYvXmWIB39FPGsEIGatP_KTY_VK53TnDxNSBVokfVs`. Both spreadsheet environment
variables therefore point to that same workbook. The separate raw history file
is queried only for the first three rows of `playoff_picks`. The extra `pick_summary` tab is not
needed by the current Streamlit screens.

Check `https://SERVICE_URL/health` for `{"status":"ok"}`, then check
`https://SERVICE_URL/api/snapshot` for a successful JSON response containing
`"isDemo": false`. Health alone does not verify spreadsheet access.
For the new game source, also require `"gamesSource": "live_scores_and_games"`.
Immediately after manual import, neither game nor score verification passes
until `last_fetched_at` records a successful automatic feed check.

If `/api/snapshot` returns 502, check the Cloud Run logs. `HTTPError: 403` commonly
means the runtime account is missing Viewer access or the Sheets API is disabled;
`400` can mean a worksheet name differs from the Streamlit code. No credentials
or spreadsheet contents are included in API error responses.

Streamlit worksheet aliases can differ from the actual Google tab titles. In
that case, set `MBCC_WORKSHEET_TITLES` to a JSON object mapping the aliases in
`backend/sheets_adapter.py` to their actual titles. For example, the YAML entry
`MBCC_WORKSHEET_TITLES: '{"current_pick_success":"Current Scores"}'` maps just
that alias and keeps the other defaults. Do not rename the original worksheets.
The server logs Google's structured 400 message to identify an invalid range;
the public error response still contains no Google error details.

Once the snapshot is verified, open Data Connection in the iPhone app, turn off
Explore demo data, and use `https://SERVICE_URL/api/snapshot`.

## Rollback and billing

Cloud Run retains revisions, and traffic can be moved back to a previous working
revision. Keep the existing Streamlit app running while validating this service.
Creating the service does not create a database or modify spreadsheet values.

The runtime service account can be reused across revisions. Avoid granting it
project-wide Editor/Owner access or the ability to create service-account keys.
