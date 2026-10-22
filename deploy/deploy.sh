#!/usr/bin/env bash
# Update the API on the server: pull, sync dependencies, restart.
# Usage (from your machine): ssh root@<host> 'bash -s' < deploy/deploy.sh
set -euo pipefail

APP_USER=truckrouting
APP_DIR=/home/$APP_USER/app

sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
sudo -u "$APP_USER" bash -lc "cd $APP_DIR/backend && ~/.local/bin/uv sync --frozen --no-dev"
systemctl restart truck-routing
sleep 2
curl -fsS http://127.0.0.1:8100/api/health && echo " <- API healthy"
