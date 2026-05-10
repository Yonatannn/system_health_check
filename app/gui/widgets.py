from __future__ import annotations
from PyQt5.QtWidgets import QLabel, QFrame, QHBoxLayout, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

from app.core.models import CheckStatus, OverallStatus

STATUS_COLORS = {
    CheckStatus.PASS: "#2e7d32",
    CheckStatus.WARNING: "#e65100",
    CheckStatus.FAIL: "#c62828",
    CheckStatus.SKIPPED: "#757575",
}

OVERALL_COLORS = {
    OverallStatus.READY: "#2e7d32",
    OverallStatus.READY_WITH_WARNINGS: "#e65100",
    OverallStatus.NOT_READY: "#c62828",
}

OVERALL_BG = {
    OverallStatus.READY: "#e8f5e9",
    OverallStatus.READY_WITH_WARNINGS: "#fff3e0",
    OverallStatus.NOT_READY: "#ffebee",
}


def status_badge(status: CheckStatus) -> QLabel:
    label = QLabel(status.value)
    color = STATUS_COLORS.get(status, "#757575")
    label.setStyleSheet(
        f"color: white; background-color: {color}; "
        f"padding: 2px 8px; border-radius: 3px; font-weight: bold; font-size: 11px;"
    )
    label.setAlignment(Qt.AlignCenter)
    label.setFixedWidth(80)
    return label


def overall_status_label(status: OverallStatus) -> QLabel:
    label = QLabel(f"  {status.value}  ")
    fg = OVERALL_COLORS.get(status, "#333333")
    bg = OVERALL_BG.get(status, "#f5f5f5")
    label.setStyleSheet(
        f"color: {fg}; background-color: {bg}; border: 2px solid {fg}; "
        f"padding: 6px 16px; border-radius: 4px; font-size: 14px; font-weight: bold;"
    )
    label.setAlignment(Qt.AlignCenter)
    return label


def section_header(text: str) -> QLabel:
    label = QLabel(text)
    font = label.font()
    font.setBold(True)
    font.setPointSize(10)
    label.setFont(font)
    label.setStyleSheet("color: #1565c0; padding-top: 4px; padding-bottom: 2px;")
    return label


def horizontal_line() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    return line
