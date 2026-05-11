from __future__ import annotations
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QGroupBox, QMessageBox, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from app.core.paths import AppPaths
from app.core.config_loader import AppSettings
from app.core.bundle import load_bundle_manifest, validate_bundle
from app.core.profile_loader import load_all_profiles
from app.update.sync_manager import SyncManager, SyncReport
from app.windows.admin import is_admin, restart_as_admin
from app.gui.widgets import section_header, horizontal_line


class SyncWorker(QThread):
    log_message = pyqtSignal(str)
    finished = pyqtSignal(object)

    def __init__(self, paths: AppPaths, settings: AppSettings):
        super().__init__()
        self.paths = paths
        self.settings = settings

    def run(self):
        manager = SyncManager(self.paths, self.settings, log=self.log_message.emit)
        report = manager.run_sync()
        self.finished.emit(report)


class UpdateTab(QWidget):
    sync_completed = pyqtSignal()

    def __init__(self, paths: AppPaths, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.settings = settings
        self._worker: Optional[SyncWorker] = None
        self._setup_ui()

    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setSpacing(10)
        main.setContentsMargins(12, 12, 12, 12)

        # Server / sources info
        info_group = QGroupBox("Sync Configuration")
        info_layout = QVBoxLayout(info_group)

        server_row = QHBoxLayout()
        server_row.addWidget(QLabel("Configuration Server:"))
        self._server_label = QLabel(self.settings.server_ip)
        self._server_label.setStyleSheet("font-weight: bold; color: #1565c0;")
        server_row.addWidget(self._server_label)
        server_row.addStretch()
        info_layout.addLayout(server_row)

        iface_row = QHBoxLayout()
        iface_row.addWidget(QLabel("Sync Interface:"))
        iface_match = self.settings.sync_interface_match
        iface_text = iface_match.get("adapter_name") or iface_match.get("mac_address") or "not configured"
        self._iface_label = QLabel(iface_text)
        self._iface_label.setStyleSheet("font-weight: bold;")
        iface_row.addWidget(self._iface_label)
        iface_row.addStretch()
        info_layout.addLayout(iface_row)

        # GitLab repos from profiles
        self._repos_layout = info_layout
        self._populate_repos()

        main.addWidget(info_group)

        # Admin warning
        self._admin_warning = QLabel()
        self._admin_warning.setStyleSheet("color: #c62828; background-color: #ffebee; "
                                           "padding: 6px; border-radius: 4px;")
        self._admin_warning.setWordWrap(True)
        self._admin_warning.hide()
        main.addWidget(self._admin_warning)

        self._restart_admin_btn = QPushButton("Restart as Administrator")
        self._restart_admin_btn.clicked.connect(restart_as_admin)
        self._restart_admin_btn.setStyleSheet("QPushButton { background-color: #e65100; color: white; "
                                               "padding: 6px; border-radius: 4px; font-weight: bold; }"
                                               "QPushButton:hover { background-color: #f57c00; }")
        self._restart_admin_btn.hide()
        main.addWidget(self._restart_admin_btn)

        self._check_admin_status()

        # Action buttons
        btn_row = QHBoxLayout()
        self._sync_btn = QPushButton("Sync Now")
        self._sync_btn.setFixedHeight(36)
        self._sync_btn.setStyleSheet("QPushButton { background-color: #1565c0; color: white; "
                                      "padding: 6px 20px; border-radius: 4px; font-weight: bold; font-size: 13px; }"
                                      "QPushButton:hover { background-color: #1976d2; }"
                                      "QPushButton:disabled { background-color: #bdbdbd; }")
        self._sync_btn.clicked.connect(self._start_sync)
        btn_row.addWidget(self._sync_btn)

        self._validate_btn = QPushButton("Validate Current Bundle")
        self._validate_btn.setFixedHeight(36)
        self._validate_btn.setStyleSheet("QPushButton { background-color: #37474f; color: white; "
                                          "padding: 6px 20px; border-radius: 4px; font-weight: bold; }"
                                          "QPushButton:hover { background-color: #455a64; }")
        self._validate_btn.clicked.connect(self._validate_bundle)
        btn_row.addWidget(self._validate_btn)
        btn_row.addStretch()
        main.addLayout(btn_row)

        main.addWidget(horizontal_line())

        # Log output
        main.addWidget(section_header("Sync Log"))
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Consolas", 9))
        self._log.setStyleSheet("background-color: #fafafa; border: 1px solid #e0e0e0;")
        main.addWidget(self._log, 1)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        main.addWidget(self._status_label)

    def _check_admin_status(self):
        if self.settings.temporarily_switch_to_dhcp and not is_admin():
            self._admin_warning.setText(
                "Administrator privileges are required to temporarily switch "
                "the network interface to DHCP for sync."
            )
            self._admin_warning.show()
            self._restart_admin_btn.show()
        else:
            self._admin_warning.hide()
            self._restart_admin_btn.hide()

    def _start_sync(self):
        self._sync_btn.setEnabled(False)
        self._validate_btn.setEnabled(False)
        self._log.clear()
        self._status_label.setText("")

        self._worker = SyncWorker(self.paths, self.settings)
        self._worker.log_message.connect(self._append_log)
        self._worker.finished.connect(self._on_sync_done)
        self._worker.start()

    def _append_log(self, msg: str):
        self._log.appendPlainText(msg)

    def _on_sync_done(self, report: SyncReport):
        self._sync_btn.setEnabled(True)
        self._validate_btn.setEnabled(True)

        for msg in report.messages:
            self._append_log(msg)

        if report.success:
            self._status_label.setText("Sync completed successfully.")
            self._status_label.setStyleSheet("color: #2e7d32; font-weight: bold; padding: 4px;")
            self.sync_completed.emit()
        else:
            self._status_label.setText(report.error or "Sync failed.")
            self._status_label.setStyleSheet("color: #c62828; font-weight: bold; padding: 4px;")

            if not report.interface_restored:
                QMessageBox.critical(
                    self, "Network Interface Error",
                    "The network interface could not be restored to its original configuration.\n\n"
                    "Please manually restore your network settings."
                )

    def _validate_bundle(self):
        ok, err = validate_bundle(self.paths.config_bundle_dir)
        if ok:
            QMessageBox.information(self, "Bundle Validation", "Current bundle is valid.")
        else:
            QMessageBox.warning(self, "Bundle Validation", f"Bundle validation failed:\n{err}")

    def _populate_repos(self):
        profiles = load_all_profiles(self.paths.profiles_dir)
        repos = [p.source_repo for p in profiles if p.source_repo]
        if repos:
            self._repos_layout.addWidget(QLabel("GitLab Repositories:"))
            for r in repos:
                self._repos_layout.addWidget(QLabel(f"  • {r.name} — {r.url}"))

    def refresh(self):
        self._server_label.setText(self.settings.server_ip)
        iface_match = self.settings.sync_interface_match
        iface_text = iface_match.get("adapter_name") or iface_match.get("mac_address") or "not configured"
        self._iface_label.setText(iface_text)
        self._check_admin_status()
