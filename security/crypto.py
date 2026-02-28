"""Fernet encryption for sensitive data (API keys, passwords in DB)."""

import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_master_key = os.getenv("FERNET_MASTER_KEY", "").strip()

try:
    if not _master_key or _master_key == "PLACEHOLDER":
        raise ValueError("empty or placeholder key")
    _cipher_suite = Fernet(_master_key.encode())
except (ValueError, Exception):
    _master_key = Fernet.generate_key().decode()
    logger.warning(
        "FERNET_MASTER_KEY не задан или невалиден — сгенерирован временный. "
        "Скопируйте в .env / docker-compose:\n  FERNET_MASTER_KEY=%s",
        _master_key,
    )
    _cipher_suite = Fernet(_master_key.encode())


def encrypt_secret(secret: str) -> str:
    """Шифрует чувствительные данные перед записью в БД."""
    if not secret:
        return secret
    return _cipher_suite.encrypt(secret.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Расшифровывает данные из БД."""
    if not token:
        return token
    return _cipher_suite.decrypt(token.encode()).decode()
