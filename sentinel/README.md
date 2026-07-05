# Sentinel — Offline AI-Powered Windows System Maintenance Agent

Sentinel watches your disk, figures out what's safe to clean, and asks
before it touches anything. It never runs automatically without your
approval, never phones home, and never needs the internet.

## Why it's safe by design

The single hard rule underneath everything else: **nothing is ever deleted
without an explicit, per-item Approve click.** This isn't a UI convention —
it's enforced in code at three independent layers:

1. **`utils/safety_rules.py`** — a default-deny path classifier. Anything
   under Documents, Desktop, Pictures, Videos, System32, Program Files,
   the registry, drivers, `.git`, `.ssh`, OneDrive, etc. is permanently
   blacklisted (`NEVER_TOUCH_PATTERNS`). Anything *not* recognized as a
   known cache/temp/build-artifact location is treated as protected by
   default — recognized-safe is an allowlist, not the other way around.
2. **`core/permission.py` + `gui/approval_dialog.py`** — the agent loop
   cannot reach the executor without going through `PermissionProvider.ask()`,
   which for the GUI means a modal dialog with per-category Approve /
   Reject / View Details buttons and no "approve everything" shortcut for
   anything above "high confidence."
3. **`services/cleanup_executor.py`** — the *only* module allowed to call
   `os.unlink`/`shutil.rmtree`. It raises `ValueError` if handed anything
   where `.approved is not True`, and independently re-checks every path
   against the protected-path blacklist even if something upstream got it
   wrong. This is covered by `tests/test_cleanup_executor.py`.

## Architecture

```
sentinel/
  core/            Agent loop skeleton, permission gate, wake-trigger scheduler
  agents/          Concrete agents (CleanupAgent today; RAM/CPU/Battery/etc. later)
  services/        Read-only scanners, disk monitor, cleanup executor, reports
  models/          SQLite persistence (preferences/learning, action log), dataclasses
  gui/             PySide6 dashboard, approval dialog, settings, history
  utils/           Safety rules, logging, config, elevation, notifications
  config/          default_config.json + generated user_config.json + sentinel.db
  logs/            sentinel.log (human log) + actions.jsonl (structured action log)
  tests/           pytest unit + integration tests, plus example scan data
```

### The agent loop

Every agent (today: `CleanupAgent`; tomorrow: RAM/CPU/Battery/Security/
Startup-Optimizer/etc.) subclasses `core.agent_base.BaseAgent` and
implements four steps:

```
Observe -> Analyze -> Reason -> [Ask Permission] -> Execute -> Verify -> Log -> Sleep
```

`BaseAgent.run_once()` owns the plumbing: it calls your `observe/analyze/
reason`, checks learned auto-approve preferences, prompts for anything
left, and only then calls your `execute_approved`. You cannot skip the
permission step from inside a subclass — it happens in the base class
before `execute_approved` is even called.

### Triggers

`core/triggers.py` implements the two wake conditions from the spec:

- **Periodic** — every N minutes (default 30, configurable in Settings).
- **Storage threshold** — polled every 15s (configurable); if any drive's
  free space drops below the configured threshold (default 20 GB), the
  agent wakes immediately regardless of the periodic timer.

Whichever fires first wins; `TriggerScheduler.wait_for_next_wake()`
returns a `WakeEvent` describing which one it was, which shows up in the
dashboard status bar and the action log.

### Extending with new cleanup categories

Add a function to `services/scan_targets.py` following the existing
pattern (return a `ScanTargetResult` or `None`), then add it to the
`TARGET_SCANNERS` dict. No changes are needed anywhere else — the agent,
GUI, executor, and reports all pick it up automatically. This is where
you'd add the Docker/Conda/Unity/Unreal/Visual Studio/Android Studio/
duplicate-photo scanners from the original spec; they were intentionally
left as an extension point rather than shipped half-tested, since each
one (especially Docker image/volume pruning) has real footguns that
deserve their own careful safety review and its own test file, the same
way `node_modules`/`venv` detection got here.

