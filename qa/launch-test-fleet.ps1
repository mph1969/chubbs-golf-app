# ── launch-test-fleet.ps1 ──────────────────────────────────────────────────
# Launches 10 isolated Chrome windows tiled on a single monitor for a
# full-round multi-device dry-run of a Chubbs match-play event.
#
# Selection (10 players across the 4 R16 groups):
#   Scorers (4): TERRY (G1), RYAN N (G2), NICK (G3), JACK S (G4)
#   Viewers (3): MATT (G1), GEORGE (G2), RICARDO (G3) — non-scorer per group
#   Full G4 (3): JORDAN, LEIGH, HANSON  (+ JACK S already in scorers = full 4)
#
# So you can watch ONE complete foursome (G4) end-to-end while sampling
# scorer + viewer behaviour from the other three groups.
#
# Why --user-data-dir per window: Chrome's --incognito alone shares state
# across windows in the same profile (same localStorage, same SW). Unique
# user-data-dirs spawn truly independent Chrome instances — each gets its
# own localStorage, cookies, and service worker registration. This mirrors
# 10 separate phones, which is what we want.
#
# Usage:
#   pwsh qa/launch-test-fleet.ps1
#   pwsh qa/launch-test-fleet.ps1 -EventId 2026-LIVE-MAY-LIVE-20260523
#   pwsh qa/launch-test-fleet.ps1 -MonitorWidth 2560 -MonitorHeight 1440
#   pwsh qa/launch-test-fleet.ps1 -MonitorOffsetX 1920   # secondary monitor right of primary
#
# To clean up after testing: close all windows, then delete the profile
# root directory (printed at launch time, lives under $env:TEMP).
# ───────────────────────────────────────────────────────────────────────────

param(
    [string]$EventId        = "2026-TEST5-Brai",
    [int]   $MonitorWidth   = 1920,
    [int]   $MonitorHeight  = 1080,
    [int]   $Cols           = 5,
    [int]   $Rows           = 2,
    [int]   $MonitorOffsetX = 0,
    [int]   $MonitorOffsetY = 0,
    [int]   $StaggerMs      = 600
)

$BaseUrl = "https://chubbs-golf.netlify.app/?loadEvent=$EventId&player="

# Fixed 10-window selection — row-major fill of the grid:
#   Row 1 (cols 0-4):  4 scorers + 1 G1 viewer
#   Row 2 (cols 0-4):  G2 viewer, G3 viewer, 3 × G4 full-foursome
$Players = @(
    @{ name = "TERRY  (G1 scorer)";  pid = "TERRY";   role = "scorer" },
    @{ name = "RYAN N (G2 scorer)";  pid = "RYANN";   role = "scorer" },
    @{ name = "NICK   (G3 scorer)";  pid = "NICK";    role = "scorer" },
    @{ name = "JACK S (G4 scorer)";  pid = "JACKS";   role = "scorer" },
    @{ name = "MATT   (G1 view)";    pid = "MATT";    role = "viewer" },
    @{ name = "GEORGE (G2 view)";    pid = "GEORGE";  role = "viewer" },
    @{ name = "RICARDO(G3 view)";    pid = "RICARDO"; role = "viewer" },
    @{ name = "JORDAN (G4 full)";    pid = "JORDAN";  role = "g4full" },
    @{ name = "LEIGH  (G4 full)";    pid = "LEIGH";   role = "g4full" },
    @{ name = "HANSON (G4 full)";    pid = "HANSON";  role = "g4full" }
)

if ($Players.Count -gt ($Cols * $Rows)) {
    Write-Error "Grid $Cols x $Rows can hold $($Cols * $Rows) windows but $($Players.Count) are configured."
    exit 1
}

$winW = [int]($MonitorWidth  / $Cols)
$winH = [int]($MonitorHeight / $Rows)

# Locate Chrome — try the two common Windows install paths first, then fall back to PATH.
$Chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $Chrome)) { $Chrome = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" }
if (-not (Test-Path $Chrome)) {
    $cmd = Get-Command chrome -ErrorAction SilentlyContinue
    if ($cmd) { $Chrome = $cmd.Source }
}
if (-not (Test-Path $Chrome)) {
    Write-Error "Could not find chrome.exe. Edit the `$Chrome variable in this script with the correct path."
    exit 1
}

# One root temp dir per launch — easy to delete later.
$timestamp   = Get-Date -Format 'yyyyMMdd-HHmmss'
$ProfileRoot = Join-Path $env:TEMP "chubbs-fleet-$timestamp"
New-Item -ItemType Directory -Path $ProfileRoot -Force | Out-Null

Write-Host ""
Write-Host "Chubbs test fleet launcher" -ForegroundColor Cyan
Write-Host "==========================" -ForegroundColor Cyan
Write-Host "Event:        $EventId"
Write-Host "Chrome:       $Chrome"
Write-Host "Grid:         $Cols cols x $Rows rows on ${MonitorWidth}x${MonitorHeight} monitor"
Write-Host "Window size:  ${winW} x ${winH}"
Write-Host "Origin:       ($MonitorOffsetX, $MonitorOffsetY)"
Write-Host "Profile root: $ProfileRoot"
Write-Host ""

for ($i = 0; $i -lt $Players.Count; $i++) {
    $p     = $Players[$i]
    $col   = $i % $Cols
    $row   = [int]($i / $Cols)
    $x     = $MonitorOffsetX + ($col * $winW)
    $y     = $MonitorOffsetY + ($row * $winH)
    $profileDir = Join-Path $ProfileRoot ("p{0:D2}-{1}" -f $i, $p.pid)
    $url   = "$BaseUrl$($p.pid)"

    $idx = ($i + 1).ToString().PadLeft(2)
    Write-Host "[$idx/10] $($p.name)  @ ($x, $y)  ->  $($p.pid)"

    $chromeArgs = @(
        "--user-data-dir=$profileDir",
        "--new-window",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=DefaultBrowserSettingEnabled",
        "--window-size=$winW,$winH",
        "--window-position=$x,$y",
        $url
    )

    Start-Process -FilePath $Chrome -ArgumentList $chromeArgs | Out-Null

    # Small stagger so Chrome doesn't merge subsequent launches into the
    # first window (race during initial profile registration).
    if ($StaggerMs -gt 0 -and $i -lt ($Players.Count - 1)) {
        Start-Sleep -Milliseconds $StaggerMs
    }
}

Write-Host ""
Write-Host "All $($Players.Count) windows launched." -ForegroundColor Green
Write-Host ""
Write-Host "Group structure for reference:" -ForegroundColor Yellow
Write-Host "  R16 G1 (M1 + M2): MATT, JAMIE, PAUL, TERRY*    [scorer = TERRY,  viewer here = MATT]"
Write-Host "  R16 G2 (M3 + M4): GEORGE, ANTHONY, RYANN*, KEVIN  [scorer = RYAN N, viewer here = GEORGE]"
Write-Host "  R16 G3 (M5 + M6): NICK*, RICARDO, DUSTIN, JOHNB   [scorer = NICK,   viewer here = RICARDO]"
Write-Host "  R16 G4 (M7 + M8): JORDAN, JACKS*, LEIGH, HANSON   [FULL foursome — all 4 visible]"
Write-Host ""
Write-Host "Clean up when done:" -ForegroundColor Yellow
Write-Host "  Close all 10 windows, then:"
Write-Host "  Remove-Item -Recurse -Force '$ProfileRoot'"
