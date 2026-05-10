from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QPlainTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from app.core.paths import AppPaths
from app.core.config_loader import AppSettings
from app.core.bundle import load_bundle_manifest
from app.windows.adapters import list_adapters
from app.windows.admin import is_admin
from app.windows.powershell import ping_host
from app.gui.widgets import section_header, horizontal_line
import shutil
import yaml


class DiagnosticsWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, settings: AppSettings):
        super().__init__()
        self.settings = settings

    def run(self):
        adapters = list_adapters()
        admin = is_admin()
        git_exe = self.settings.git_executable
        git_found = shutil.which(git_exe) is not None
        server_reachable = ping_host(self.settings.server_ip,
                                      timeout_seconds=self.settings.server_reachability_timeout)
        self.finished.emit({
            "adapters": adapters,
            "admin": admin,
            "git_found": git_found,
            "git_exe": git_exe,
            "server_reachable": server_reachable,
            "server_ip": self.settings.server_ip,
        })


class DiagnosticsTab(QWidget):
    def __init__(self, paths: AppPaths, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.settings = settings
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setSpacing(10)
        main.setContentsMargins(12, 12, 12, 12)

        refresh_btn = QPushButton("Refresh Diagnostics")
        refresh_btn.setStyleSheet("QPushButton { background-color: #37474f; color: white; "
                                   "padding: 6px 20px; border-radius: 4px; font-weight: bold; }"
                                   "QPushButton:hover { background-color: #455a64; }")
        refresh_btn.clicked.connect(self._run_diagnostics)
        main.addWidget(refresh_btn)

        # System checks group
        sys_group = QGroupBox("System Checks")
        sys_layout = QVBoxLayout(sys_group)
        self._admin_label = QLabel("Administrator: —")
        self._git_label = QLabel("Git executable: —")
        self._server_label = QLabel("Server reachable: —")
        sys_layout.addWidget(self._admin_label)
        sys_layout.addWidget(self._git_label)
        sys_layout.addWidget(self._server_label)
        main.addWidget(sys_group)

        # Network interfaces table
        main.addWidget(section_header("Network Interfaces"))
        self._adapter_table = QTableWidget(0, 5)
        self._adapter_table.setHorizontalHeaderLabels(
            ["Name", "Status", "MAC", "IPv4", "Description"]
        )
        self._adapter_table.horizontalHeader().setStretchLastSection(True)
        self._adapter_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._adapter_table.setSelectionBehavior(QTableWidget.SelectRows)
        main.addWidget(self._adapter_table)

        # Bundle manifest
        main.addWidget(section_header("Bundle Manifest"))
        self._manifest_text = QPlainTextEdit()
        self._manifest_text.setReadOnly(True)
        self._manifest_text.setFont(QFont("Consolas", 9))
        self._manifest_text.setMaximumHeight(200)
        self._load_manifest()
        main.addWidget(self._manifest_text)

    def _run_diagnostics(self):
        self._worker = DiagnosticsWorker(self.settings)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_done(self, info: dict):
        admin = info["admin"]
        self._admin_label.setText(
            f"Administrator: {'Yes ✓' if admin else 'No — limited functionality'}"
        )
        self._admin_label.setStyleSheet(
            "color: #2e7d32;" if admin else "color: #c62828;"
        )

        git_found = info["git_found"]
        self._git_label.setText(
            f"Git executable ({info['git_exe']}): {'Found ✓' if git_found else 'Not found ✗'}"
        )
        self._git_label.setStyleSheet(
            "color: #2e7d32;" if git_found else "color: #c62828;"
        )

        reachable = info["server_reachable"]
        self._server_label.setText(
            f"Server {info['server_ip']}: {'Reachable ✓' if reachable else 'Not reachable ✗'}"
        )
        self._server_label.setStyleSheet(
            "color: #2e7d32;" if reachable else "color: #c62828;"
        )

        adapters = info["adapters"]
        self._adapter_table.setRowCount(len(adapters))
        for row, a in enumerate(adapters):
            ipv4_str = ", ".join(f"{addr}/{pfx}" for addr, pfx in a.ipv4_addresses) or "—"
            for col, val in enumerate([a.name, a.status, a.mac, ipv4_str, a.description]):
                item = QTableWidgetItem(val or "")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self._adapter_table.setItem(row, col, item)

        self._load_manifest()

    def _load_manifest(self):
        from app.core.bundle import load_bundle_manifest
        manifest = load_bundle_manifest(self.paths.config_bundle_dir)
        if manifest:
            text = (f"Name: {manifest.name}\n"
                    f"Version: {manifest.version}\n"
                    f"Created: {manifest.created_at}\n"
                    f"Profiles: {', '.join(manifest.profile_ids)}\n"
                    f"Valid: {manifest.is_valid}")
            if manifest.gitlab_sources:
                text += "\n\nGitLab Sources:"
                for s in manifest.gitlab_sources:
                    text += f"\n  • {s.name}: {s.url} ({s.branch}) @ {s.commit or 'unknown'}"
        else:
            text = "No bundle manifest found."
        self._manifest_text.setPlainText(text)
