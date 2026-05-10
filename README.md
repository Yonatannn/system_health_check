# Ground Station Precheck Manager

A Windows-only desktop application that validates a ground station computer's configuration before a flight mission and keeps that configuration synchronized from a local server.

## What it does

Before every mission, the operator opens this tool, selects the operational profile (e.g. "Plane - Field"), and clicks **Run Check**. The tool inspects the computer and reports whether it is **READY**, **READY WITH WARNINGS**, or **NOT READY**.

What is checked:

| Check | What it verifies |
|-------|-----------------|
| Network interfaces | Each configured adapter exists, is up, and has the correct static IPv4 address and subnet |
| Mission Planner files | `joystick.xml` and `config.xml` exist in the Mission Planner directory, are valid XML, and their content matches the expected baseline (SHA256) |
| External config files | Other files (camera, payload, etc.) exist at their target paths and match the expected baseline |

If anything is wrong, the tool shows exactly what was expected vs. what was found. The operator can then click **Apply Profile** to overwrite the incorrect files from the local configuration bundle — the tool creates a timestamped backup first.

When a configuration server (`192.168.1.1`) is available, the operator uses the **Update Bundle** tab to pull the latest configuration from GitLab repositories and SMB shares, rebuild the local bundle, and then disconnect. All subsequent precheck operations work fully offline using that bundle.

## What it does NOT do

- No continuous monitoring or background service
- No MAVLink or Pixhawk communication
- No ArduPilot parameter validation
- No GPS, EKF, battery, or arming checks
- No internet access required during precheck
- No Linux or macOS support

## Tech stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10 |
| GUI | PyQt5 |
| Packaging | PyInstaller → single `.exe` |
| Config format | YAML (profiles, settings, manifests) |
| File integrity | SHA256 |
| Git sync | `git clone` / `git fetch` + `reset --hard` |
| SMB sync | `robocopy /MIR` |
| Network switching | PowerShell (`Set-NetIPInterface`, `New-NetIPAddress`) |

## Project layout

```
├── main.py                          Entry point
├── app/
│   ├── core/                        Data models, YAML loaders, path resolution
│   │   ├── models.py                CheckResult, Profile, BundleManifest dataclasses
│   │   ├── result.py                make_pass/fail/warning helpers, status calculation
│   │   ├── paths.py                 AppPaths — all directory locations in one place
│   │   ├── config_loader.py         Load/save app_settings.yaml
│   │   ├── profile_loader.py        Load profile YAML → Profile objects
│   │   └── bundle.py                Load bundle manifest, validate bundle structure
│   ├── checks/                      Read-only validation logic
│   │   ├── windows_interfaces.py    PowerShell-based adapter enumeration and IP check
│   │   ├── mission_planner_files.py File exist / XML valid / SHA256 match
│   │   ├── external_files.py        Same checks for non-MP config files
│   │   └── xml_validation.py        XML parse check (stdlib ElementTree)
│   ├── windows/                     Windows system integration
│   │   ├── admin.py                 is_admin(), restart_as_admin()
│   │   ├── powershell.py            Safe PowerShell wrapper (stdout, stderr, exit code, timeout)
│   │   ├── adapters.py              List all network adapters with IP info
│   │   ├── ip_config.py             Snapshot / switch-to-DHCP / restore IP configuration
│   │   └── dhcp_context.py          Context manager: DHCP switch + guaranteed restore
│   ├── update/                      Sync and bundle build
│   │   ├── sync_manager.py          Orchestrates the full sync sequence
│   │   ├── gitlab_sync.py           git clone / fetch / reset per repository
│   │   ├── smb_sync.py              robocopy or Python shutil for SMB shares
│   │   ├── bundle_builder.py        Atomic bundle build (temp → validate → replace)
│   │   └── checksum_manifest.py     SHA256 for every file in the bundle
│   ├── actions/                     Write operations triggered by the user
│   │   ├── apply_profile.py         Copy bundle files to target paths
│   │   ├── backup.py                Create timestamped backup before overwriting
│   │   └── file_copy.py             Safe file copy with parent directory creation
│   └── gui/                         PyQt5 interface
│       ├── main_window.py           Main window, tab container, status bar
│       ├── precheck_tab.py          Profile selector, Run Check, results, Apply Profile
│       ├── update_tab.py            Sync Now, live log, error display
│       ├── settings_tab.py          Edit and save app_settings.yaml from the UI
│       ├── diagnostics_tab.py       Adapter list, admin/git/server status, bundle manifest
│       └── widgets.py               Shared status badges and UI helpers
├── config/
│   └── app_settings.yaml            All application settings (server IP, paths, features, sources)
├── data/
│   ├── config_bundle/               Active offline configuration bundle
│   │   ├── bundle_manifest.yaml     Bundle version, source commits, available profiles
│   │   ├── profiles/                One YAML file per operational profile
│   │   ├── mission_planner/         Expected Mission Planner XML files, organized by profile
│   │   ├── external_configs/        Expected external config files, organized by profile
│   │   └── checksums/sha256_manifest.yaml
│   └── sources/                     Raw copies from GitLab/SMB (not used directly for checks)
│       ├── gitlab/
│       └── smb/
├── backups/                         Timestamped backups created before Apply Profile
├── build.spec                       PyInstaller build configuration
├── run.bat                          Launch script for the packaged .exe
└── requirements.txt
```

## Quick start (development)

```bash
# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

## Build for Windows

```bash
pip install pyinstaller
pyinstaller build.spec
```

Distribute these files together:
```
dist/GroundStationPrecheck.exe
config/app_settings.yaml
data/config_bundle/          ← the active bundle; update this, not the .exe
run.bat
```

The `.exe` contains application code. The `data/config_bundle/` directory contains the operational configuration. They version independently — updating configuration never requires rebuilding the executable.

## Detailed usage guide

See [USAGE.md](USAGE.md) for step-by-step instructions for every workflow.
