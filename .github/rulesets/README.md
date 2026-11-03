# Branch rulesets (source of truth)

These JSON files define GitHub [repository rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets). Edit here, not only in the GitHub UI.

| File | Branch | Merge method | Required checks |
|------|--------|--------------|-----------------|
| `develop.json` | `develop` | squash only | `backend`, `frontend`, `docker` |
| `master.json` | `master` | merge commit only | those three + `release-gate` |

`release-gate` (in `.github/workflows/ci.yml`) fails any PR into `master` whose head is not `develop`.

## Apply

- **CI:** `.github/workflows/apply-rulesets.yml` syncs `*.json` → GitHub on push to `develop`/`master` (paths under this folder) or `workflow_dispatch`.
- **Local:** `./.github/scripts/apply-rulesets.sh` (uses `gh` auth).

Actions need a classic/fine-grained PAT with **Administration: Read and write** stored as repo secret `RULESET_ADMIN_TOKEN` (`GITHUB_TOKEN` cannot manage rulesets).
