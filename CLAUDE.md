# Chubbs Peterson Invitational (CPI) — Golf Scoring Suite

Monthly golf tournament app for a friend group in Nansha. Season runs Sept→June (10 events). The suite is three apps under one GitHub repo, two Netlify sites, one Firebase project.

## Repos & Deployments

| Path | What | Netlify site | Deploys |
|---|---|---|---|
| `ChubbsMobileApp_v5/` | Scorer PWA used by players on course | `chubbs-golf.netlify.app` | auto on push to master |
| `ChubbsAdmin/` | Event-setup portal used by organiser | `chubbs-admin.netlify.app` | auto on push to master |
| _(future)_ | Public leaderboard | TBD (separate site) | not yet built — see `Archive/chubbs-golf-app-master.zip` |

GitHub: `mph1969/chubbs-golf-app` (this repo). Firebase project: Realtime Database under Michael's account.

## Tech Stack

- **Vanilla JS, no build step.** Each app is a single `index.html` with inline `<script>`; Netlify serves as-is.
- **Firebase Realtime Database** for cross-device event sync + admin-to-mobile handoff.
- **Service Worker** on the mobile PWA only. Admin has no SW.
- **localStorage** for state, roster, history, season store.
- **No framework, no bundler.** Edit the HTML, commit, push. Done.

## Data Flow

```
Admin builds event config ──push──► Firebase /events/{eventId}/bundle
                                           │
                                           ▼
                          Mobile pulls bundle, scores the round
                                           │
                                           ▼
                       User taps "Save snapshot" when done
                                           │
                      ┌────────────────────┴────────────────────┐
                      ▼                                         ▼
           cpi_history_v1 (last 12 rounds)        chubbs_seasons_v1 (ACTIVE_SEASON)
           via saveEventSnapshot()                 via appendCurrentEventToActiveSeason()
```

## Key Files

**Mobile PWA (`ChubbsMobileApp_v5/`)** — ~6,200 lines in `index.html`:
- `stablefordPoints()` (~2271) — **6/5/4/3/2/1/0** for net diff ≤−4 / −3 / −2 / −1 / 0 / +1 / ≥+2. Matches CPI Point System exactly.
- `shotsReceived(hcp, si)` (~2265) — `floor(hcp/18) + (si ≤ hcp%18 ? 1 : 0)`. Standard WHS allocation.
- `saveEventSnapshot()` (~1679) — writes to `cpi_history_v1` AND calls `appendCurrentEventToActiveSeason()`.
- `ensureActiveSeason()` / `fetchSeason4IfMissing()` (~1790, 1819) — season store lifecycle.
- `aggregateSeason()` (~1857) — handbook-accurate: best 7 of 10 + 3★ perfect-attendance bonus + playoff cuts.
- `renderSeason()` (~1959) — standings UI with Top-16 seed line + qualified-16 playoff line + ⚠ DNQ badges.
- `season-4.json` — baked historical Season 4 data (7 events, 111 player-rounds Sept-Mar).

**Admin (`ChubbsAdmin/`)** — ~2,500 lines:
- `season-4.json` — copy of mobile's season data (kept in sync — Python extractor writes both).
- `buildPlayoffPayload()` / `renderPlayoffCard()` (v5.25) — §11 R16+QF setup card. Loads `./season-4.json`, applies admin's roster overrides, computes top-16 seedings, embeds in event bundle as `playoffs.{seeds, stage, seededAt, ...}`. Mobile receives → `season.playoffs.seeds` locked with `source:'admin'`.
- `exportConfig()` / `applyConfigPayload()` — clone-an-event workflow. `init()` runs BEFORE form repopulation (order fix in v5.38) so course + date fields survive import.
- `showLibraryPanel()` — in-app archive of 20 most-recent exports (bundles + configs), independent of OS download folder.
- `pushToLiveApp()` — writes event bundle to Firebase.
- Top-button groups: Data / Deploy / Danger (v5.38 layout).

## Scoring Rules — Source of Truth

**The CPI Handbook.pdf in `ChubbsMobileApp_v5/` is authoritative.** Before changing any scoring logic, read the relevant section:

