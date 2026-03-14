from PyQt6 import QtCore, QtGui, QtWidgets

from ntfy_tray.database import Settings
from ntfy_tray.gui.themes import get_theme_file
from ntfy_tray.i18n import tr


settings = Settings("ntfy-tray")


class StatusWidget(QtWidgets.QLabel):
    def __init__(self):
        super(StatusWidget, self).__init__()
        self.setFixedSize(QtCore.QSize(20, 20))
        self.setScaledContents(True)
        self.set_connecting()
        self.image = None

    def set_status(self, image: str):
        self.image = image
        self.setPixmap(QtGui.QPixmap(get_theme_file(image)))

    def set_active(self):
        self.setToolTip(tr("status.active"))
        self.set_status("status_active.svg")

    def set_connecting(self):
        self.setToolTip(tr("status.connecting"))
        self.set_status("status_connecting.svg")

    def set_inactive(self):
        self.setToolTip(tr("status.inactive"))
        self.set_status("status_inactive.svg")

    def set_error(self):
        self.setToolTip(tr("status.error"))
        self.set_status("status_error.svg")

    def refresh(self):
        # refresh on theme change
        if self.image:
            self.set_status(self.image)
