# Usage Guide — Ground Station Precheck Manager

This guide covers every workflow in the application: daily precheck, applying configuration, syncing from the server, adding profiles, and building the executable.

---

## Table of contents

1. [Daily precheck workflow](#1-daily-precheck-workflow)
2. [Apply Profile — fix a mismatch](#2-apply-profile--fix-a-mismatch)
3. [Sync from the configuration server](#3-sync-from-the-configuration-server)
4. [Diagnostics tab](#4-diagnostics-tab)
5. [Settings tab](#5-settings-tab)
6. [Adding or editing a profile](#6-adding-or-editing-a-profile)
7. [Adding files to the bundle](#7-adding-files-to-the-bundle)
8. [App settings reference](#8-app-settings-reference)
9. [Building the Windows executable](#9-building-the-windows-executable)
10. [Deploying a new bundle without rebuilding the exe](#10-deploying-a-new-bundle-without-rebuilding-the-exe)
11. [Understanding check results](#11-understanding-check-results)
12. [How the sync sequence works internally](#12-how-the-sync-sequence-works-internally)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Daily precheck workflow

This is the primary use case. No network connection is required.

**Steps:**

1. Launch `GroundStationPrecheck.exe` (or `python main.py` in development).
2. Open the **Precheck** tab (it is the default).
3. At the top you will see the bundle version and creation date. If it says *"not found"*, you must sync first — see [section 3](#3-sync-from-the-configuration-server).
4. Select the operational profile from the dropdown (e.g. **Plane - Field**).
5. Click **Run Check**.
6. Wait for results (the check runs in the background; the UI stays responsive).
7. Read the overall status banner and the per-check results below it.

**Overall status meanings:**

| Status | Meaning |
|--------|---------|
| `READY` | All checks passed. Safe to proceed. |
| `READY WITH WARNINGS` | No blocking failures, but something is non-ideal. Review warnings before flight. |
| `NOT READY` | At least one blocking check failed. Do not proceed until resolved. |

**Per-check result meanings:**

| Badge | Meaning |
|-------|---------|
| `PASS` | Check succeeded. |
| `FAIL` | Check failed. The row shows what was expected and what was found. |
| `WARNING` | Non-blocking issue. |
| `SKIPPED` | Check is not enabled or not applicable for this profile. |

**What is checked by default (Plane - Field profile):**

- **Main PC Interface** — adapter named `Ethernet` exists, is up, has IP `192.168.0.100/24`
- **USB Network Adapter** — adapter named `Ethernet 2` exists, is up, has IP `192.168.1.100/24`
- **Joystick XML** — `%USERPROFILE%\Documents\Mission Planner\joystick.xml` exists, is valid XML, SHA256 matches bundle baseline
- **Mission Planner Config** — same checks for `config.xml`
- **Camera Configuration** — optional; checked if the file and baseline both exist

---

## 2. Apply Profile — fix a mismatch

If a Mission Planner file check shows `FAIL` (wrong content or missing), use Apply Profile to restore it from the bundle.

**Steps:**

1. Run a check first (Apply Profile becomes active after a check).
2. Click **Apply Profile**.
3. A dialog shows exactly which files will be overwritten and their target paths. Review this list.
4. Click **Yes** to proceed.
5. The tool:
   - Creates a backup under `backups/<timestamp>/` for each file that already exists at the target path
   - Copies the baseline file from `data/config_bundle/` to the target path
6. A summary dialog shows what was applied and where the backup was saved.

**Backup location:** `backups/2026-05-10_1430/joystick.xml` — one folder per apply operation, named by date and time.

**When Apply Profile is not shown:** If the `enable_apply_profile` feature is disabled in settings, the button will be hidden.

---

## 3. Sync from the configuration server

Use this when the ground station computer is connected to the LAN with the configuration server at `192.168.1.1`. After sync the machine can go back offline — precheck always uses the local bundle.

**Pre-conditions:**
- The computer must be physically on the same LAN as the configuration server.
- The application must be running as **Administrator** (required to temporarily switch the network interface to DHCP). If not elevated, the Update Bundle tab will show a warning and a **Restart as Administrator** button.

**Steps:**

1. Open the **Update Bundle** tab.
2. Verify the displayed server IP (`192.168.1.1`) and sync interface name match your setup.
3. If a red administrator warning is shown, click **Restart as Administrator** and accept the UAC prompt.
4. Click **Sync Now**.
5. Watch the live log. The sequence is:
   - Snapshot current IP configuration of the sync interface
   - Switch the sync interface to DHCP
   - Wait for DHCP address assignment (up to 30 seconds)
   - Ping `192.168.1.1` to verify reachability
   - `git fetch` + `git reset --hard` for each GitLab repository
   - `robocopy /MIR` for each SMB share
   - Build a new normalized bundle in a temp directory
   - Validate the new bundle
   - Atomically replace `data/config_bundle/`
   - Restore the sync interface to its original static IP configuration
   - Report success or failure

6. If sync succeeds, the Precheck tab automatically reloads the profiles and bundle info.

**What happens if the server is not reachable:**
- The sync stops before touching any files.
- The interface is restored to its original IP.
- The existing bundle is completely untouched.
- The log shows: `Sync failed: configuration server 192.168.1.1 is not reachable.`

**What happens if the interface cannot be restored:**
- A high-severity error dialog appears showing the saved original configuration so you can restore it manually in Windows network settings.

**Validate Current Bundle button:** Runs a structural validation of the current `data/config_bundle/` without syncing. Use this to confirm the bundle is intact after manually copying files.

---

## 4. Diagnostics tab

A read-only inspection panel. Click **Refresh Diagnostics** to populate it.

| Section | What it shows |
|---------|--------------|
| Administrator | Whether the app is running elevated. Sync will require this. |
| Git executable | Whether `git` (or the configured path) is found on PATH. |
| Server reachable | Pings `192.168.1.1` and shows reachable / not reachable. |
| Network Interfaces table | All detected adapters with name, status, MAC, current IPv4, and description. |
| Bundle Manifest | Current bundle version, creation date, profile IDs, and GitLab source commits. |

Use the interface table to find the exact Windows adapter name when configuring a new profile. Copy the `Name` column value directly into the profile YAML `adapter_name` field.

---

## 5. Settings tab

Edit application settings through the UI without touching YAML files manually. Click **Save Settings** to write changes to `config/app_settings.yaml`.

| Field | Description |
|-------|-------------|
| Mission Planner Directory | Where Mission Planner stores its config files. Default: `%USERPROFILE%/Documents/Mission Planner`. Supports environment variables. |
| Config Bundle Directory | Where the active bundle lives. Default: `./data/config_bundle`. |
| Git Executable | Path to git. Default: `git` (must be on PATH). For portable git, enter the full path e.g. `C:\portable_git\bin\git.exe`. |
| Configuration Server IP | Default: `192.168.1.1`. |
| Sync Interface Name | The Windows adapter name used for DHCP switching during sync. Find it in the Diagnostics tab. |
| Enable Apply Profile | Show/hide the Apply Profile button. |
| Enable Backups Before Apply | Create timestamped backups before overwriting files. Strongly recommended. |
| Enable GitLab Sync | Include GitLab repositories in the sync operation. |
| Enable SMB Sync | Include SMB shares in the sync operation. |
| Temporarily Switch Interface to DHCP | Whether to switch the sync interface to DHCP before syncing. Disable only if the server is reachable on the existing static IP. |

**Note:** Changing paths (bundle directory, Mission Planner directory) takes effect on the next Run Check or Sync Now. The GitLab/SMB source URLs and paths are only editable directly in `config/app_settings.yaml` — the Settings tab covers the most commonly changed fields.

---

## 6. Adding or editing a profile

Profiles are YAML files in `data/config_bundle/profiles/`. The application loads all `.yaml` files in that directory on startup.

**Create a new profile:**

1. Copy an existing profile file, e.g.:
   ```
   data/config_bundle/profiles/plane_field.yaml  →  data/config_bundle/profiles/plane_lab.yaml
   ```

2. Edit the new file. Key sections:

   ```yaml
   profile:
     id: "plane_lab"                  # Must be unique. Used as identifier internally.
     display_name: "Plane - Lab"      # Shown in the dropdown.
     description: "Lab configuration."

   windows_interfaces:
     - id: "main_pc_interface"        # Internal ID, unique within this profile.
       display_name: "Main PC Interface"
       required: true                 # If false, failure becomes a WARNING not a FAIL.
       match_by:
         adapter_name: "Ethernet"     # Use exact Windows adapter name from Diagnostics tab.
         # mac_address: "AA-BB-CC-DD-EE-FF"  # Alternative — more stable for USB adapters.
         # description_contains: "USB"       # Fallback — least reliable.
       expected_ipv4:
         address: "192.168.10.200"
         prefix_length: 24

   mission_planner:
     base_path: "%USERPROFILE%/Documents/Mission Planner"
     files:
       - id: "joystick"
         display_name: "Joystick XML"
         target_path: "joystick.xml"                        # Relative to base_path.
         expected_file: "mission_planner/plane_lab/joystick.xml"  # Relative to bundle root.
         required: true
         type: "xml"
         checks:
           exists: true
           valid_xml: true
           sha256_match: true
         apply:
           enabled: true
           backup_before_replace: true

   external_files:
     - id: "camera_config"
       display_name: "Camera Configuration"
       target_path: "C:/Arc/Camera/config.json"   # Absolute path on the target machine.
       expected_file: "external_configs/camera/plane_lab/config.json"
       required: false                              # false = warning if missing, not fail.
       checks:
         exists: true
         sha256_match: true
       apply:
         enabled: true
         backup_before_replace: true
   ```

3. Place the expected files in the bundle at the paths referenced by `expected_file`:
   ```
   data/config_bundle/mission_planner/plane_lab/joystick.xml
   data/config_bundle/mission_planner/plane_lab/config.xml
   data/config_bundle/external_configs/camera/plane_lab/config.json
   ```

4. Regenerate the checksum manifest so SHA256 checks work:
   ```bash
   python -c "
   from app.update.checksum_manifest import write_checksum_manifest
   from pathlib import Path
   write_checksum_manifest(Path('data/config_bundle'))
   print('Done')
   "
   ```

5. Restart the application — the new profile appears in the dropdown.

**Interface matching priority** (the tool tries these in order):
1. `mac_address` — most stable; use for USB adapters that may get renamed
2. `adapter_name` — use for fixed adapters with a predictable name
3. `description_contains` — least reliable, use only as fallback

---

## 7. Adding files to the bundle

To add a new file that the precheck should validate:

1. Place the expected (baseline) file in the bundle:
   ```
   data/config_bundle/external_configs/<category>/<profile_id>/filename.ext
   ```

2. Add the file spec to the relevant profile YAML under `external_files` (or `mission_planner.files` for Mission Planner files).

3. Regenerate checksums:
   ```bash
   python -c "
   from app.update.checksum_manifest import write_checksum_manifest
   from pathlib import Path
   write_checksum_manifest(Path('data/config_bundle'))
   "
   ```

4. Update `data/config_bundle/bundle_manifest.yaml` — bump the `version` field so the UI reflects the change:
   ```yaml
   bundle:
     version: "2026.05.10-002"
   ```

5. Restart the application.

---

## 8. App settings reference

Full annotated `config/app_settings.yaml`:

```yaml
app:
  name: "Ground Station Precheck Manager"
  version: "1.0.0"

paths:
  data_dir: "./data"
  config_bundle_dir: "./data/config_bundle"    # Active bundle used for all checks.
  sources_dir: "./data/sources"                # Raw GitLab/SMB copies. Not used for checks.
  mission_planner_dir: "%USERPROFILE%/Documents/Mission Planner"  # Supports env vars.
  backup_dir: "./backups"

features:
  enable_apply_profile: true       # Show Apply Profile button.
  enable_backups: true             # Create backups before Apply Profile.
  enable_gitlab_sync: true         # Include git repos in Sync Now.
  enable_smb_sync: true            # Include SMB shares in Sync Now.

sync:
  server_ip: "192.168.1.1"
  require_server_reachable_before_sync: true
  temporarily_switch_interface_to_dhcp: true   # Set false only if server is reachable on static IP.
  restore_interface_after_sync: true
  server_reachability_timeout_seconds: 10
  dhcp_wait_timeout_seconds: 30

tools:
  git_executable: "git"            # Or full path to portable git.

sources:
  gitlab:
    enabled: true
    repositories:
      - name: "mission-configs"    # Used as the local folder name under data/sources/gitlab/.
        url: "http://192.168.1.1/group/mission-configs.git"
        branch: "main"
        local_path: "./data/sources/gitlab/mission-configs"   # Where git clone puts files.

      - name: "network-configs"
        url: "http://192.168.1.1/group/network-configs.git"
        branch: "main"
        local_path: "./data/sources/gitlab/network-configs"

  smb:
    enabled: true
    shares:
      - name: "ground-station-configs"
        source_path: "\\\\192.168.1.1\\GroundStationConfigs"  # UNC path to SMB share.
        local_path: "./data/sources/smb/ground-station-configs"

network:
  sync_interface:
    match_by:
      adapter_name: "Ethernet"     # Windows adapter name used for DHCP switching during sync.
```

---

## 9. Building the Windows executable

Run on a Windows machine with Python 3.10 installed:

```bat
pip install -r requirements.txt
pip install pyinstaller
pyinstaller build.spec
```

The output is `dist/GroundStationPrecheck.exe`.

**What to distribute:**

```
GroundStationPrecheck.exe
config\app_settings.yaml
data\config_bundle\        (the active bundle)
run.bat
```

`data\sources\` and `backups\` are generated at runtime — do not need to be pre-distributed.

**Portable Git:** If the target machine does not have Git installed, include a portable git and set the `tools.git_executable` path in `app_settings.yaml`:
```yaml
tools:
  git_executable: "./portable_git/bin/git.exe"
```

---

## 10. Deploying a new bundle without rebuilding the exe

The bundle (`data/config_bundle/`) is separate from the executable. To update configuration on deployed machines:

1. Run a sync on one machine (Sync Now from the Update Bundle tab).
2. Copy the updated `data/config_bundle/` directory to other machines.
3. No reboot or restart required — next time the operator clicks Run Check, the new bundle is used.

Alternatively, if GitLab/SMB sync is available on all machines, each machine can sync independently.

---

## 11. Understanding check results

Every result row shows:

- **Badge** — PASS / FAIL / WARNING / SKIPPED
- **Title** — what was checked (e.g. "Joystick XML — SHA256 Mismatch")
- **Expected** — what the tool expected to find
- **Actual** — what was actually found
- **Details** — additional context when the check fails

**Example FAIL output for an interface:**
```
[FAIL] USB Network Adapter — IPv4 Mismatch
  Expected: 192.168.1.100/24
  Actual:   169.254.12.33/16
```
This means the adapter was found and is up, but Windows assigned an APIPA address instead of the configured static IP. Fix: open Windows network settings and set the static IP manually, or Apply Profile if the profile includes a network apply action.

**Example FAIL output for a file:**
```
[FAIL] Joystick XML — SHA256 Mismatch
  Expected: 84e4f6056450…
  Actual:   a1b2c3d4e5f6…
```
The file exists and is valid XML, but its content differs from the baseline. Fix: click Apply Profile to restore it from the bundle.

---

## 12. How the sync sequence works internally

Understanding this helps when diagnosing sync failures.

```
User clicks Sync Now
  │
  ├─ Check: is the app running as Administrator?
  │    No  → show error, do not proceed
  │
  ├─ Find the sync adapter by name/MAC
  │
  ├─ SNAPSHOT current adapter state
  │    (IP, subnet, gateway, DNS, DHCP/static)
  │
  ├─ SWITCH adapter to DHCP
  │
  ├─ WAIT for DHCP address (non-APIPA)
  │    Timeout → RESTORE adapter → show error
  │
  ├─ PING 192.168.1.1
  │    Unreachable → RESTORE adapter → show error
  │                  (bundle untouched)
  │
  ├─ GIT SYNC (foreach repo):
  │    if local repo exists → git fetch + reset --hard + clean
  │    if not              → git clone
  │    capture HEAD commit hash
  │
  ├─ SMB SYNC (foreach share):
  │    robocopy /MIR → data/sources/smb/<name>/
  │
  ├─ BUILD BUNDLE (in temp directory):
  │    copy profiles from existing bundle
  │    integrate GitLab source files (mission_planner/, external_configs/, profiles/)
  │    integrate SMB source files
  │    write bundle_manifest.yaml (with commit hashes)
  │    write checksums/sha256_manifest.yaml
  │    validate bundle structure and YAML
  │
  ├─ ATOMIC REPLACE:
  │    rename data/config_bundle → data/config_bundle.old
  │    copy temp bundle → data/config_bundle
  │    delete data/config_bundle.old
  │
  ├─ RESTORE adapter to snapshotted state
  │    Failure → show high-severity error with saved config for manual restore
  │
  └─ Show final result; Precheck tab reloads
```

The key invariant: **`data/config_bundle/` is only replaced after the new bundle has been fully built and validated.** If anything fails before the atomic replace step, the existing bundle is completely intact.

---

## 13. Troubleshooting

**"Bundle: not found" in the Precheck tab**
→ The `data/config_bundle/bundle_manifest.yaml` file is missing. Either sync from the server (section 3) or manually copy a bundle into `data/config_bundle/`.

**Profile dropdown is empty**
→ No `.yaml` files found in `data/config_bundle/profiles/`. Check that the bundle is present and the `config_bundle_dir` path in settings is correct.

**"Administrator privileges are required" warning in Update Bundle**
→ Right-click the .exe or shortcut → Run as administrator. Or click **Restart as Administrator** in the Update Bundle tab.

**Git not found during sync**
→ Either install Git and ensure it is on PATH, or use portable Git and set `tools.git_executable` in `app_settings.yaml` to the full path.

**DHCP timeout during sync**
→ The adapter did not get a DHCP address within 30 seconds. Increase `sync.dhcp_wait_timeout_seconds` in settings, or check that the server's DHCP service is running.

**Sync succeeds but bundle validation fails**
→ The GitLab repository structure does not match what the bundle builder expects (it looks for `mission_planner/`, `external_configs/`, and `profiles/` subdirectories). Check the repository layout and adjust the bundle builder or the repository structure accordingly.

**SHA256 check fails after manually editing a file in the bundle**
→ Regenerate the checksum manifest:
```bash
python -c "
from app.update.checksum_manifest import write_checksum_manifest
from pathlib import Path
write_checksum_manifest(Path('data/config_bundle'))
print('Checksums updated')
"
```

**Check results show all FAIL for Mission Planner files (running on macOS/Linux for development)**
→ Expected. On non-Windows, the Mission Planner directory does not exist. Interface checks use mock data. Deploy to Windows for production validation.
