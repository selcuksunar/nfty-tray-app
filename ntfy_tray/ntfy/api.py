from __future__ import annotations
import json
import requests
import logging
from ntfy_tray.database import Settings
from ntfy_tray.ntfy.listener import _apply_auth

logger = logging.getLogger("ntfy-tray")
settings = Settings("ntfy-tray")


class NtfyClient:
    def __init__(self, url: str, username: str | None = None, password: str | None = None):
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        _apply_auth(self.session, username, password)

    def get_subscriptions(self) -> list[dict] | None:
        topics_url = settings.value("Server/topics_url", type=str)
        if not topics_url:
            logger.warning("Server/topics_url is not configured.")
            return None  # None = config error → use saved topics

        try:
            response = self.session.get(topics_url, timeout=10)
            if not response.ok:
                logger.error(f"Failed to fetch topics JSON: {response.status_code}")
                return None
            data = response.json()
        except Exception as e:
            logger.error(f"Error fetching topics JSON: {e}")
            return None

        topic_entries = data.get("topics", [])
        subscriptions = []
        for entry in topic_entries:
            topic = entry.get("name", "").strip()
            if not topic:
                continue
            try:
                r = self.session.get(
                    f"{self.url}/{topic}/json",
                    params={"poll": "1", "since": "0"},
                    timeout=10,
                )
                if r.status_code in [401, 403]:
                    logger.debug(f"Access denied to topic: {topic} ({r.status_code})")
                    continue
            except Exception as e:
                logger.error(f"Error checking permissions for topic {topic}: {e}")
                continue

            subscriptions.append({
                "topic": topic,
                "name": entry.get("display_name", topic),
                "description": entry.get("description", f"ntfy topic: {topic}"),
                "icon": entry.get("icon", ""),
            })

        logger.debug(f"Authorized subscriptions: {subscriptions}")
        return subscriptions

    def get_messages(self, topic: str, since: str = "all") -> list[dict] | None:
        """Fetch cached messages for a topic. since='all' returns all cached messages."""
        try:
            response = self.session.get(
                f"{self.url}/{topic}/json",
                params={"poll": "1", "since": since},
                timeout=15,
            )
            if not response.ok:
                logger.error(f"get_messages: {topic} status={response.status_code}")
                return []
            messages = []
            for line in response.text.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    messages.append(msg)
                except Exception as e:
                    logger.error(f"Error parsing message line: {e}")
            return messages
        except Exception as e:
            logger.error(f"Error fetching messages for {topic}: {e}")
            return None

    def delete_message(self, topic: str, message_id: str) -> bool:
        try:
            response = self.session.delete(f"{self.url}/{topic}/messages/{message_id}")
            return response.ok
        except Exception as e:
            logger.error(f"Error deleting message {message_id}: {e}")
            return False

    def delete_messages(self, topic: str | None = None) -> bool:
        try:
            url = f"{self.url}/{topic}/messages" if topic else f"{self.url}/*/messages"
            response = self.session.delete(url)
            return response.ok
        except Exception as e:
            logger.error(f"Error deleting messages: {e}")
            return False
