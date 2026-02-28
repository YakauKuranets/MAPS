"""
syndicate_userbot.py — OSINT Telegram Userbot для мониторинга целевых каналов.

Подключается через Telethon, слушает TARGET_CHATS, обогащает профили
акторов, скачивает утечки, соблюдает тайминги маскировки.

ВНИМАНИЕ: Используется ИСКЛЮЧИТЕЛЬНО для легитимного OSINT-мониторинга
открытых каналов. Все действия логируются в audit trail.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ═══ Config from env ═══
API_ID: int = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
SESSION_NAME: str = os.getenv("SYNDICATE_SESSION", "syndicate_session")
TARGET_CHATS: list[str] = [
    c.strip() for c in os.getenv("SYNDICATE_TARGET_CHATS", "").split(",") if c.strip()
]
LEAKS_DIR: Path = Path(os.getenv("SYNDICATE_LEAKS_DIR", "/tmp/syndicate_leaks"))
SLEEP_THRESHOLD: float = float(os.getenv("SYNDICATE_SLEEP_SEC", "2.0"))

# Patterns for enrichment
_IOC_PATTERNS = {
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "domain": re.compile(r"\b[a-zA-Z0-9-]+\.[a-zA-Z]{2,}\b"),
    "btc_wallet": re.compile(r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    "sha256": re.compile(r"\b[a-fA-F0-9]{64}\b"),
}


class SyndicateUserbot:
    """Telegram userbot for passive OSINT collection."""

    def __init__(self) -> None:
        self._client = None
        self._running = False
        self._messages_processed = 0

    async def _get_client(self):
        """Lazy init Telethon client."""
        if self._client is not None:
            return self._client

        if not API_ID or not API_HASH:
            logger.error("[SYNDICATE] TELEGRAM_API_ID / TELEGRAM_API_HASH не настроены")
            return None

        try:
            from telethon import TelegramClient
            self._client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
            await self._client.start()
            me = await self._client.get_me()
            logger.warning(
                "[SYNDICATE] Инфильтрация успешна. Агент: %s (id=%s)",
                me.username or me.first_name,
                me.id,
            )
            return self._client
        except ImportError:
            logger.error("[SYNDICATE] Telethon не установлен: pip install telethon")
            return None
        except Exception as exc:
            logger.error("[SYNDICATE] Ошибка авторизации: %s", exc)
            return None

    def _extract_iocs(self, text: str) -> dict:
        """Extract indicators of compromise from message text."""
        iocs = {}
        for name, pattern in _IOC_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                iocs[name] = list(set(matches))
        return iocs

    async def _enrich_actor_profile(self, sender_id: int, text: str, chat_title: str) -> dict:
        """Enrich threat actor profile with intercepted data."""
        iocs = self._extract_iocs(text)
        profile = {
            "sender_id": sender_id,
            "chat": chat_title,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "text_preview": text[:200],
            "iocs": iocs,
            "word_count": len(text.split()),
        }
        if iocs:
            logger.info(
                "[SYNDICATE] IOC обнаружены в %s: %s",
                chat_title,
                {k: len(v) for k, v in iocs.items()},
            )
        return profile

    async def _analyze_leak_file(self, file_path: Path) -> dict:
        """Analyze downloaded leak file."""
        stat = file_path.stat()
        result = {
            "path": str(file_path),
            "size_bytes": stat.st_size,
            "extension": file_path.suffix,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.warning("[SYNDICATE] Leak file analyzed: %s (%d bytes)", file_path.name, stat.st_size)
        return result

    async def _handle_message(self, event) -> None:
        """Process incoming message from target chat."""
        self._messages_processed += 1
        sender = await event.get_sender()
        sender_id = sender.id if sender else 0
        chat = await event.get_chat()
        chat_title = getattr(chat, "title", "DM")

        # Text enrichment
        if event.text:
            await self._enrich_actor_profile(sender_id, event.text, chat_title)

        # Document download (leaks)
        if event.document:
            mime = event.document.mime_type or ""
            interesting_mimes = [
                "application/zip",
                "application/x-rar",
                "application/gzip",
                "application/pdf",
                "text/csv",
                "application/json",
            ]
            if mime in interesting_mimes:
                LEAKS_DIR.mkdir(parents=True, exist_ok=True)
                file_path = LEAKS_DIR / f"{sender_id}_{event.id}{Path(event.document.attributes[0].file_name).suffix if event.document.attributes else '.bin'}"
                await event.download_media(file=str(file_path))
                await self._analyze_leak_file(file_path)

        # Traffic masking delay
        await asyncio.sleep(SLEEP_THRESHOLD)

    async def start_monitoring(self) -> None:
        """Start listening to target chats."""
        client = await self._get_client()
        if not client:
            logger.error("[SYNDICATE] Невозможно запустить мониторинг без клиента")
            return

        if not TARGET_CHATS:
            logger.warning("[SYNDICATE] TARGET_CHATS пуст — мониторинг не начнётся")
            return

        from telethon import events

        @client.on(events.NewMessage(chats=TARGET_CHATS))
        async def handler(event):
            await self._handle_message(event)

        self._running = True
        logger.warning("[SYNDICATE] Мониторинг %d каналов запущен", len(TARGET_CHATS))
        await client.run_until_disconnected()

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False
        if self._client:
            await self._client.disconnect()
            logger.info("[SYNDICATE] Отключение от Telegram завершено")

    @property
    def stats(self) -> dict:
        return {
            "running": self._running,
            "messages_processed": self._messages_processed,
            "target_chats": len(TARGET_CHATS),
        }


# Singleton
syndicate_bot = SyndicateUserbot()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(syndicate_bot.start_monitoring())
