#!/usr/bin/env bash
set -e

# Go to repo root (adjust if running from scripts/)
cd "$(dirname "$0")/.." || exit 1

# 1. Initialize if needed
if [ ! -d .git ]; then
    echo "[INFO] Initializing new git repo..."
    git init
fi

# 2. Configure default branch
git branch -M main

# 3. Add/update .gitignore
if [ ! -f .gitignore ]; then
    cat > .gitignore <<'EOF'
# Python
__pycache__/
*.py[cod]
*.pyo
.venv/
.python-version

# NDI wheels
ndi/*.whl

# VSCode settings
.vscode/

# OS files
.DS_Store
Thumbs.db
EOF
    echo "[INFO] Created .gitignore"
fi

# 4. Stage everything
git add -A

# 5. Commit
git commit -m "Phase 1 refactor – initial commit with pyenv, setup.bat, preflight tests, and updated README" || {
    echo "[WARN] Nothing to commit (no changes)"
}

# 6. Optional: add remote + push
# Uncomment and edit the URL to push to your GitHub
# git remote add origin git@github.com:youruser/PoseCamPC.git
# git push -u origin main

echo "[OK] Git repo is ready."
git status
