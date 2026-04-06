from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile

from PyQt6 import QtCore, QtWidgets

from ntfy_tray.i18n import tr
from ntfy_tray.tasks import DownloadUpdateTask


class UpdateDialog(QtWidgets.QDialog):
    def __init__(self, latest_version: str, download_url: str, parent=None):
        super().__init__(parent)
        self.latest_version = latest_version
        self.download_url = download_url
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle(tr("update.title"))
        self.setMinimumWidth(380)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint)

        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel(tr("update.message").format(version=self.latest_version))
        label.setWordWrap(True)
        layout.addWidget(label)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_update = QtWidgets.QPushButton(tr("update.install"))
        self.btn_later = QtWidgets.QPushButton(tr("update.later"))
        btn_layout.addWidget(self.btn_update)
        btn_layout.addWidget(self.btn_later)
        layout.addLayout(btn_layout)

        self.btn_update.clicked.connect(self._start_download)
        self.btn_later.clicked.connect(self.reject)

    def _start_download(self):
        self.btn_update.setEnabled(False)
        self.btn_later.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText(tr("update.downloading"))

        ext = ".dmg" if platform.system() == "Darwin" else ".exe"
        self._dest = os.path.join(tempfile.gettempdir(), f"ntfy-tray-update{ext}")

        self._task = DownloadUpdateTask(self.download_url, self._dest)
        self._task.progress.connect(self.progress_bar.setValue)
        self._task.finished.connect(self._on_downloaded)
        self._task.failed.connect(self._on_error)
        self._task.start()

    def _on_downloaded(self, path: str):
        self.status_label.setText(tr("update.installing"))
        self._install(path)

    def _on_error(self):
        self.status_label.setText(tr("update.error"))
        self.btn_later.setEnabled(True)

    def _install(self, path: str):
        system = platform.system()
        if system == "Darwin":
            # Mount DMG, copy .app, restart
            subprocess.Popen([
                "bash", "-c",
                f'hdiutil attach "{path}" -mountpoint /tmp/ntfy-update-mnt && '
                f'cp -R /tmp/ntfy-update-mnt/ntfy-tray.app /Applications/ && '
                f'hdiutil detach /tmp/ntfy-update-mnt && '
                f'open /Applications/ntfy-tray.app'
            ])
            QtWidgets.QApplication.quit()
        elif system == "Windows":
            # Run installer silently, quit current instance
            subprocess.Popen([path, "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"])
            QtWidgets.QApplication.quit()
        else:
            self.status_label.setText(tr("update.manual"))
            self.btn_later.setText(tr("update.close"))
            self.btn_later.setEnabled(True)
