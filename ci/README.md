# CI for the native-preset-mode fork

Fork-only folder (not in upstream jmcollin78/versatile_thermostat), so nothing here
ever conflicts with an upstream merge. The project's top-level `README.md` is
upstream's and is deliberately left untouched for the same reason.

## Jobs (Jenkins on LXC 200)

| Job | File | What it does |
|---|---|---|
| `versatile-thermostat-sync` | `ci/Jenkinsfile.sync` | Weekly (Monday 03:00): merges `upstream/main` into `native-preset-mode`, pushes, and if anything new came in cuts a fork release for HACS. |
| `versatile-thermostat` | `ci/Jenkinsfile` | Full pytest suite in a Python venv on the Jenkins agent (`BRANCH` parameter). |

## Sync job: merge and versioning

- **Real merge, not fast-forward** — `native-preset-mode` always carries the
  native_preset_mode patch commits on top of upstream.
- **Version-line conflicts are resolved automatically.** The fork bumps its own
  patch version in `manifest.json` on every release, so every new upstream
  release conflicts on that one line (first hit 2026-10-12: fork 10.5.2 vs
  upstream 10.5.1). If `manifest.json` is the *only* conflicted file and the two
  sides differ in nothing but the `"version"` line, the job takes upstream's
  manifest and continues. Any other conflict aborts the merge and fails the job —
  resolve it by hand.
- **Release version** = patch + 1 on the *higher* of the fork's pre-merge version
  and the merged manifest version, skipping any `vX.Y.Z` tag that already exists.
  So the fork version never goes backwards and never reuses a tag (10.5.2 fork +
  10.5.1 upstream → 10.5.3).
- The release is a GitHub release with `versatile_thermostat.zip` attached. HACS
  shows it as an update on its next refresh; installing it in HA is a manual step.

## Dry-running the sync logic

Extract the `sh '''…'''` block, replace `git push …` with an echo and run it with
`sh -e` in an empty directory (e.g. on the Jenkins container). Run it on Linux:
upstream has branch names long enough to break a Windows checkout.
