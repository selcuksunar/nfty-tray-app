from __future__ import annotations

import base64
import json
import logging
import time

import websocket
from PyQt6 import QtCore

logger = logging.getLogger("ntfy-tray")


def _build_ws_url(http_url: str) -> str:
    """Convert http(s):// URL to ws(s):// URL."""
    url = http_url.rstrip("/")
    if url.startswith("https://"):
        return "wss://" + url[8:]
    elif url.startswith("http://"):
        return "ws://" + url[7:]
    return url


def _build_auth_headers(username: str | None, password: str | None) -> list[str]:
    """Build WebSocket handshake Authorization headers for ntfy auth."""
    if username and password:
        creds = base64.b64encode(f"{username}:{password}".encode()).decode()
        return [f"Authorization: Basic {creds}"]
    elif password:
        return [f"Authorization: Bearer {password}"]
    elif username:
        return [f"Authorization: Bearer {username}"]
    return []


# Keep for api.py which imports it
def _apply_auth(session, username: str | None, password: str | None):
    if username and password:
        session.auth = (username, password)
    elif password:
        session.headers["Authorization"] = f"Bearer {password}"
    elif username:
        session.headers["Authorization"] = f"Bearer {username}"


class NtfyListener(QtCore.QThread):
    new_message = QtCore.pyqtSignal(dict)
    opened = QtCore.pyqtSignal()
    closed = QtCore.pyqtSignal()
    reconnecting = QtCore.pyqtSignal()

    def __init__(self, url: str, topics: list[str], username: str | None = None, password: str | None = None):
        super().__init__()
        self.url = url.rstrip("/")
        self.topics = topics
        self.username = username
        self.password = password
        self._running = False
        self._ws: websocket.WebSocket | None = None

    def _interruptible_sleep(self, seconds: int):
        """Sleep in 100 ms increments so stop() can interrupt."""
        for _ in range(seconds * 10):
            if not self._running:
                break
            self.msleep(100)

    def run(self):
        self._running = True
        topics_str = ",".join(self.topics)
        ws_base = _build_ws_url(self.url)
        ws_url = f"{ws_base}/{topics_str}/ws"
        headers = _build_auth_headers(self.username, self.password)

        # Only get messages from this point forward; history is loaded separately
        last_event_time = int(time.time())
        opened_once = False
        backoff = 5  # seconds, doubles on failure, caps at 60

        while self._running:
            connected = False
            try:
                full_url = f"{ws_url}?since={last_event_time}"
                logger.debug(f"ntfy ws: connecting to {full_url}")

                self._ws = websocket.create_connection(
                    full_url,
                    header=headers,
                    timeout=15,      # handshake / connect timeout
                )
                self._ws.settimeout(90)  # read timeout per frame (keepalive arrives within ~55s)

                connected = True
                if not opened_once:
                    opened_once = True
                    self.opened.emit()
                backoff = 5

                # Receive loop
                while self._running:
                    try:
                        raw = self._ws.recv()
                        if raw is None:
                            break
                        data = json.loads(raw)
                        t = data.get("time", 0)
                        if t:
                            last_event_time = t
                        if data.get("event") == "message":
                            self.new_message.emit(data)
                    except websocket.WebSocketTimeoutException:
                        # No keepalive in 90 s — server silent, reconnect
                        logger.debug("ntfy ws: keepalive timeout, reconnecting")
                        break
                    except websocket.WebSocketConnectionClosedException:
                        logger.debug("ntfy ws: connection closed by server")
                        break
                    except json.JSONDecodeError as e:
                        logger.error(f"ntfy ws: bad JSON: {e}")
                    except Exception as e:
                        if self._running:
                            logger.error(f"ntfy ws recv: {type(e).__name__}: {e}")
                        break

            except (websocket.WebSocketException, OSError, ConnectionError) as e:
                if self._running:
                    logger.warning(f"ntfy ws connect failed: {type(e).__name__}: {e}")
            except Exception as e:
                if self._running:
                    logger.error(f"ntfy ws unexpected: {type(e).__name__}: {e}")
            finally:
                try:
                    if self._ws is not None:
                        self._ws.close()
                except Exception:
                    pass
                self._ws = None

                if self._running:
                    self.reconnecting.emit()
                    if not connected:
                        # Connection failed — back off before retry
                        self._interruptible_sleep(backoff)
                        backoff = min(backoff * 2, 60)
                    # If connected but then dropped — reconnect immediately

        self.closed.emit()

    def stop(self):
        self._running = False
        try:
            if self._ws is not None:
                self._ws.close()
        except Exception:
            pass
        self.wait()
