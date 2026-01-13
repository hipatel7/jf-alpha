#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKTREE_DIR="$ROOT_DIR/.gh-pages"

if [ ! -d "$WORKTREE_DIR" ]; then
  echo "gh-pages worktree not found at $WORKTREE_DIR"
  echo "Run: git worktree add -b gh-pages .gh-pages"
  exit 1
fi

rsync -a --delete "$ROOT_DIR/dashboard/" "$WORKTREE_DIR/"

cd "$WORKTREE_DIR"

if [ -n "$(git status -s)" ]; then
  git add .
  git commit -m "Update dashboard"
  git push origin gh-pages
  echo "Published gh-pages updates."
else
  echo "No changes to publish."
fi