| § | Rule | Status |
|---|---|---|
| 3.2 | Handicap auto-adjust (>45→−3, 41-45→−2, 36-40→−1, 27-35→0, 16-26→+1, <15→+2) | ✅ v5.40 (suggestions card on Leaderboard tab, one-tap apply) |
| 5.2 | Spenny pickup convention (par-3→gross 7, par-4→8, par-5→10) | ⏳ informational only |
| 5.8 | Tiebreaker hierarchy (birthday > new parent > marriage > countback > handicap) | ⏳ not implemented; app uses gross-countback |
| 6.1 | Stableford table | ✅ v5.35 |
| 8.1-8.4 | Gold jacket, clown jacket, 3-time winner golden underwear | ⏳ not tracked |
| 10.2 | Season points: best 7 + 3★ perfect-10 bonus, rank points [13,11,10,9,8,7,6,5,4,3,2,1] | ✅ v5.39 |
| 11 | Playoffs: top 16 after 8 rounds, min 3 rounds to qualify | ✅ v5.39 (prediction only — bracket UI not built) |
| 12 | Shooter Cup October Ryder Cup format | 🟡 data hook shipped (event.players[i].overrideSeasonPts) — admin UI deferred until October |

## Season Infrastructure

The mobile app has a durable "seasons" concept:

- **Constants at the top of the season module** (`ACTIVE_SEASON_ID`, `ACTIVE_SEASON_NAME`, `DEFAULT_RANK_POINTS`). Bump `ACTIVE_SEASON_ID` at season rollover (~June for S4→S5).
- **`chubbs_seasons_v1` localStorage** = `{ viewingSeasonId, seasons: { 'season-4': {...}, 'season-5': {...} } }`.
- **Season 4 is baked-in:** `ChubbsMobileApp_v5/season-4.json` is generated from `Season 4 Scores.xlsx` (Terry's sheet) via a Python extractor in the parent directory. Regen when the xlsx updates.
- **Phase 2 live-accumulate:** `appendCurrentEventToActiveSeason()` runs on every `saveEventSnapshot()`, keying by event id so re-saves overwrite in place.
- **Player-name normalization** lives in the Python extractor: Mike H → Hanson, Mike → Mike W, Stuartom → Stuart, Ryan → Ryan N, PLZ → Penglei, Greame → Graeme. Three Matts: **Matt D** (top of standings), **Matthew SA** (new South African player — Mar Qingyuan "Other Matt", Apr Palm "Mathew"), **Matty** (older Shenzhen player matty_11989, none in current 8-event dataset). Map: bare "Matt" → Matt D when Matt D not already in event; "Other Matt" / "Mathew" → Matthew SA.

## Deployment Workflow

1. Edit the relevant `index.html` (mobile or admin).
2. If mobile: bump `CACHE_VERSION` in `sw.js` on every deploy that touches mobile assets (monotonically increasing — just bump by +1). Bump `APP_VERSION` in `index.html` when shipping a user-visible release. **The two do NOT need to match** — CACHE_VERSION has historically run ahead of APP_VERSION (drift was ~20 by v5.59) because cosmetic/fix commits bumped CACHE without an APP_VERSION roll. All that matters for cache invalidation is that CACHE_VERSION differs from the previously deployed value.
3. Commit, push to master.
4. Netlify auto-deploys within ~45s.
5. PWA shows an update-available banner on next load.

## localStorage Keys

| Key | Purpose |
|---|---|
| `cpi_chubbshub_v4` | Active event state (players, scores, options) |
| `chubbs_mobile_event_cache_v1` | Last 5 event bundles for offline restore |
| `cpi_history_v1` | Up to 12 past-round snapshots (for Restore Scores) |
| `chubbs_seasons_v1` | Season store (Season 4 + any future seasons) |
| `chubbs_event_library_v1` | Admin in-app archive (20 most recent exports) |
| `chubbs_admin_collapsed_v1` | Admin card collapse preferences |
| `chubbs_fontsize` | UI font-size preference (std/large/xl) |
| `dc_pro_v1` | Pro unlock (unused on Chubbs — DX! Golf only) |

## Untracked In-Repo Files (local-only)

- `Season 4 Scores.xlsx` — Terry's season spreadsheet, source for `season-4.json`.
- `LIVE-APRIL-CHUBBS-At-config-2026-04-17.json` — Michael's local April event config.
- `NewFeatures/files.zip` — draft public-leaderboard prototype (legacy).
- `Archive/chubbs-golf-app-master.zip` — snapshot of the public-leaderboard sub-app (same repo, different subfolder presumably).

These stay untracked — do not `git add` them in a commit unless explicitly asked.

## Recurring Conventions

- **Bump CACHE_VERSION on every mobile deploy; bump APP_VERSION on user-visible releases.** Values intentionally drift — see Deployment Workflow above. Do NOT "fix" the offset by lowering CACHE_VERSION — that would break cache invalidation for users on the current cache.
- **Commit messages follow the pattern** `Area: short headline (vX.YZ)`. Feature intent in the body, not implementation.
- **Push immediately after each feature** — Michael actively tests on iPhone between pushes and shares links with the brain trust.
- **Don't re-implement what's in the handbook PDF.** Cite the section in code comments when shipping handbook-sourced logic.
