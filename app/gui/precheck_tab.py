from __future__ import annotations
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QScrollArea, QFrame, QMessageBox, QGroupBox, QGridLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from app.core.models import Profile, CheckResult, CheckStatus, OverallStatus, PrecheckReport
from app.core.paths import AppPaths
from app.core.config_loader import AppSettings
from app.core.profile_loader import load_all_profiles
from app.core.bundle import load_bundle_manifest
from app.core.result import group_by_category, calculate_overall_status
from app.checks.windows_interfaces import run_interface_checks
from app.checks.mission_planner_files import run_mission_planner_checks
from app.checks.external_files import run_external_file_checks
from app.actions.apply_profile import apply_profile, preview_apply
from app.gui.widgets import status_badge, overall_status_label, section_header, horizontal_line


class PrecheckWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, profile: Profile, bundle_dir: Path):
        super().__init__()
        self.profile = profile
        self.bundle_dir = bundle_dir

    def run(self):
        try:
            results = []
            results.extend(run_interface_checks(self.profile))
            results.extend(run_mission_planner_checks(self.profile, self.bundle_dir))
            results.extend(run_external_file_checks(self.profile, self.bundle_dir))
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class ResultRow(QFrame):
    def __init__(self, result: CheckResult, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("QFrame { border: 1px solid #e0e0e0; border-radius: 3px; margin: 1px; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        badge = status_badge(result.status)
        layout.addWidget(badge)

        info = QVBoxLayout()
        title = QLabel(result.title)
        title.setStyleSheet("font-weight: bold; border: none;")
        info.addWidget(title)

        if result.expected or result.actual:
            row = QHBoxLayout()
            if result.expected:
                row.addWidget(QLabel(f"Expected: {result.expected}"))
            if result.actual:
                row.addWidget(QLabel(f"Actual: {result.actual}"))
            row.addStretch()
            info.addLayout(row)

        if result.details:
            det = QLabel(result.details)
            det.setStyleSheet("color: #555; font-size: 11px; border: none;")
            det.setWordWrap(True)
            info.addWidget(det)

        layout.addLayout(info)
        layout.addStretch()


class PrecheckTab(QWidget):
    def __init__(self, paths: AppPaths, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.settings = settings
        self.profiles: list[Profile] = []
        self.current_results: list[CheckResult] = []
        self._worker: Optional[PrecheckWorker] = None
        self._setup_ui()
        self._load_profiles()

    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setSpacing(8)
        main.setContentsMargins(12, 12, 12, 12)

        # Header info
        info_layout = QHBoxLayout()
        self._bundle_label = QLabel("Bundle: —")
        self._bundle_label.setStyleSheet("color: #555;")
        info_layout.addWidget(self._bundle_label)
        info_layout.addStretch()
        main.addLayout(info_layout)
        main.addWidget(horizontal_line())

        # Profile selection row
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Profile:"))
        self._profile_combo = QComboBox()
        self._profile_combo.setMinimumWidth(200)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        profile_row.addWidget(self._profile_combo)
        profile_row.addStretch()

        self._check_btn = QPushButton("Run Check")
        self._check_btn.setFixedWidth(120)
        self._check_btn.clicked.connect(self._run_check)
        self._check_btn.setStyleSheet("QPushButton { background-color: #1565c0; color: white; "
                                       "padding: 6px; border-radius: 4px; font-weight: bold; }"
                                       "QPushButton:hover { background-color: #1976d2; }"
                                       "QPushButton:disabled { background-color: #bdbdbd; }")
        profile_row.addWidget(self._check_btn)

        self._apply_btn = QPushButton("Apply Profile")
        self._apply_btn.setFixedWidth(130)
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._apply_profile)
        self._apply_btn.setStyleSheet("QPushButton { background-color: #2e7d32; color: white; "
                                       "padding: 6px; border-radius: 4px; font-weight: bold; }"
                                       "QPushButton:hover { background-color: #388e3c; }"
                                       "QPushButton:disabled { background-color: #bdbdbd; }")
        profile_row.addWidget(self._apply_btn)
        main.addLayout(profile_row)
        main.addWidget(horizontal_line())

        # Overall status
        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Overall Status:"))
        self._status_label = QLabel("—")
        self._status_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px 12px;")
        status_row.addWidget(self._status_label)
        status_row.addStretch()
        main.addLayout(status_row)

        # Results scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._results_container = QWidget()
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setSpacing(4)
        self._results_layout.addStretch()
        scroll.setWidget(self._results_container)
        main.addWidget(scroll, 1)

        self._update_bundle_info()

    def _update_bundle_info(self):
        manifest = load_bundle_manifest(self.paths.config_bundle_dir)
        if manifest:
            validity = "OK" if manifest.is_valid else "INVALID"
            self._bundle_label.setText(
                f"Bundle: v{manifest.version}  |  Created: {manifest.created_at}  |  Status: {validity}"
            )
        else:
            self._bundle_label.setText("Bundle: not found — run sync to download configuration")

    def _load_profiles(self):
        self.profiles = load_all_profiles(self.paths.config_bundle_dir / "profiles")
        self._profile_combo.clear()
        for p in self.profiles:
            self._profile_combo.addItem(p.display_name, p)
        self._check_btn.setEnabled(len(self.profiles) > 0)

    def _on_profile_changed(self, _):
        self._clear_results()
        self._apply_btn.setEnabled(False)

    def _current_profile(self) -> Optional[Profile]:
        idx = self._profile_combo.currentIndex()
        if idx < 0 or idx >= len(self.profiles):
            return None
        return self.profiles[idx]

    def _run_check(self):
        profile = self._current_profile()
        if not profile:
            return
        self._check_btn.setEnabled(False)
        self._apply_btn.setEnabled(False)
        self._clear_results()
        self._status_label.setText("Running…")

        self._worker = PrecheckWorker(profile, self.paths.config_bundle_dir)
        self._worker.finished.connect(self._on_check_done)
        self._worker.error.connect(self._on_check_error)
        self._worker.start()

    def _on_check_done(self, results: list[CheckResult]):
        self.current_results = results
        self._check_btn.setEnabled(True)
        self._apply_btn.setEnabled(self.settings.enable_apply_profile and len(results) > 0)
        self._render_results(results)

    def _on_check_error(self, msg: str):
        self._check_btn.setEnabled(True)
        self._status_label.setText("Error")
        QMessageBox.critical(self, "Check Error", f"An error occurred during the check:\n{msg}")

    def _render_results(self, results: list[CheckResult]):
        self._clear_results()
        if not results:
            self._status_label.setText("No results")
            return

        overall = calculate_overall_status(results)
        colors = {
            OverallStatus.READY: "#2e7d32",
            OverallStatus.READY_WITH_WARNINGS: "#e65100",
            OverallStatus.NOT_READY: "#c62828",
        }
        bg = {
            OverallStatus.READY: "#e8f5e9",
            OverallStatus.READY_WITH_WARNINGS: "#fff3e0",
            OverallStatus.NOT_READY: "#ffebee",
        }
        c = colors[overall]
        b = bg[overall]
        self._status_label.setText(overall.value)
        self._status_label.setStyleSheet(
            f"color: {c}; background-color: {b}; border: 2px solid {c}; "
            f"font-size: 14px; font-weight: bold; padding: 4px 16px; border-radius: 4px;"
        )

        categories = group_by_category(results)
        layout = self._results_layout
        # Remove stretch
        item = layout.takeAt(layout.count() - 1)

        for cat in categories:
            layout.addWidget(section_header(cat.name))
            for result in cat.results:
                layout.addWidget(ResultRow(result))

        layout.addStretch()

    def _clear_results(self):
        layout = self._results_layout
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._status_label.setText("—")
        self._status_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px 12px;")

    def _apply_profile(self):
        profile = self._current_profile()
        if not profile:
            return

        preview = preview_apply(profile, self.paths.config_bundle_dir)
        if not preview:
            QMessageBox.information(self, "Apply Profile", "No files to apply for this profile.")
            return

        file_list = "\n".join(f"  • {item.display_name}: {item.dst}" for item in preview)
        reply = QMessageBox.question(
            self, "Apply Profile",
            f"The following files will be replaced:\n\n{file_list}\n\n"
            f"{'Backups will be created before replacement.' if self.settings.enable_backups else 'No backups configured.'}\n\n"
            f"Proceed?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        result = apply_profile(profile, self.paths.config_bundle_dir, self.paths.backup_dir)
        if result.success:
            msg = "Profile applied successfully.\n\nApplied:\n" + "\n".join(f"  • {f}" for f in result.applied)
            if result.backup_dir:
                msg += f"\n\nBackup saved to: {result.backup_dir}"
            QMessageBox.information(self, "Apply Profile", msg)
        else:
            msg = "Apply completed with errors.\n"
            if result.applied:
                msg += "\nApplied:\n" + "\n".join(f"  • {f}" for f in result.applied)
            if result.errors:
                msg += "\n\nErrors:\n" + "\n".join(f"  • {e}" for e in result.errors)
            QMessageBox.warning(self, "Apply Profile", msg)

    def refresh(self):
        self._load_profiles()
        self._update_bundle_info()
