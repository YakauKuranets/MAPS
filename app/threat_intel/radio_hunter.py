"""Radio hunter anomaly detector based on Neo4j graph signals."""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class RadioHunterEngine:
    """Detects anomalous cell towers via Neo4j graph analysis."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://playe-neo4j-cluster:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self._driver = None
        self._query_count = 0

    @property
    def driver(self):
        """Lazy Neo4j driver — only connects on first use."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_lifetime=3600,
                connection_acquisition_timeout=10,
            )
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def health_check(self) -> bool:
        """Verify Neo4j connectivity."""
        try:
            self.driver.verify_connectivity()
            return True
        except Exception as exc:
            logger.warning("[RADIO_HUNTER] Neo4j health check failed: %s", exc)
            return False

    def find_anomalous_towers(
        self,
        min_signal: int = 90,
        min_hunters: int = 3,
        limit: int = 10,
    ) -> List[Dict]:
        """Find cell towers with anomalous characteristics.

        Args:
            min_signal: Minimum signal strength threshold (suspicious if too high)
            min_hunters: Minimum number of distinct agents that intercepted the tower
            limit: Max results to return
        """
        query = """
        MATCH (agent:Operative)-[r:INTERCEPTED_SIGNAL]->(tower:CellNode)
        WHERE tower.signal_strength > $min_signal 
          AND tower.registered_provider = 'UNKNOWN'
        WITH tower,
             count(DISTINCT agent) as hunter_count,
             collect(r.timestamp) as timestamps
        WHERE hunter_count >= $min_hunters
        RETURN tower.id as tower_id,
               tower.location_lat as lat,
               tower.location_lon as lon,
               tower.mac_address as mac,
               tower.signal_strength as signal,
               hunter_count,
               size(timestamps) as intercept_count
        ORDER BY hunter_count DESC, signal DESC
        LIMIT $limit
        """
        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    min_signal=min_signal,
                    min_hunters=min_hunters,
                    limit=limit,
                )
                suspects = [record.data() for record in result]
                self._query_count += 1
                if suspects:
                    logger.warning(
                        "[RADIO_HUNTER] Обнаружено %s подозрительных узлов (query #%d)",
                        len(suspects),
                        self._query_count,
                    )
                else:
                    logger.info("[RADIO_HUNTER] Аномальных узлов не найдено")
                return suspects
        except Exception as exc:
            logger.error("[RADIO_HUNTER] Query failed: %s", exc)
            return []

    def get_primary_target(self) -> Optional[Dict]:
        """Get highest-priority suspicious tower with coordinates."""
        suspects = self.find_anomalous_towers()
        if not suspects:
            return None

        target = suspects[0]
        logger.warning(
            "[RADIO_HUNTER] Координаты цели переданы в Командный Центр: %s, %s",
            target.get("lat"),
            target.get("lon"),
        )
        return {
            "target_lat": target.get("lat"),
            "target_lon": target.get("lon"),
            "signal_strength": target.get("signal"),
            "hunter_count": target.get("hunter_count"),
            "type": "Syndrome_Hardware",
        }

    @property
    def stats(self) -> dict:
        return {
            "uri": self.uri,
            "connected": self._driver is not None,
            "queries_executed": self._query_count,
        }


hunter_engine = RadioHunterEngine()
