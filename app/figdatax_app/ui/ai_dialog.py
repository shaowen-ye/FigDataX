"""AI settings dialog and the calibration-suggestion review dialog."""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ..ai import config as aicfg
from ..ai.keystore import get_api_key, keychain_available, set_api_key
from ..ai.providers import AIError

_KIND_LABELS = {
    "claude-cli": "Claude 订阅 CLI / Claude Max (claude)",
    "codex-cli": "ChatGPT 订阅 CLI / Codex (codex)",
    "openai-compat": "OpenAI 兼容 API / DeepSeek 等",
}


class AISettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 设置 / AI Settings")
        self.settings = settings
        self.cfg = aicfg.load_config(settings)
        self.resize(520, 300)
        self._build()
        self._sync_visibility()

    def _build(self):
        form = QFormLayout(self)

        self.kind = QComboBox()
        for k in aicfg.KINDS:
            self.kind.addItem(_KIND_LABELS[k], k)
        self.kind.setCurrentIndex(aicfg.KINDS.index(self.cfg["kind"])
                                  if self.cfg["kind"] in aicfg.KINDS else 0)
        self.kind.currentIndexChanged.connect(self._sync_visibility)
        form.addRow("提供方 / Provider", self.kind)

        self.model = QLineEdit(self.cfg["model"])
        self.model.setPlaceholderText("留空用默认 / blank = provider default")
        form.addRow("模型 / Model (CLI)", self.model)

        self.base_url = QLineEdit(self.cfg["base_url"])
        form.addRow("API Base URL", self.base_url)
        self.api_model = QLineEdit(self.cfg["api_model"])
        form.addRow("API 模型 / API model", self.api_model)

        self.api_key = QLineEdit(get_api_key("openai-compat"))
        self.api_key.setEchoMode(QLineEdit.Password)
        hint = "" if keychain_available() else " (无 Keychain：仅本次会话 / session-only)"
        form.addRow(f"API Key{hint}", self.api_key)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        form.addRow(self.status)

        row = QHBoxLayout()
        test_btn = QPushButton("测试连接 / Test")
        test_btn.clicked.connect(self._test)
        row.addWidget(test_btn)
        box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        box.accepted.connect(self._save)
        box.rejected.connect(self.reject)
        row.addWidget(box)
        holder = QWidget(); holder.setLayout(row)
        form.addRow(holder)

    def _current_kind(self) -> str:
        return self.kind.currentData()

    def _sync_visibility(self):
        api = self._current_kind() == "openai-compat"
        cli = not api
        self.model.setEnabled(cli)
        self.base_url.setEnabled(api)
        self.api_model.setEnabled(api)
        self.api_key.setEnabled(api)

    def _collect(self) -> dict:
        return {"kind": self._current_kind(), "model": self.model.text().strip(),
                "base_url": self.base_url.text().strip(),
                "api_model": self.api_model.text().strip()}

    def _test(self):
        cfg = self._collect()
        self.status.setText("测试中… / Testing…")
        self.status.repaint()
        try:
            provider = aicfg.build_provider(cfg, api_key=self.api_key.text().strip())
            reply = provider.complete("Reply with the single word: OK", timeout=60)
            self.status.setText(f"✓ 连接成功 / OK — {reply[:60]}")
        except AIError as exc:
            self.status.setText(f"✗ {exc}")
        except Exception as exc:  # noqa: BLE001
            self.status.setText(f"✗ {exc}")

    def _save(self):
        cfg = self._collect()
        aicfg.save_config(self.settings, cfg)
        if cfg["kind"] == "openai-compat":
            if not set_api_key("openai-compat", self.api_key.text().strip()) \
                    and self.api_key.text().strip():
                QMessageBox.information(
                    self, "AI", "Key 未能存入 Keychain，仅本次会话有效。\n"
                                "Key not saved to Keychain; session-only.")
        self.accept()


class CalibrationReviewDialog(QDialog):
    """Let the user confirm/adjust AI-suggested tick values before they are applied."""

    def __init__(self, suggestion, plot_bbox, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 校准建议 / Review AI calibration")
        self.suggestion = suggestion
        self.plot_bbox = plot_bbox
        self.resize(460, 360)
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        v.addWidget(QLabel(
            f"图表类型 / Chart type: <b>{self.suggestion.chart_type}</b>"
            + (f" · {self.suggestion.notes}" if self.suggestion.notes else "")))
        v.addWidget(QLabel("勾选并核对刻度值；取消勾选忽略该点。\n"
                           "Check and verify each tick; uncheck to skip."))
        rows = [("x", t) for t in (self.suggestion.x_ticks or [])] + \
               [("y", t) for t in (self.suggestion.y_ticks or [])]
        self.table = QTableWidget(len(rows), 3)
        self.table.setHorizontalHeaderLabels(["用 / Use", "轴 / Axis", "值 / Value"])
        self._rows = rows
        for r, (axis, t) in enumerate(rows):
            use = QTableWidgetItem(); use.setCheckState(Qt.Checked)
            self.table.setItem(r, 0, use)
            self.table.setItem(r, 1, QTableWidgetItem(axis))
            self.table.setItem(r, 2, QTableWidgetItem(f"{t.value:g}"))
        v.addWidget(self.table)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        v.addWidget(box)

    def confirmed(self) -> List[tuple]:
        """Return [(axis, value, suggestion), ...] for checked, valid rows."""
        out = []
        for r, (axis, t) in enumerate(self._rows):
            if self.table.item(r, 0).checkState() != Qt.Checked:
                continue
            try:
                value = float(self.table.item(r, 2).text())
            except ValueError:
                continue
            out.append((axis, value, t))
        return out
