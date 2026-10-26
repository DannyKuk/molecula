#!/usr/bin/env bash
# Creates a ready-to-run worktree under .claude/worktrees/, or removes one.
#   scripts/worktree.sh <branch>            new branch from main, or the existing branch
#   scripts/worktree.sh <branch> --remove   removes the worktree; the branch stays
# A new worktree gets the main checkout's .env (with DATA_DIR pointing at its data/, so the store
# isn't downloaded again) and frontend/.env.local, then npm ci and uv sync.
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 || ( $# -eq 2 && $2 != "--remove" ) ]]; then
  echo "usage: scripts/worktree.sh <branch> [--remove]" >&2
  exit 2
fi

branch=$1
main=$(cd "$(git rev-parse --git-common-dir)/.." && pwd)
path="$main/.claude/worktrees/${branch//\//-}"

if [[ ${2:-} == "--remove" ]]; then
  git -C "$main" worktree remove "$path"
  echo "removed $path (branch $branch kept)"
  exit 0
fi

if git -C "$main" show-ref --verify --quiet "refs/heads/$branch"; then
  git -C "$main" worktree add "$path" "$branch"
else
  git -C "$main" worktree add -b "$branch" "$path" main
fi

if [[ -f "$main/.env" ]]; then
  main_data=$(cygpath -m "$main/data" 2>/dev/null || echo "$main/data")
  if grep -q '^DATA_DIR=.' "$main/.env"; then
    cp "$main/.env" "$path/.env"
  else
    grep -v '^DATA_DIR=' "$main/.env" > "$path/.env"
    echo "DATA_DIR=$main_data" >> "$path/.env"
  fi
fi
[[ -f "$main/frontend/.env.local" ]] && cp "$main/frontend/.env.local" "$path/frontend/.env.local"

(cd "$path/frontend" && npm ci --no-audit --no-fund)
(cd "$path/backend" && uv sync)

echo "ready: $path"
