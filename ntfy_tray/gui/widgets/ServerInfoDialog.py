import os

from ntfy_tray.database import Settings
from ntfy_tray.ntfy.models import NtfyVersionModel
from ntfy_tray.tasks import ImportSettingsTask, VerifyServerInfoTask
from ntfy_tray.utils import update_widget_property
from ntfy_tray.i18n import tr
from PyQt6 import QtWidgets, QtNetwork

from ..designs.widget_server import Ui_Dialog


settings = Settings("ntfy-tray")


class ServerInfoDialog(QtWidgets.QDialog, Ui_Dialog):
    def __init__(self, url: str = "", token: str = "", enable_import: bool = True):
        super(ServerInfoDialog, self).__init__()
        self.setupUi(self)
        self.setWindowTitle(tr("server.title"))
        self.line_url.setPlaceholderText("https://ntfy.sh")
        self.label_2.setText(tr("server.username_label"))
        self.line_token.setPlaceholderText(tr("server.username"))
        self.line_password = QtWidgets.QLineEdit()
        self.line_password.setPlaceholderText(tr("server.password"))
        self.line_password.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.formLayout.addRow(tr("server.password_label"), self.line_password)
        self.certPath = settings.value("Server/certPath", type=str) or ""

        self.line_token.setText(settings.value("Server/username", type=str))
        self.line_password.setText(settings.value("Server/password", type=str))
        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setDisabled(True)
        self.pb_import.setVisible(enable_import)
        self.pb_certificate.hide()
        self.label_status.setText(tr("server.certificate.path").format(path=self.certPath))
        self.label_status.hide()
        self.link_callbacks()
        self.line_url.setText(url)

    def test_server_info(self):
        update_widget_property(self.pb_test, "state", "")
        update_widget_property(self.line_url, "state", "")
        update_widget_property(self.line_token, "state", "")
        update_widget_property(self.pb_certificate, "state", "")
        self.label_server_info.clear()

        url = self.line_url.text()
        username = self.line_token.text()
        password = self.line_password.text()
        if not url:
            return

        self.pb_test.setDisabled(True)
        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setDisabled(True)

        self.task = VerifyServerInfoTask(url, username, password)
        self.task.success.connect(self.server_info_success)
        self.task.incorrect_credentials.connect(self.incorrect_credentials_callback)
        self.task.incorrect_url.connect(self.incorrect_url_callback)
        self.task.start()

    def server_info_success(self):
        self.pb_test.setEnabled(True)
        update_widget_property(self.pb_test, "state", "success")
        update_widget_property(self.line_token, "state", "success")
        update_widget_property(self.line_url, "state", "success")
        update_widget_property(self.pb_certificate, "state", "")
        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setFocus()

    def incorrect_credentials_callback(self):
        self.pb_test.setEnabled(True)
        update_widget_property(self.pb_test, "state", "failed")
        update_widget_property(self.line_token, "state", "failed")
        update_widget_property(self.line_password, "state", "failed")
        update_widget_property(self.line_url, "state", "success")
        self.line_token.setFocus()

    def incorrect_url_callback(self):
        self.pb_test.setEnabled(True)
        self.label_server_info.clear()
        update_widget_property(self.pb_test, "state", "failed")
        update_widget_property(self.line_token, "state", "success")
        update_widget_property(self.line_url, "state", "failed")
        update_widget_property(self.pb_certificate, "state", "")
        self.line_url.setFocus()

    def incorrect_cert_callback(self):
        self.pb_test.setEnabled(True)
        self.label_server_info.clear()
        update_widget_property(self.pb_test, "state", "failed")
        update_widget_property(self.line_token, "state", "success")
        update_widget_property(self.line_url, "state", "success")
        update_widget_property(self.pb_certificate, "state", "failed")
        self.line_url.setFocus()

    def input_changed_callback(self):
        if self.line_url.text().startswith("https"):
            self.label_status.show()
            self.pb_certificate.show()
        else:
            self.label_status.hide()
            self.pb_certificate.hide()
            self.certPath = ""
        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setDisabled(True)
        update_widget_property(self.pb_test, "state", "")

    def import_success_callback(self):
        self.line_url.setText(settings.value("Server/url", type=str))
        self.line_token.setText(settings.value("Server/username", type=str))
        self.line_password.setText(settings.value("Server/password", type=str))

    def import_callback(self):
        fname = QtWidgets.QFileDialog.getOpenFileName(
            self, tr("settings.dialog.import_settings"), settings.value("export/path", type=str), "*",
        )[0]
        if fname and os.path.exists(fname):
            self.import_settings_task = ImportSettingsTask(fname)
            self.import_settings_task.success.connect(self.import_success_callback)
            self.import_settings_task.start()

    def certificate_callback(self):
        fname = QtWidgets.QFileDialog.getOpenFileName(
            self, tr("server.import_cert"), os.path.expanduser("~"), tr("server.cert_filter"),
        )[0]
        if fname and os.path.exists(fname):
            # Verify the certificate
            if certificate := QtNetwork.QSslCertificate.fromPath(fname):
                self.certPath = fname
                self.label_status.setText(tr("server.certificate.path").format(path=self.certPath))
            else:
                self.label_status.setText(tr("server.certificate.invalid"))
                self.certPath = ""
        else:
            self.label_status.setText(tr("server.certificate.none"))
            self.certPath = ""
            
        self.input_changed_callback()
        
    def link_callbacks(self):
        self.pb_test.clicked.connect(self.test_server_info)
        self.line_url.textChanged.connect(self.input_changed_callback)
        self.line_token.textChanged.connect(self.input_changed_callback)
        self.line_password.textChanged.connect(self.input_changed_callback)
        self.pb_import.clicked.connect(self.import_callback)
        self.pb_certificate.clicked.connect(self.certificate_callback)
