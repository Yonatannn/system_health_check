from __future__ import annotations
from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel, QWidget
)
from PyQt5.QtCore import Qt

from app.core.paths import AppPaths
from app.core.config_loader import AppSettings
from app.gui.precheck_tab import PrecheckTab
from app.gui.update_tab import UpdateTab
from app.gui.diagnostics_tab import DiagnosticsTab


class MainWindow(QMainWindow):
    def __init__(self, paths: AppPaths, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.settings = settings

        self.setWindowTitle(f"{settings.app_name}  v{settings.app_version}")
        self.resize(860, 620)
        self.setMinimumSize(700, 480)

        self._setup_ui()
        paths.ensure_dirs()

    def _setup_ui(self):
        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        self._precheck_tab = PrecheckTab(self.paths, self.settings)
        tabs.addTab(self._precheck_tab, "Precheck")

        self._update_tab = UpdateTab(self.paths, self.settings)
        self._update_tab.sync_completed.connect(self._on_sync_completed)
        tabs.addTab(self._update_tab, "Update Bundle")

        self._diagnostics_tab = DiagnosticsTab(self.paths, self.settings)
        tabs.addTab(self._diagnostics_tab, "Diagnostics")

        self.setCentralWidget(tabs)

        status_bar = QStatusBar()
        version_label = QLabel(f"App v{self.settings.app_version}")
        version_label.setStyleSheet("color: #757575; padding: 0 8px;")
        status_bar.addPermanentWidget(version_label)
        self.setStatusBar(status_bar)

        self.setStyleSheet("""
            QMainWindow { background-color: #fafafa; }
            QTabWidget::pane { border: 1px solid #e0e0e0; }
            QTabBar::tab { padding: 8px 32px; font-size: 12px; min-width: 100px; }
            QTabBar::tab:selected { color: #1565c0; border-bottom: 2px solid #1565c0; font-weight: bold; }
            QGroupBox { font-weight: bold; border: 1px solid #e0e0e0; border-radius: 4px; margin-top: 8px; padding-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
            QPushButton { border-radius: 4px; }
            QComboBox { padding: 4px; }
            QLineEdit { padding: 4px; border: 1px solid #bdbdbd; border-radius: 3px; }
        """)

    def _on_sync_completed(self):
        self._precheck_tab.refresh()
