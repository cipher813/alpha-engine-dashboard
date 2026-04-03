#!/usr/bin/env bash
# deploy.sh — Build Hugo blog and deploy to EC2
#
# Usage:
#   ./blog/deploy.sh              # build + deploy
#   ./blog/deploy.sh --build-only # local build only (no deploy)
#
# Prerequisites:
#   - hugo installed locally
#   - ae-trading SSH alias configured in ~/.zshrc
#   - Nginx config already deployed with /blog/ location block

set -euo pipefail

BLOG_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${BLOG_DIR}/public"
REMOTE_DIR="/var/www/blog"
SSH_ALIAS="ae-trading"

echo "=== Nous Ergon Blog Deploy ==="

# Step 1: Build
echo "[1/3] Building Hugo site..."
cd "$BLOG_DIR"
hugo --minify
echo "  Built to ${BUILD_DIR}"

if [[ "${1:-}" == "--build-only" ]]; then
    echo "  --build-only: skipping deploy"
    echo "  Preview: cd blog && hugo server -D"
    exit 0
fi

# Step 2: Ensure remote directory exists
echo "[2/3] Deploying to EC2..."
ssh "$SSH_ALIAS" "sudo mkdir -p ${REMOTE_DIR} && sudo chown ec2-user:ec2-user ${REMOTE_DIR}"

# Step 3: Rsync built files
rsync -avz --delete "${BUILD_DIR}/" "${SSH_ALIAS}:${REMOTE_DIR}/"
echo "  Synced to ${SSH_ALIAS}:${REMOTE_DIR}"

# Step 4: Verify
echo "[3/3] Verifying..."
ssh "$SSH_ALIAS" "ls -la ${REMOTE_DIR}/index.html"
echo ""
echo "=== Deploy complete ==="
echo "Blog live at: https://nousergon.ai/blog/"
