#!/usr/bin/env bash
# Update the existing Cloud Run service using its existing runtime/build identities.
set -euo pipefail

MBCC_PROJECT="project-72f15f51-cfef-4c90-b6e"
MBCC_REGION="us-east1"
MBCC_READER="mbcc-sheet-reader@${MBCC_PROJECT}.iam.gserviceaccount.com"
MBCC_BUILDER="mbcc-api-builder@${MBCC_PROJECT}.iam.gserviceaccount.com"
MBCC_SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$MBCC_SOURCE"

echo "Updating mbcc-api with live scores and the Today’s Update blog feed."
gcloud run deploy mbcc-api \
  --project="$MBCC_PROJECT" --region="$MBCC_REGION" --source=. \
  --service-account="$MBCC_READER" \
  --build-service-account="projects/${MBCC_PROJECT}/serviceAccounts/${MBCC_BUILDER}" \
  --env-vars-file=cloudrun/env.yaml \
  --cpu=1 --memory=512Mi --min=0 --max=1 \
  --concurrency=8 --timeout=60 --cpu-throttling --quiet

MBCC_URL=$(gcloud run services describe mbcc-api --project="$MBCC_PROJECT" \
  --region="$MBCC_REGION" --format='value(status.url)')
MBCC_RESPONSE=$(mktemp)
trap 'rm -f "$MBCC_RESPONSE"' EXIT
if ! curl --fail --silent --show-error --max-time 60 \
  "${MBCC_URL}/api/snapshot" --output "$MBCC_RESPONSE"; then
  echo "The service deployed, but its snapshot failed. Recent server diagnostics:"
  gcloud run services logs read mbcc-api --project="$MBCC_PROJECT" \
    --region="$MBCC_REGION" --limit=20
  exit 2
fi
python3 - "$MBCC_RESPONSE" <<'PY'
import json
import sys

with open(sys.argv[1]) as response:
    snapshot = json.load(response)
if snapshot.get("isDemo") is not False or snapshot.get("gamesSource") != "live_scores_and_games":
    raise SystemExit("The service is not reading live_scores_and_games; check the deployed configuration.")
games = snapshot.get("games", [])
if not games:
    raise SystemExit("The live tab returned no games; check the uploaded tab.")
updates = snapshot.get("updates")
if not isinstance(updates, list):
    raise SystemExit("The service did not return the blog feed; check the deployed backend.")
if snapshot.get("todaysUpdate") != (updates[0] if updates else None):
    raise SystemExit("The featured post does not match the blog feed.")
print("Source confirmed: live_scores_and_games;", len(games), "games.")
print("Published blog posts:", len(updates))
if snapshot.get("playoffStandingsError"):
    raise SystemExit("The API is running, but playoff history could not load. Check Viewer access to the separate history workbook and the playoff_history tab.")
playoff_standings = snapshot.get("playoffStandings")
if not isinstance(playoff_standings, list):
    raise SystemExit("The service did not return playoff standings; check the backend and MBCC_PLAYOFF_HISTORY_ENABLED configuration.")
print("All-time playoff users:", len(playoff_standings))
print("Verified games:", sum(game.get("gameVerification") == "verified" for game in games))
print("Verified scores:", sum(game.get("verification") == "verified" for game in games))
print("Imported entries stay unverified until the first successful automatic check.")
PY
echo "App connection remains: ${MBCC_URL}/api/snapshot"
