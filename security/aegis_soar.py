import asyncio
import ipaddress
import logging
import os

import httpx

logger = logging.getLogger(__name__)

CF_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CF_ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID")
TELEGRAM_ADMIN_NOTIFY = os.getenv("AEGIS_TELEGRAM_NOTIFY", "1") == "1"

_BLOCKED_ATTACKS = 0
_blocked_ips: set[str] = set()  # Dedup within process lifetime


def register_blocked_attack() -> None:
    global _BLOCKED_ATTACKS
    _BLOCKED_ATTACKS += 1


def get_blocked_attacks() -> int:
    """Return number of attacks blocked by SOAR runtime since process start."""
    return _BLOCKED_ATTACKS


async def block_ip_on_edge(ip_address: str, reason: str = "Aegis Autonomous Block"):
    """
    Отправляет команду в Cloudflare WAF на блокировку IP-адреса на уровне Edge.
    """
    if not ip_address:
        return False

    # Validate IP format
    try:
        addr = ipaddress.ip_address(ip_address)
        if addr.is_private or addr.is_loopback or addr.is_reserved:
            logger.warning("[AEGIS_SOAR] Пропуск приватного/резервного IP: %s", ip_address)
            return False
    except ValueError:
        logger.error("[AEGIS_SOAR] Невалидный IP-адрес: %s", ip_address)
        return False

    # Dedup — don't block same IP twice
    if ip_address in _blocked_ips:
        logger.info("[AEGIS_SOAR] IP %s уже заблокирован", ip_address)
        return True


    if not CF_API_TOKEN or not CF_ZONE_ID:
        logger.error("[AEGIS_SOAR] Токен Cloudflare не настроен. Симуляция блокировки.")
        logger.warning("[AEGIS_SOAR] [SIMULATION] IP %s заблокирован. Причина: %s", ip_address, reason)
        return False

    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/firewall/access_rules/rules"
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "mode": "block",
        "configuration": {"target": "ip", "value": ip_address},
        "notes": f"PLAYE_V4_AEGIS: {reason}",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=5.0)
            if response.status_code == 200:
                logger.critical("[AEGIS_SOAR] ВНИМАНИЕ! IP %s успешно заблокирован на уровне WAF!", ip_address)
                register_blocked_attack()
                _blocked_ips.add(ip_address)
                # Async Telegram notification
                if TELEGRAM_ADMIN_NOTIFY:
                    try:
                        from app.bot.notifications import send_to_admin
                        await send_to_admin(
                            f"🛡 AEGIS SOAR: IP {ip_address} заблокирован\n"
                            f"Причина: {reason}"
                        )
                    except Exception:
                        pass  # Non-critical
                return True

            logger.error("[AEGIS_SOAR] Ошибка WAF API: %s", response.text)
            return False
    except Exception as exc:
        logger.error("[AEGIS_SOAR] Ошибка соединения с WAF: %s", exc)
        return False


def block_ip_sync(ip_address: str, reason: str = "Aegis Autonomous Block") -> bool:
    """Синхронная обертка для интеграции в sync-контексты."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already inside an async context — schedule as a task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, block_ip_on_edge(ip_address, reason))
            return future.result(timeout=10)
    else:
        return asyncio.run(block_ip_on_edge(ip_address, reason))
