"""
Voice settings dialog — Kokoro voice picker, speed/volume sliders, test button.

Opened from the top-bar 🔊 / 🔇 Voice button. Provides full control over:
  * Enable/disable
  * Kokoro voice selection (from KOKORO_VOICES list)
  * Speech speed (0.5x – 2.0x)
  * Speech volume (0% – 100%)
  * Model download trigger if Kokoro not yet present
  * "Test voice" button to hear a sample
"""

from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QSlider, QVBoxLayout, QWidget, QCheckBox,
)

from app.services.voice import KOKORO_VOICES, KOKORO_MODEL, KOKORO_VPACK
from app.ui.theme import COLORS, FONTS, SPACE


class VoiceSettingsDialog(QDialog):
    """Modal settings dialog for the voice service."""

    test_requested      = Signal()
    download_requested  = Signal()

    def __init__(self, voice, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.voice = voice
        self.setWindowTitle("Voice Settings")
        self.setMinimumWidth(440)
        self.setStyleSheet(
            f"QDialog {{ background-color: {COLORS.bg_panel}; }}"
            f"QLabel {{ color: {COLORS.text}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACE.xl, SPACE.lg, SPACE.xl, SPACE.lg)
        outer.setSpacing(SPACE.md)

        # ── Header ─────────────────────────────────────────────────────────
        title = QLabel("Voice")
        title.setStyleSheet(
            f"color: {COLORS.text}; font-size: {FONTS.xl}pt; font-weight: 700;"
        )
        outer.addWidget(title)

        sub = QLabel("Configure the AI coach's voice. Changes apply instantly.")
        sub.setStyleSheet(
            f"color: {COLORS.text_muted}; font-size: {FONTS.sm}pt;"
        )
        sub.setWordWrap(True)
        outer.addWidget(sub)

        outer.addWidget(self._divider())

        # ── Enable toggle ──────────────────────────────────────────────────
        row = QHBoxLayout()
        row.setSpacing(SPACE.sm)
        self.enable_check = QCheckBox("Enable voice coaching")
        self.enable_check.setChecked(self.voice.enabled)
        self.enable_check.setStyleSheet(
            f"QCheckBox {{ color: {COLORS.text}; font-size: {FONTS.md}pt; }}"
            f"QCheckBox::indicator {{ width: 16px; height: 16px; }}"
            f"QCheckBox::indicator:checked {{"
            f"  background-color: {COLORS.accent}; border-radius: 3px;"
            f"}}"
            f"QCheckBox::indicator:unchecked {{"
            f"  background-color: {COLORS.bg_input}; border-radius: 3px;"
            f"  border: 1px solid {COLORS.border_subtle};"
            f"}}"
        )
        self.enable_check.toggled.connect(self._on_enable_toggled)
        row.addWidget(self.enable_check)
        row.addStretch(1)
        outer.addLayout(row)

        # ── Status line ────────────────────────────────────────────────────
        self.status_label = QLabel(self._status_text())
        self.status_label.setStyleSheet(
            f"color: {COLORS.text_dim}; font-size: {FONTS.sm}pt;"
        )
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        # ── Read for color selector ───────────────────────────────────────
        outer.addSpacing(SPACE.sm)
        self._labeled_row(outer, "Read aloud for", "")
        self.color_combo = QComboBox()
        self.color_combo.addItem("Auto (my moves only)", "auto")
        self.color_combo.addItem("Both colors",  "both")
        self.color_combo.addItem("White only",   "white")
        self.color_combo.addItem("Black only",   "black")
        # Select current value
        current_color = getattr(self.voice, "read_color", "both")
        for i in range(self.color_combo.count()):
            if self.color_combo.itemData(i) == current_color:
                self.color_combo.setCurrentIndex(i)
                break
        self.color_combo.setStyleSheet(self._combo_qss())
        self.color_combo.currentIndexChanged.connect(self._on_color_changed)
        outer.addWidget(self.color_combo)

        # Hint under the dropdown explaining the new "auto" option
        self._color_hint = QLabel(self._color_hint_text())
        self._color_hint.setStyleSheet(
            f"color: {COLORS.text_dim}; font-size: {FONTS.xs}pt;"
        )
        self._color_hint.setWordWrap(True)
        outer.addWidget(self._color_hint)

        outer.addWidget(self._divider())

        # ── Kokoro voice picker ────────────────────────────────────────────
        self._labeled_row(outer, "AI Voice (Kokoro)", "")
        self.voice_combo = QComboBox()
        for voice_id, label in KOKORO_VOICES:
            self.voice_combo.addItem(label, voice_id)
        # Select current voice
        for i, (vid, _) in enumerate(KOKORO_VOICES):
            if vid == self.voice._kvoice:
                self.voice_combo.setCurrentIndex(i)
                break
        self.voice_combo.setStyleSheet(self._combo_qss())
        self.voice_combo.currentIndexChanged.connect(self._on_voice_changed)
        outer.addWidget(self.voice_combo)

        if not (KOKORO_MODEL.exists() and KOKORO_VPACK.exists()):
            self.download_btn = QPushButton("⬇  Download AI voice (one-time, ~100 MB)")
            self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.download_btn.setMinimumHeight(34)
            self.download_btn.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {COLORS.bg_card};"
                f"  color: {COLORS.accent};"
                f"  border: 1px solid {COLORS.accent};"
                f"  border-radius: 5px;"
                f"  padding: 7px 12px;"
                f"  font-size: {FONTS.sm}pt;"
                f"  font-weight: 600;"
                f"}}"
                f"QPushButton:hover {{ background-color: {COLORS.bg_card_hi}; }}"
            )
            self.download_btn.clicked.connect(self._on_download_clicked)
            outer.addWidget(self.download_btn)

        outer.addSpacing(SPACE.sm)

        # ── Speed slider ───────────────────────────────────────────────────
        self.speed_label = QLabel(f"Speed:  {self.voice._kspeed:.1f}×")
        self.speed_label.setStyleSheet(
            f"color: {COLORS.text}; font-size: {FONTS.md}pt;"
        )
        outer.addWidget(self.speed_label)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setMinimum(50)    # 0.5x
        self.speed_slider.setMaximum(200)   # 2.0x
        self.speed_slider.setValue(int(self.voice._kspeed * 100))
        self.speed_slider.setStyleSheet(self._slider_qss())
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        outer.addWidget(self.speed_slider)

        # ── Volume slider ──────────────────────────────────────────────────
        self.vol_label = QLabel(f"Volume:  {int(self.voice._vol * 100)}%")
        self.vol_label.setStyleSheet(
            f"color: {COLORS.text}; font-size: {FONTS.md}pt;"
        )
        outer.addWidget(self.vol_label)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setMinimum(0)
        self.vol_slider.setMaximum(100)
        self.vol_slider.setValue(int(self.voice._vol * 100))
        self.vol_slider.setStyleSheet(self._slider_qss())
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        outer.addWidget(self.vol_slider)

        outer.addWidget(self._divider())

        # ── Action buttons ─────────────────────────────────────────────────
        action_row = QHBoxLayout()
        action_row.setSpacing(SPACE.sm)

        self.test_btn = QPushButton("🔊  Test voice")
        self.test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_btn.setMinimumHeight(36)
        self.test_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {COLORS.bg_card};"
            f"  color: {COLORS.text};"
            f"  border: 1px solid {COLORS.border_subtle};"
            f"  border-radius: 5px;"
            f"  padding: 8px 14px;"
            f"  font-size: {FONTS.md}pt;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {COLORS.bg_card_hi};"
            f"  border-color: {COLORS.border_focus};"
            f"}}"
        )
        self.test_btn.clicked.connect(self._on_test_clicked)
        action_row.addWidget(self.test_btn)

        action_row.addStretch(1)

        close_btn = QPushButton("Done")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setMinimumHeight(36)
        close_btn.setStyleSheet(
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
        close_btn.clicked.connect(self.accept)
        action_row.addWidget(close_btn)

        outer.addLayout(action_row)

    # ─────────────────────────────────────────────────────────────────────
    def _divider(self) -> QFrame:
        d = QFrame()
        d.setFixedHeight(1)
        d.setStyleSheet(f"background-color: {COLORS.border_subtle};")
        return d

    def _labeled_row(self, parent_layout, title: str, hint: str) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        t = QLabel(title)
        t.setStyleSheet(f"color: {COLORS.text}; font-size: {FONTS.md}pt; font-weight: 600;")
        row.addWidget(t)
        if hint:
            h = QLabel(hint)
            h.setStyleSheet(f"color: {COLORS.text_dim}; font-size: {FONTS.xs}pt;")
            row.addWidget(h)
        row.addStretch(1)
        parent_layout.addLayout(row)

    def _combo_qss(self) -> str:
        return (
            f"QComboBox {{"
            f"  background-color: {COLORS.bg_input};"
            f"  color: {COLORS.text};"
            f"  border: 1px solid {COLORS.border_subtle};"
            f"  border-radius: 5px;"
            f"  padding: 6px 10px;"
            f"  font-size: {FONTS.md}pt;"
            f"  min-height: 22px;"
            f"}}"
            f"QComboBox:hover {{ border-color: {COLORS.border_focus}; }}"
            f"QComboBox::drop-down {{ border: none; width: 24px; }}"
            f"QComboBox QAbstractItemView {{"
            f"  background-color: {COLORS.bg_card};"
            f"  color: {COLORS.text};"
            f"  selection-background-color: {COLORS.accent};"
            f"  selection-color: {COLORS.on_accent};"
            f"  border: 1px solid {COLORS.border_subtle};"
            f"}}"
        )

    def _slider_qss(self) -> str:
        return (
            f"QSlider::groove:horizontal {{"
            f"  height: 4px;"
            f"  background-color: {COLORS.bg_input};"
            f"  border-radius: 2px;"
            f"}}"
            f"QSlider::sub-page:horizontal {{"
            f"  background-color: {COLORS.accent};"
            f"  border-radius: 2px;"
            f"}}"
            f"QSlider::handle:horizontal {{"
            f"  background-color: {COLORS.text};"
            f"  width: 14px;"
            f"  height: 14px;"
            f"  margin: -6px 0;"
            f"  border-radius: 7px;"
            f"}}"
            f"QSlider::handle:horizontal:hover {{"
            f"  background-color: {COLORS.accent};"
            f"}}"
        )

    def _status_text(self) -> str:
        if self.voice.kokoro_ready:
            return "✓  AI voice ready"
        if KOKORO_MODEL.exists() and KOKORO_VPACK.exists():
            return "Loading AI voice…"
        if self.voice.fallback_ready:
            return "Using system voice (download Kokoro for AI quality)"
        return "No voice available"

    # ── Slot handlers ─────────────────────────────────────────────────────
    def _on_enable_toggled(self, checked: bool) -> None:
        # Mirror to voice service without re-triggering the button
        if checked != self.voice.enabled:
            self.voice.toggle()

    def _on_voice_changed(self, idx: int) -> None:
        voice_id = self.voice_combo.itemData(idx)
        if voice_id:
            self.voice.set_kokoro_voice(voice_id)

    def _on_color_changed(self, idx: int) -> None:
        color = self.color_combo.itemData(idx)
        if color in ("both", "white", "black", "auto"):
            self.voice.set_read_color(color)
        # Update the hint to match the new selection
        if hasattr(self, "_color_hint"):
            self._color_hint.setText(self._color_hint_text())

    def _color_hint_text(self) -> str:
        """Returns a one-line hint that explains the current 'read aloud for'
        choice. The auto option specifically explains how it works since
        users will be curious why it might not narrate anything."""
        choice = self.color_combo.itemData(self.color_combo.currentIndex())
        if choice == "auto":
            return ("Uses your saved usernames (👤 in the top bar) to figure "
                    "out which side was you and narrate only those moves.")
        if choice == "white":
            return "Voice narrates only White's moves."
        if choice == "black":
            return "Voice narrates only Black's moves."
        return "Voice narrates every move."

    def _on_speed_changed(self, val: int) -> None:
        speed = val / 100.0
        self.voice.set_speed(speed)
        self.speed_label.setText(f"Speed:  {speed:.1f}×")

    def _on_volume_changed(self, val: int) -> None:
        vol = val / 100.0
        self.voice.set_volume(vol)
        self.vol_label.setText(f"Volume:  {val}%")

    def _on_test_clicked(self) -> None:
        # Ensure voice is on for the test
        if not self.voice.enabled:
            self.voice.toggle()
            self.enable_check.setChecked(True)
        self.voice.speak(
            "Hi, I'm your ChessLens coach. Pick the voice that sounds best to you."
        )

    def _on_download_clicked(self) -> None:
        self.download_requested.emit()
        self.download_btn.setEnabled(False)
        self.download_btn.setText("Downloading… see status in the left panel")
