#!/usr/bin/env bash
# Fail-fast guard: refuses a dirty working tree before a proof stamps
# source_commit=$(git rev-parse HEAD) or otherwise attributes a run to HEAD.
#
# "Dirty" means anything `git status --porcelain` reports: staged changes,
# unstaged edits to tracked files, or untracked files. Any of these can make
# what actually executes differ from HEAD, so a run that stamps HEAD as its
# source_commit would misattribute the result. Gitignored proof/runtime
# output (proof/, tmp/, etc.) is intentionally exempt: `git status
# --porcelain` without `--ignored` never reports ignored paths, so leaving
# generated evidence in place never trips this check.
#
# Usage:
#   source require_clean_source.sh; require_clean_source "$REPO_DIR"
#   bash require_clean_source.sh [REPO_DIR]   # standalone CLI check

require_clean_source() {
  local repo="${1:-.}"
  local dirty
  dirty="$(git -C "$repo" status --porcelain 2>&1)" || {
    printf 'ERROR: could not read git status for %s:\n%s\n' "$repo" "$dirty" >&2
    return 2
  }
  if [[ -n "$dirty" ]]; then
    printf 'ERROR: repository is not clean; refusing to attribute this run to HEAD (source_commit would be wrong):\n' >&2
    printf '%s\n' "$dirty" >&2
    printf 'ERROR: commit, stash, or discard the changes above and retry.\n' >&2
    return 1
  fi
  return 0
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  # Invoked directly (not sourced): act as a standalone CLI check so tests
  # (and operators) can exercise this in isolation, without booting anything.
  require_clean_source "${1:-.}"
  exit $?
fi
