#!/bin/bash
# Deploy token dashboard to Vercel
# Usage: ./deploy.sh [vercel-project-name]

set -e

PROJECT_NAME="${1:-hermes-token-dashboard}"
DASHBOARD_DIR="/home/ubuntu/token-dashboard"

cd "$DASHBOARD_DIR"

echo "🔄 Generating latest dashboard..."
python3 scripts/generate_dashboard.py

echo "📦 Checking git status..."
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "📝 Committing changes..."
    git add -A
    git commit -m "chore: update token dashboard $(date '+%Y-%m-%d %H:%M')"
else
    echo "✅ No changes to commit"
fi

echo "🚀 Deploying to Vercel..."
if npx vercel@latest --prod --scope=$(npx vercel@latest whoami 2>/dev/null | head -1) --yes --token="$VERCEL_TOKEN" 2>/dev/null; then
    echo "✅ Deployed successfully!"
else
    echo "⚠️  Vercel CLI deploy failed, trying git push method..."
    git push origin main
    echo "✅ Pushed to GitHub - Vercel will auto-deploy"
fi

echo ""
echo "📊 Dashboard: https://$PROJECT_NAME.vercel.app"
echo "📁 Local: file://$DASHBOARD_DIR/index.html"