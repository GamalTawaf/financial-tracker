#!/usr/bin/env bash
# Sync .github/rulesets/*.json to this repository via the GitHub Rulesets API.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

REPO="${REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"

shopt -s nullglob
files=(.github/rulesets/*.json)
if [[ ${#files[@]} -eq 0 ]]; then
  echo "No ruleset files under .github/rulesets/" >&2
  exit 1
fi

for file in "${files[@]}"; do
  name="$(jq -r .name "$file")"
  echo "Syncing ruleset '$name' from $file"
  existing_id="$(
    gh api "/repos/${REPO}/rulesets" \
      | jq -r --arg n "$name" '.[] | select(.name == $n) | .id' \
      | head -n1
  )"
  if [[ -n "$existing_id" ]]; then
    echo "  Updating #$existing_id"
    gh api -X PUT "/repos/${REPO}/rulesets/${existing_id}" --input "$file" >/dev/null
  else
    echo "  Creating"
    gh api -X POST "/repos/${REPO}/rulesets" --input "$file" >/dev/null
  fi
done

echo "Done."
