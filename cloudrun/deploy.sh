#!/usr/bin/env bash
# Run in Google Cloud Shell after uploading/extracting mbcc-cloudrun.zip.
set -euo pipefail

MBCC_PROJECT="project-72f15f51-cfef-4c90-b6e"
MBCC_REGION="us-east1"
MBCC_SERVICE="mbcc-api"
MBCC_READER="mbcc-sheet-reader@${MBCC_PROJECT}.iam.gserviceaccount.com"
MBCC_BUILDER="mbcc-api-builder@${MBCC_PROJECT}.iam.gserviceaccount.com"
MBCC_SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$MBCC_SOURCE"

trap 'echo "Deployment stopped at line $LINENO. Copy the error above into the chat; do not include credentials." >&2' ERR

echo "Deploying ${MBCC_SERVICE} to ${MBCC_PROJECT} in ${MBCC_REGION}."
echo "This enables the required APIs and creates a public, read-only endpoint."
echo "Configuration: request-based billing, 0 minimum instances, 1 maximum instance."

gcloud projects describe "$MBCC_PROJECT" --format='value(projectId)'
gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  sheets.googleapis.com iam.googleapis.com \
  --project="$MBCC_PROJECT" --quiet

# The owner already created this account and shared the challenge workbook.
gcloud iam service-accounts describe "$MBCC_READER" \
  --project="$MBCC_PROJECT" --format='value(email)'

# Keep build permissions separate from spreadsheet-reading permissions.
if ! gcloud iam service-accounts describe "$MBCC_BUILDER" \
     --project="$MBCC_PROJECT" --format='value(email)' >/dev/null 2>&1; then
  gcloud iam service-accounts create mbcc-api-builder \
    --display-name="MBCC API Builder" --project="$MBCC_PROJECT" --quiet
fi
gcloud projects add-iam-policy-binding "$MBCC_PROJECT" \
  --member="serviceAccount:${MBCC_BUILDER}" \
  --role=roles/run.builder --condition=None --quiet --format=none

echo "The new build permission can take a couple of minutes to become active."
echo "If the first build reports a permission error, wait two minutes and rerun this script."

gcloud run deploy "$MBCC_SERVICE" \
  --project="$MBCC_PROJECT" --region="$MBCC_REGION" \
  --source=. \
  --service-account="$MBCC_READER" \
  --build-service-account="projects/${MBCC_PROJECT}/serviceAccounts/${MBCC_BUILDER}" \
  --env-vars-file=cloudrun/env.yaml \
  --allow-unauthenticated \
  --cpu=1 --memory=512Mi --min=0 --max=1 \
  --concurrency=8 --timeout=60 --cpu-throttling --quiet

MBCC_URL=$(gcloud run services describe "$MBCC_SERVICE" \
  --project="$MBCC_PROJECT" --region="$MBCC_REGION" --format='value(status.url)')
echo ""
echo "Service deployed: ${MBCC_URL}"
echo "App connection URL: ${MBCC_URL}/api/snapshot"
echo "Checking the running API..."
curl --fail --silent --show-error --max-time 60 "${MBCC_URL}/health"
echo ""

MBCC_SNAPSHOT=$(mktemp)
trap 'rm -f "$MBCC_SNAPSHOT"' EXIT
if curl --fail --silent --show-error --max-time 60 \
     "${MBCC_URL}/api/snapshot" --output "$MBCC_SNAPSHOT"; then
  python3 - "$MBCC_SNAPSHOT" <<'PY'
import json, sys
with open(sys.argv[1]) as source:
    snapshot = json.load(source)
if snapshot.get("isDemo") is not False:
    raise SystemExit("Unexpected demo response; do not use this as live results.")
print("Live spreadsheet response verified:", len(snapshot["players"]), "players,", len(snapshot["games"]), "games.")
PY
  echo "Ready: turn off Explore demo data in the iPhone app and use the app connection URL above."
else
  echo "The service is running, but a Sheets request or data format needs attention."
  echo "The server messages below identify access errors or the field that could not be parsed."
  echo "Recent server messages:"
  gcloud run services logs read "$MBCC_SERVICE" \
    --project="$MBCC_PROJECT" --region="$MBCC_REGION" --limit=15
  exit 2
fi

