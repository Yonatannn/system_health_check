from __future__ import annotations
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QCheckBox, QGroupBox, QHBoxLayout, QFileDialog, QMessageBox, QLabel
)

from app.core.paths import AppPaths
from app.core.config_loader import AppSettings, load_app_settings, save_app_settings
from app.gui.widgets import section_header, horizontal_line


class SettingsTab(QWidget):
    def __init__(self, paths: AppPaths, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.settings = settings
        self._setup_ui()

    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setSpacing(10)
        main.setContentsMargins(12, 12, 12, 12)

        # Paths group
        paths_group = QGroupBox("Paths")
        paths_form = QFormLayout(paths_group)

        self._mp_dir = self._path_field(
            self.settings.mission_planner_dir or "%USERPROFILE%/Documents/Mission Planner"
        )
        paths_form.addRow("Mission Planner Directory:", self._mp_dir)

        self._bundle_dir = self._path_field(
            self.settings.config_bundle_dir or "./data/config_bundle"
        )
        paths_form.addRow("Config Bundle Directory:", self._bundle_dir)

        self._git_exe = QLineEdit(self.settings.git_executable)
        paths_form.addRow("Git Executable:", self._git_exe)

        main.addWidget(paths_group)

        # Sync group
        sync_group = QGroupBox("Sync")
        sync_form = QFormLayout(sync_group)

        self._server_ip = QLineEdit(self.settings.server_ip)
        sync_form.addRow("Configuration Server IP:", self._server_ip)

        iface_match = self.settings.sync_interface_match
        self._sync_iface = QLineEdit(iface_match.get("adapter_name", "Ethernet"))
        sync_form.addRow("Sync Interface Name:", self._sync_iface)

        main.addWidget(sync_group)

        # Features group
        feat_group = QGroupBox("Features")
        feat_layout = QVBoxLayout(feat_group)

        self._chk_apply = QCheckBox("Enable Apply Profile")
        self._chk_apply.setChecked(self.settings.enable_apply_profile)
        feat_layout.addWidget(self._chk_apply)

        self._chk_backups = QCheckBox("Enable Backups Before Apply")
        self._chk_backups.setChecked(self.settings.enable_backups)
        feat_layout.addWidget(self._chk_backups)

        self._chk_gitlab = QCheckBox("Enable GitLab Sync")
        self._chk_gitlab.setChecked(self.settings.enable_gitlab_sync)
        feat_layout.addWidget(self._chk_gitlab)

        self._chk_smb = QCheckBox("Enable SMB Sync")
        self._chk_smb.setChecked(self.settings.enable_smb_sync)
        feat_layout.addWidget(self._chk_smb)

        self._chk_dhcp = QCheckBox("Temporarily Switch Interface to DHCP for Sync")
        self._chk_dhcp.setChecked(self.settings.temporarily_switch_to_dhcp)
        feat_layout.addWidget(self._chk_dhcp)

        main.addWidget(feat_group)

        # Save button
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.setStyleSheet("QPushButton { background-color: #1565c0; color: white; "
                                "padding: 6px 20px; border-radius: 4px; font-weight: bold; }"
                                "QPushButton:hover { background-color: #1976d2; }")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        main.addLayout(btn_row)

        main.addStretch()

        note = QLabel("Note: Some settings require a restart to take effect.")
        note.setStyleSheet("color: #757575; font-size: 11px;")
        main.addWidget(note)

    def _path_field(self, value: str) -> QLineEdit:
        field = QLineEdit(value)
        return field

    def _save(self):
        settings_path = self.paths.config_dir / "app_settings.yaml"
        try:
            data = load_app_settings(settings_path).raw()
        except Exception:
            data = {}

        data.setdefault("paths", {})["mission_planner_dir"] = self._mp_dir.text()
        data.setdefault("paths", {})["config_bundle_dir"] = self._bundle_dir.text()
        data.setdefault("tools", {})["git_executable"] = self._git_exe.text()
        data.setdefault("sync", {})["server_ip"] = self._server_ip.text()
        data.setdefault("network", {}).setdefault("sync_interface", {}).setdefault("match_by", {})["adapter_name"] = self._sync_iface.text()
        data.setdefault("features", {})["enable_apply_profile"] = self._chk_apply.isChecked()
        data.setdefault("features", {})["enable_backups"] = self._chk_backups.isChecked()
        data.setdefault("features", {})["enable_gitlab_sync"] = self._chk_gitlab.isChecked()
        data.setdefault("features", {})["enable_smb_sync"] = self._chk_smb.isChecked()
        data.setdefault("sync", {})["temporarily_switch_interface_to_dhcp"] = self._chk_dhcp.isChecked()

        try:
            save_app_settings(settings_path, data)
            QMessageBox.information(self, "Settings", "Settings saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Settings", f"Failed to save settings:\n{e}")
