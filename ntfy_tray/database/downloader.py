import logging
import os
import sys
import requests

from .cache import Cache
from .settings import Settings


logger = logging.getLogger("ntfy-tray")
settings = Settings("ntfy-tray")


def _get_certifi_path() -> str:
    """Get the certifi CA bundle path, works both in dev and PyInstaller builds."""
    if getattr(sys, 'frozen', False):
        bundle_dir = sys._MEIPASS
        frozen_cert = os.path.join(bundle_dir, 'certifi', 'cacert.pem')
        if os.path.exists(frozen_cert):
            return frozen_cert
    try:
        import certifi
        return certifi.where()
    except ImportError:
        pass
    return True  # requests default


class Downloader(object):
    def __init__(self):
        self.cache = Cache()
        self.session = requests.Session()
        certfile = settings.value("Server/certPath", type=str)
        if certfile and os.path.exists(certfile):
            self.session.verify = certfile
        else:
            self.session.verify = _get_certifi_path()

    def get(self, url: str) -> requests.Response:
        """
        Get the response of an http get request.
        Bypasses the cache.
        """
        return self.session.get(url)

    def get_filename(self, url: str) -> str:
        """
        Get the content of an http get request, as a filename.
        """
        if filename := self.cache.lookup(url):
            return filename

        try:
            response = self.get(url)
        except Exception as e:
            logger.error(f"get_filename: downloading {url} failed.: {e}")
            return ""

        return self.cache.store(url, response) if response.ok else ""
