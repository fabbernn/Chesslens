"""
User profile dialog — manage the usernames ChessLens recognises as "you".

A simple modal:
  * Read-only list of saved handles with a × on each row for removal
  * Text field + Add button at the bottom for new entries
  * Brief explainer at the top of what this does

Opened from the top-bar 👤 button.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
)

from app.services.user_profile import UserProfile
from app.ui.theme import COLORS, FONTS, SPACE


class UserProfileDialog(QDialog):
    """Edit the list of usernames ChessLens treats as the current user."""

    profile_changed = Signal()   # fired whenever the list changes

    def __init__(self, profile: UserProfile, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.profile = profile
        self.setWindowTitle("Your chess usernames")
        self.setMinimumWidth(440)
        self.setStyleSheet(
            f"QDialog {{ background-color: {COLORS.bg_panel}; }}"
            f"QLabel  {{ color: {COLORS.text}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACE.xl, SPACE.lg, SPACE.xl, SPACE.lg)
        outer.setSpacing(SPACE.md)

        # ── Header ─────────────────────────────────────────────────────────
        title = QLabel("Your chess usernames")
        title.setStyleSheet(
            f"color: {COLORS.text}; font-size: {FONTS.xl}pt; font-weight: 700;"
        )
        outer.addWidget(title)

        sub = QLabel(
            "Add the handles you play under (chess.com, lichess, OTB clubs). "
            "When you analyze a game, ChessLens recognises which side was you "
            "and can narrate only your moves."
        )
        sub.setStyleSheet(f"color: {COLORS.text_muted}; font-size: {FONTS.sm}pt;")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        outer.addWidget(self._divider())

        # ── Username list ──────────────────────────────────────────────────
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            f"QListWidget {{"
            f"  background-color: {COLORS.bg_input};"
            f"  color: {COLORS.text};"
            f"  border: 1px solid {COLORS.border_subtle};"
            f"  border-radius: 5px;"
            f"  padding: 4px;"
            f"  font-size: {FONTS.md}pt;"
            f"}}"
            f"QListWidget::item {{ padding: 0; border-radius: 3px; }}"
            f"QListWidget::item:hover {{ background-color: {COLORS.bg_card}; }}"
        )
        self.list_widget.setMinimumHeight(160)
        outer.addWidget(self.list_widget)

        # ── Add row ────────────────────────────────────────────────────────
        add_row = QHBoxLayout()
        add_row.setSpacing(SPACE.sm)

        self.input = QLineEdit()
        self.input.setPlaceholderText("e.g. hikaru, yourname")
        self.input.setStyleSheet(
            f"QLineEdit {{"
            f"  background-color: {COLORS.bg_input};"
            f"  color: {COLORS.text};"
            f"  border: 1px solid {COLORS.border_subtle};"
            f"  border-radius: 5px;"
            f"  padding: 7px 10px;"
            f"  font-size: {FONTS.md}pt;"
            f"}}"
            f"QLineEdit:focus {{ border-color: {COLORS.border_focus}; }}"
        )
        self.input.returnPressed.connect(self._on_add_clicked)
        add_row.addWidget(self.input, 1)

        self.add_btn = QPushButton("Add")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setMinimumHeight(34)
        self.add_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {COLORS.accent};"
            f"  color: {COLORS.on_accent};"
            f"  border: none;"
            f"  border-radius: 5px;"
            f"  padding: 7px 18px;"
            f"  font-size: {FONTS.md}pt;"
            f"  font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{ background-color: {COLORS.accent_hover}; }}"
            f"QPushButton:disabled {{ background-color: {COLORS.bg_card};"
            f"  color: {COLORS.text_dim}; }}"
        )
        self.add_btn.clicked.connect(self._on_add_clicked)
        add_row.addWidget(self.add_btn)

        outer.addLayout(add_row)

        outer.addWidget(self._divider())

        # ── Close ──────────────────────────────────────────────────────────
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        done_btn = QPushButton("Done")
        done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        done_btn.setMinimumHeight(36)
        done_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {COLORS.accent};"
            f"  color: {COLORS.on_accent};"
            f"  border: none;"
            f"  border-radius: 5px;"
            f"  padding: 8px 22px;"
            f"  font-size: {FONTS.md}pt;"
            f"  font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{ background-color: {COLORS.accent_hover}; }}"
        )
        done_btn.clicked.connect(self.accept)
        close_row.addWidget(done_btn)
        outer.addLayout(close_row)

        self._refresh_list()

    # ─────────────────────────────────────────────────────────────────────
    def _divider(self) -> QFrame:
        d = QFrame()
        d.setFixedHeight(1)
        d.setStyleSheet(f"background-color: {COLORS.border_subtle};")
        return d

    def _refresh_list(self) -> None:
        """Rebuild the list widget from the current profile state."""
        self.list_widget.clear()
        if not self.profile.usernames:
            placeholder = QListWidgetItem("(no usernames yet — add one below)")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(Qt.GlobalColor.gray)
            self.list_widget.addItem(placeholder)
            return
        for name in self.profile.usernames:
            self._add_row(name)

    def _add_row(self, name: str) -> None:
        """Render one username row with a × remove button."""
        item = QListWidgetItem()
        widget = QWidget()
        widget.setStyleSheet("background-color: transparent;")
        h = QHBoxLayout(widget)
        h.setContentsMargins(8, 4, 6, 4)
        h.setSpacing(SPACE.sm)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {COLORS.text}; font-size: {FONTS.md}pt; font-weight: 500;"
            f"background-color: transparent;"
        )
        h.addWidget(name_lbl, 1)

        rm = QPushButton("×")
        rm.setFixedSize(22, 22)
        rm.setCursor(Qt.CursorShape.PointingHandCursor)
        rm.setToolTip(f"Remove “{name}”")
        rm.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: transparent;"
            f"  color: {COLORS.text_dim};"
            f"  border: none;"
            f"  font-size: 16pt;"
            f"  font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{ color: {COLORS.danger}; }}"
        )
        rm.clicked.connect(lambda _, n=name: self._on_remove(n))
        h.addWidget(rm)

        item.setSizeHint(widget.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)

    # ── Slot handlers ─────────────────────────────────────────────────────
    def _on_add_clicked(self) -> None:
        name = self.input.text().strip()
        if not name:
            return
        if self.profile.add(name):
            self.input.clear()
            self._refresh_list()
            self.profile_changed.emit()
        else:
            # Already exists — just clear the input, no error needed
            self.input.clear()

    def _on_remove(self, name: str) -> None:
        if self.profile.remove(name):
            self._refresh_list()
            self.profile_changed.emit()