### Extending with new agent types (RAM, CPU, Battery, Security, ...)

Subclass `BaseAgent`, implement `observe/analyze/reason/execute_approved`
for that domain, and instantiate it alongside `CleanupAgent` in
`gui/main_window.py`'s `AgentWorker`. Each agent gets its own
`TriggerScheduler` and `PermissionProvider` instance, so a RAM agent
could wake on a different cadence than the cleanup agent without any
cross-talk.

## Installation (development)

```powershell
git clone <this-repo> Sentinel
cd Sentinel
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Requires Windows 10/11 for full functionality (Recycle Bin, Prefetch,
Delivery Optimization, etc. are Windows-specific paths). The core logic
(safety rules, scanners' path detection, executor, tests) also runs on
Linux/macOS for development purposes — `list_local_drives()` falls back
to `/` on non-Windows so you can develop and run the test suite anywhere.

## Running the tests

```powershell
pip install pytest
pytest tests/ -v
```

24 tests cover: the protected-path blacklist (Documents/Desktop/System32/
Program Files must always be refused), confidence classification, the
"never delete without explicit approval" invariant in the executor
(including a test that an *approved* but protected path is still
refused), disk health scoring, and a full headless agent cycle using an
auto-reject permission provider to prove nothing gets deleted without a
human saying yes.

## Packaging with PyInstaller

```powershell
pip install pyinstaller
pyinstaller sentinel.spec
```

This produces `dist/Sentinel/Sentinel.exe` (onedir build — more reliable
than onefile for PySide6 apps, since onefile's temp-extraction step can
trip antivirus heuristics on a system-maintenance tool). Copy the whole
`dist/Sentinel/` folder to distribute it; `config/default_config.json` is
bundled in automatically via the spec's `datas` entry.

Note: `uac_admin=False` in the spec is intentional — Sentinel does not
request admin rights for the whole process at launch. Instead,
`utils/elevation.py` requests elevation (via a standard UAC prompt, never
bypassed) only when a specific approved action needs it, e.g. clearing
`C:\Windows\SoftwareDistribution` or `C:\Windows\Prefetch`.

## Auto-start on Windows

Two options, both optional and off by default:

1. **Settings toggle** ("Start Sentinel automatically on Windows login")
   — writes to `config/user_config.json`; wiring this to an actual
   Registry Run key or Startup folder shortcut is a small addition in
   `utils/` (`elevation.py` deliberately doesn't touch the registry today,
   to keep the "never bypass Windows security" boundary crisp — happy to
   add a `startup_manager.py` if you want this fully wired).
2. **Task Scheduler** — run `scripts/create_scheduled_task.ps1` from an
   elevated PowerShell prompt, pointing it at your built `Sentinel.exe`:
   ```powershell
   .\scripts\create_scheduled_task.ps1 -ExePath "C:\Path\To\Sentinel.exe"
   ```

## What's implemented vs. what's an extension point

**Fully implemented and tested:** the agent loop, both triggers, disk
monitoring with health scoring, 18 concrete cleanup scanners (Windows/
User Temp, Recycle Bin, Thumbnail Cache, Crash Dumps, Browser Cache,
Windows Update leftovers, Delivery Optimization, Prefetch, pip/npm/
Gradle/Maven/VS Code caches, old Downloads, old zip/ISO files, unused
node_modules and Python venvs), the full safety/permission/execution
chain, SQLite-backed learned preferences, structured logging + monthly
reports, and the dark-mode dashboard/approval/settings/history GUI.

**Left as a documented extension point, not stubbed out silently:**
Docker image/container/volume pruning, Conda environments, and the
IDE-specific caches for Unity/Unreal/Visual Studio/Android Studio, plus
duplicate-file/duplicate-photo detection. These all need external
tooling calls (`docker`, `conda`) or perceptual hashing, and each
deserves its own scanner + its own safety-focused test file rather than
being bolted on unverified. The scanner registry pattern above makes
adding them mechanical once you're ready.
