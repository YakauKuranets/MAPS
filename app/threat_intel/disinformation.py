"""Defensive synthetic-traffic generator for resilience testing.

This module generates *simulated* telemetry ghosts for internal QA/honeypot validation.
It does not broadcast to external channels directly.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import List
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class SyntheticAgent:
    """Structured decoy agent record."""
    id: str
    lat: float
    lon: float
    fake_imsi: str
    simulated_device: str
    signal_strength: int
    timestamp: float


class SyndromePoisoner:
    """Defensive synthetic-traffic generator for honeypot/QA validation."""

    DEVICE_POOL = [
        "RISC-V Node", "Android 13 SE", "LoRa_Relay",
        "MeshPoint v2", "CryptoPhone", "SatSleeve",
        "QuietPhone X1", "Phantom Node v3",
    ]

    def __init__(self) -> None:
        self.active_ghosts: list[dict] = []
        self.base_lat = 55.7558
        self.base_lon = 37.6173
        self._generation_count = 0

    async def generate_ghost_swarm(self, count: int = 5000) -> list[dict]:
        """Create synthetic decoy agents for defensive simulation."""
        if count <= 0:
            raise ValueError("count must be positive")
        if count > 100_000:
            raise ValueError("count exceeds safety limit (100k)")

        logger.warning(
            "[DECOY_SIM] Генерация %s синтетических агентов для defensive-симуляции.",
            count,
        )

        swarm: list[dict] = []
        now = time.monotonic()
        for _ in range(count):
            swarm.append({
                "id": str(uuid4()),
                "lat": self.base_lat + random.uniform(-0.2, 0.2),
                "lon": self.base_lon + random.uniform(-0.2, 0.2),
                "fake_imsi": f"25099{random.randint(1000000000, 9999999999)}",
                "simulated_device": random.choice(self.DEVICE_POOL),
                "signal_strength": random.randint(-90, -30),
                "timestamp": now,
            })
            # Yield to event loop every 1000 items
            if len(swarm) % 1000 == 0:
                await asyncio.sleep(0)

        self.active_ghosts = swarm
        self._generation_count += 1
        logger.info(
            "[DECOY_SIM] Сгенерировано %s синтетических сигнатур (batch #%d).",
            len(self.active_ghosts),
            self._generation_count,
        )
        return self.active_ghosts

    async def broadcast_ghosts(self, interval: int = 10) -> None:
        """Emit local debug heartbeat for active synthetic signatures."""
        while True:
            if self.active_ghosts:
                ghost = random.choice(self.active_ghosts)
                logger.debug("[DECOY_SIM] heartbeat ghost=%s", ghost["id"])
            await asyncio.sleep(interval)

    @property
    def stats(self) -> dict:
        """Current poisoner statistics."""
        return {
            "active_ghosts": len(self.active_ghosts),
            "generation_count": self._generation_count,
            "base_coordinates": {"lat": self.base_lat, "lon": self.base_lon},
        }


poison_engine = SyndromePoisoner()
