#!/usr/bin/env bash
# Deploy the frontend to Vercel production.
#
# Deploys from a copy outside the git repo: on Vercel's Hobby plan a deployment
# whose git commit author isn't the Vercel account owner is "Blocked", and the
# CLI attaches the latest commit's author automatically.
set -euo pipefail

SRC="$(cd "$(dirname "$0")/../frontend" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

rsync -a --exclude node_modules --exclude dist "$SRC/" "$TMP/"
cd "$TMP"
npx --yes vercel deploy --prod --yes
