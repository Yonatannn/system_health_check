import sys
import os

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from app.core.paths import AppPaths
from app.core.config_loader import load_app_settings
from app.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Ground Station Precheck Manager")
    app.setOrganizationName("GroundStation")

    paths = AppPaths()
    settings = load_app_settings(paths.config_dir / "app_settings.yaml")

    window = MainWindow(paths, settings)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
