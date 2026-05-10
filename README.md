# Ground Station Precheck Manager

Windows-only desktop application for pre-use validation and configuration sync of a ground station computer.

## Requirements

- Windows 10/11
- Python 3.10 (development only)
- Git (for sync; can be portable)

## Development Setup

```bash
pip install -r requirements.txt
python main.py
```

## Build (Windows)

```bash
pip install pyinstaller
pyinstaller build.spec
```

Distribute the `dist/GroundStationPrecheck.exe` alongside:
```
GroundStationPrecheck.exe
config/app_settings.yaml
data/config_bundle/
run.bat
```

## Project Structure

```
ground_station_precheck/
├── main.py                        Entry point
├── app/
│   ├── gui/                       PyQt5 UI (main_window, precheck_tab, update_tab, settings_tab, diagnostics_tab)
│   ├── core/                      Data models, loaders, paths
│   ├── checks/                    Validation logic (interfaces, files, XML)
│   ├── update/                    Sync (GitLab, SMB, bundle builder, checksums)
│   ├── actions/                   Apply profile, backup, file copy
│   └── windows/                   Windows/PowerShell integration (admin, adapters, DHCP)
├── config/app_settings.yaml       Application settings
├── data/
│   ├── config_bundle/             Active configuration bundle (offline source of truth)
│   │   ├── bundle_manifest.yaml
│   │   ├── profiles/              Operational profiles (plane_field, copter_field, …)
│   │   ├── mission_planner/       Expected Mission Planner XML files per profile
│   │   ├── external_configs/      Other expected config files
│   │   └── checksums/             SHA256 manifest
│   └── sources/                   Raw copies from GitLab/SMB (used to build bundle)
├── backups/                       Automatic backups before Apply Profile
├── build.spec                     PyInstaller spec
└── requirements.txt
```

## Operating Modes

**Offline Precheck (normal):** Select a profile → Run Check → review results → optionally Apply Profile. No network required.

**Online/LAN Sync:** Connect to `192.168.1.1` → click Sync Now on the Update Bundle tab. Temporarily switches the configured interface to DHCP, pulls GitLab repos and SMB shares, builds a new config bundle, then restores the original IP configuration.

## Configuration

Edit `config/app_settings.yaml` to configure:
- Server IP (default `192.168.1.1`)
- Sync network interface name
- GitLab repository URLs and branches
- SMB share paths
- Paths for Mission Planner and backups

## Profiles

Profiles live in `data/config_bundle/profiles/*.yaml`. Each profile defines:
- Which Windows network interfaces to check (name/MAC matching + expected IP/subnet)
- Which Mission Planner files to validate (exists, XML valid, SHA256 match)
- Which external config files to validate

## MVP Roadmap

| Version | Features |
|---------|----------|
| v0.1 | GUI, profile selection, interface checks, Mission Planner file checks, Apply Profile |
| v0.2 | SMB sync, bundle build, manifest, checksum manifest |
| v0.3 | GitLab sync, commit hash in manifest |
| v0.4 | DHCP switching, IP restore, Admin detection, Diagnostics tab |
