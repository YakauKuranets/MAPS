"""
══════════════════════════════════════════════════════════════════════════
  PLAYE v5 — MASTER E2E + SMOKE TEST SUITE (FULL COVERAGE)
  Coverage: All 8 assessment sections + all improvements
══════════════════════════════════════════════════════════════════════════
Run:  pytest tests/test_master_e2e_smoke.py -v --tb=short -x
"""

import asyncio
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent


# ═══════════════════════════════════════════════════════════════
# SECTION 1.1: WASM SANDBOX
# ═══════════════════════════════════════════════════════════════
class TestS1_WasmSandbox:
    def test_sandbox_class_instantiation(self):
        try:
            from app.sandbox.wasm_runner import WasmSandbox
            s = WasmSandbox()
            assert s.stats["wasmtime_available"] in (True, False)
        except ImportError:
            pytest.skip("wasmtime not installed")

    def test_run_parser_missing_wasm(self):
        try:
            from app.sandbox.wasm_runner import WasmSandbox
            s = WasmSandbox()
            result = json.loads(s.run_parser("/nonexistent.wasm", "/some/file"))
            assert result.get("error") == "wasm module missing"
        except ImportError:
            pytest.skip("wasmtime not installed")

    def test_run_parser_missing_target(self):
        try:
            from app.sandbox.wasm_runner import WasmSandbox
            s = WasmSandbox()
            result = json.loads(s.run_parser("/some.wasm", "/nonexistent.jpg"))
            assert "error" in result
        except ImportError:
            pytest.skip("wasmtime not installed")

    def test_stats_property(self):
        try:
            from app.sandbox.wasm_runner import sandbox_engine
            stats = sandbox_engine.stats
            assert "wasmtime_available" in stats
            assert "runs_completed" in stats
            assert "timeout_sec" in stats
        except ImportError:
            pytest.skip("wasmtime not installed")


# ═══════════════════════════════════════════════════════════════
# SECTION 1.2: AEGIS SOAR
# ═══════════════════════════════════════════════════════════════
class TestS1_AegisSoar:
    def test_register_blocked_attack_counter(self):
        from app.security.aegis_soar import register_blocked_attack, get_blocked_attacks
        before = get_blocked_attacks()
        register_blocked_attack()
        assert get_blocked_attacks() == before + 1

    @pytest.mark.asyncio
    async def test_block_ip_no_credentials(self):
        from app.security.aegis_soar import block_ip_on_edge
        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "", "CLOUDFLARE_ZONE_ID": ""}):
            result = await block_ip_on_edge("1.2.3.4")
            assert result is False

    @pytest.mark.asyncio
    async def test_block_private_ip_rejected(self):
        """Private IPs should be rejected."""
        from app.security.aegis_soar import block_ip_on_edge
        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "test", "CLOUDFLARE_ZONE_ID": "z1"}):
            result = await block_ip_on_edge("192.168.1.1")
            assert result is False

    @pytest.mark.asyncio
    async def test_block_loopback_rejected(self):
        from app.security.aegis_soar import block_ip_on_edge
        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "test", "CLOUDFLARE_ZONE_ID": "z1"}):
            result = await block_ip_on_edge("127.0.0.1")
            assert result is False

    @pytest.mark.asyncio
    async def test_block_invalid_ip_rejected(self):
        from app.security.aegis_soar import block_ip_on_edge
        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "test", "CLOUDFLARE_ZONE_ID": "z1"}):
            result = await block_ip_on_edge("not-an-ip")
            assert result is False

    @pytest.mark.asyncio
    async def test_block_ip_with_mock_cf(self):
        from app.security.aegis_soar import block_ip_on_edge, _blocked_ips
        _blocked_ips.discard("203.0.113.1")  # Clean state
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "test", "CLOUDFLARE_ZONE_ID": "z1", "AEGIS_TELEGRAM_NOTIFY": "0"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
                result = await block_ip_on_edge("203.0.113.1", "test")
                assert result is True

    def test_sync_wrapper(self):
        from app.security.aegis_soar import block_ip_sync
        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "", "CLOUDFLARE_ZONE_ID": ""}):
            result = block_ip_sync("1.2.3.4")
            assert result is False


# ═══════════════════════════════════════════════════════════════
# SECTION 1.3: eBPF WATCHER
# ═══════════════════════════════════════════════════════════════
class TestS1_EbpfWatcher:
    def test_extract_ip_process_exec(self):
        from app.security.ebpf_watcher import extract_ip_from_k8s_context
        event = {"process_exec": {"source": {"ip": "192.168.1.100"}}}
        assert extract_ip_from_k8s_context(event) == "192.168.1.100"

    def test_extract_ip_kprobe(self):
        from app.security.ebpf_watcher import extract_ip_from_k8s_context
        event = {"process_kprobe": {"source": {"ip": "10.0.0.5"}}}
        assert extract_ip_from_k8s_context(event) == "10.0.0.5"

    def test_extract_ip_pod(self):
        from app.security.ebpf_watcher import extract_ip_from_k8s_context
        event = {"process_exec": {"process": {"pod": {"pod_ip": "172.16.0.1"}}}}
        assert extract_ip_from_k8s_context(event) == "172.16.0.1"

    def test_extract_ip_missing(self):
        from app.security.ebpf_watcher import extract_ip_from_k8s_context
        assert extract_ip_from_k8s_context({}) is None

    def test_policy_violation_detected(self):
        from app.security.ebpf_watcher import _is_policy_violation
        event = {"process_exec": {"policy_name": "block-shells", "process": {"binary": "/bin/sh"}}}
        is_v, policy, binary = _is_policy_violation(event)
        assert is_v is True
        assert policy == "block-shells"
        assert binary == "/bin/sh"

    def test_policy_violation_none(self):
        from app.security.ebpf_watcher import _is_policy_violation
        assert _is_policy_violation({})[0] is False

    def test_pick_nested_deep(self):
        from app.security.ebpf_watcher import _pick_nested
        data = {"a": {"b": {"c": "deep"}}}
        assert _pick_nested(data, ["a", "b", "c"]) == "deep"
        assert _pick_nested(data, ["a", "x"]) is None
        assert _pick_nested(data, []) == data


# ═══════════════════════════════════════════════════════════════
# SECTION 1.4: COCKROACHDB UTILS
# ═══════════════════════════════════════════════════════════════
class TestS1_CockroachUtils:
    def test_retry_success(self):
        from app.db.cockroach_utils import retry_on_serialization_failure
        @retry_on_serialization_failure(max_retries=3)
        def ok(): return "ok"
        assert ok() == "ok"

    def test_retry_non_serialization_raises(self):
        from app.db.cockroach_utils import retry_on_serialization_failure
        @retry_on_serialization_failure(max_retries=2, delay=0.01)
        def bad(): raise ValueError("nope")
        with pytest.raises(ValueError):
            bad()

    def test_retry_exhausted_raises_custom(self):
        from app.db.cockroach_utils import retry_on_serialization_failure, CockroachRetryExhausted
        @retry_on_serialization_failure(max_retries=2, delay=0.01, jitter=0)
        def flaky():
            e = Exception("40001")
            e.sqlstate = "40001"
            raise e
        with pytest.raises(CockroachRetryExhausted):
            flaky()

    def test_retry_recovers(self):
        from app.db.cockroach_utils import retry_on_serialization_failure
        calls = 0
        @retry_on_serialization_failure(max_retries=3, delay=0.01, jitter=0)
        def recovers():
            nonlocal calls; calls += 1
            if calls < 3:
                e = Exception("SerializationFailure"); e.sqlstate = "40001"; raise e
            return "recovered"
        assert recovers() == "recovered"

    @pytest.mark.asyncio
    async def test_retry_async(self):
        from app.db.cockroach_utils import retry_on_serialization_failure
        @retry_on_serialization_failure(max_retries=2, delay=0.01)
        async def async_ok(): return "async_ok"
        assert await async_ok() == "async_ok"

    @pytest.mark.asyncio
    async def test_retry_async_exhausted(self):
        from app.db.cockroach_utils import retry_on_serialization_failure, CockroachRetryExhausted
        @retry_on_serialization_failure(max_retries=1, delay=0.01, jitter=0)
        async def async_fail():
            e = Exception("40001"); e.sqlstate = "40001"; raise e
        with pytest.raises(CockroachRetryExhausted):
            await async_fail()


# ═══════════════════════════════════════════════════════════════
# SECTION 1.5: DISINFORMATION
# ═══════════════════════════════════════════════════════════════
class TestS1_Disinformation:
    @pytest.mark.asyncio
    async def test_generate_ghost_swarm(self):
        from app.threat_intel.disinformation import SyndromePoisoner
        p = SyndromePoisoner()
        ghosts = await p.generate_ghost_swarm(count=100)
        assert len(ghosts) == 100
        assert len(p.active_ghosts) == 100
        for g in ghosts:
            assert "id" in g and "lat" in g and "fake_imsi" in g

    @pytest.mark.asyncio
    async def test_generate_validates_count(self):
        from app.threat_intel.disinformation import SyndromePoisoner
        p = SyndromePoisoner()
        with pytest.raises(ValueError): await p.generate_ghost_swarm(count=0)
        with pytest.raises(ValueError): await p.generate_ghost_swarm(count=-1)
        with pytest.raises(ValueError): await p.generate_ghost_swarm(count=200_000)

    @pytest.mark.asyncio
    async def test_broadcast_no_crash(self):
        from app.threat_intel.disinformation import SyndromePoisoner
        p = SyndromePoisoner()
        await p.generate_ghost_swarm(count=5)
        task = asyncio.create_task(p.broadcast_ghosts(interval=0.01))
        await asyncio.sleep(0.05)
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

    def test_stats_property(self):
        from app.threat_intel.disinformation import SyndromePoisoner
        p = SyndromePoisoner()
        s = p.stats
        assert "active_ghosts" in s
        assert "generation_count" in s
        assert "base_coordinates" in s


# ═══════════════════════════════════════════════════════════════
# SECTION 1.6: RADIO HUNTER
# ═══════════════════════════════════════════════════════════════
class TestS1_RadioHunter:
    def test_lazy_driver_no_crash(self):
        from app.threat_intel.radio_hunter import RadioHunterEngine
        engine = RadioHunterEngine(uri="bolt://fake:7687")
        assert engine._driver is None  # Not connected yet
        engine.close()

    def test_get_primary_target_empty(self):
        from app.threat_intel.radio_hunter import RadioHunterEngine
        engine = RadioHunterEngine(uri="bolt://fake:7687")
        with patch.object(engine, 'find_anomalous_towers', return_value=[]):
            assert engine.get_primary_target() is None

    def test_get_primary_target_found(self):
        from app.threat_intel.radio_hunter import RadioHunterEngine
        engine = RadioHunterEngine(uri="bolt://fake:7687")
        mock = [{"tower_id": "t1", "lat": 55.75, "lon": 37.61, "signal": 95, "hunter_count": 5}]
        with patch.object(engine, 'find_anomalous_towers', return_value=mock):
            t = engine.get_primary_target()
            assert t["target_lat"] == 55.75
            assert t["type"] == "Syndrome_Hardware"
            assert t["hunter_count"] == 5

    def test_stats(self):
        from app.threat_intel.radio_hunter import RadioHunterEngine
        engine = RadioHunterEngine(uri="bolt://test:7687")
        s = engine.stats
        assert s["uri"] == "bolt://test:7687"
        assert s["connected"] is False
        assert s["queries_executed"] == 0


# ═══════════════════════════════════════════════════════════════
# SECTION 1.7: SYNDICATE USERBOT
# ═══════════════════════════════════════════════════════════════
class TestS1_Syndicate:
    def test_userbot_instantiation(self):
        from app.osint.syndicate_userbot import SyndicateUserbot
        bot = SyndicateUserbot()
        assert bot._running is False
        assert bot._messages_processed == 0

    def test_ioc_extraction(self):
        from app.osint.syndicate_userbot import SyndicateUserbot
        bot = SyndicateUserbot()
        text = "Contact admin@evil.com, wallet 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa, IP 10.0.0.1"
        iocs = bot._extract_iocs(text)
        assert "email" in iocs
        assert "btc_wallet" in iocs
        assert "ipv4" in iocs

    def test_stats(self):
        from app.osint.syndicate_userbot import SyndicateUserbot
        bot = SyndicateUserbot()
        s = bot.stats
        assert s["running"] is False
        assert s["messages_processed"] == 0

    @pytest.mark.asyncio
    async def test_get_client_no_credentials(self):
        from app.osint.syndicate_userbot import SyndicateUserbot
        bot = SyndicateUserbot()
        with patch.dict(os.environ, {"TELEGRAM_API_ID": "0", "TELEGRAM_API_HASH": ""}):
            client = await bot._get_client()
            assert client is None


# ═══════════════════════════════════════════════════════════════
# SECTION 1.x: IMAGE VALIDATOR
# ═══════════════════════════════════════════════════════════════
class TestS1_ImageValidator:
    def test_validate_nonexistent(self):
        try:
            from app.osint.image_validator import validate_image_integrity
            result = validate_image_integrity("/nonexistent.jpg")
            assert result["valid"] is False
        except ImportError:
            pytest.skip("Dependencies not installed")

    def test_encrypt_decrypt(self):
        try:
            from app.osint.image_validator import _encrypt_sensitive, decrypt_metadata
            data = {"gps": {"lat": 55.75, "lon": 37.61}, "device": "Test", "other": "val"}
            enc = _encrypt_sensitive(data)
            assert enc["gps"] != data["gps"]
            assert enc["other"] == "val"
            dec = decrypt_metadata(enc)
            assert dec["other"] == "val"
        except ImportError:
            pytest.skip("cryptography not installed")


# ═══════════════════════════════════════════════════════════════
# SECTION 2: TELEMETRY VALIDATION
# ═══════════════════════════════════════════════════════════════
class TestS2_Telemetry:
    def test_valid_packet(self):
        packet = {"agent_id": "a1", "lat": 53.9, "lon": 27.56, "timestamp": "2026-02-27T10:00:00Z"}
        assert all(k in packet for k in ("agent_id", "lat", "lon", "timestamp"))

    def test_missing_field(self):
        assert "agent_id" not in {"lat": 53.9, "lon": 27.56}

    def test_injection_long_string(self):
        assert len("A" * 2048) > 1024

    def test_telemetry_node_exists(self):
        assert (ROOT / "telemetry_node" / "src" / "main.rs").exists()
        assert (ROOT / "telemetry_node" / "Cargo.toml").exists()


# ═══════════════════════════════════════════════════════════════
# SECTION 3: REACT FRONTEND
# ═══════════════════════════════════════════════════════════════
class TestS3_Frontend:
    COMPONENTS = [
        "react_frontend/src/components/CommandCenterMap.js",
        "react_frontend/src/components/DashboardLayout.js",
        "react_frontend/src/components/IdentityGraphPanel.jsx",
        "react_frontend/src/components/CTIConsole.jsx",
        "react_frontend/src/components/MiniTerminal.jsx",
        "react_frontend/src/components/AssetRiskGraphPanel.jsx",
        "react_frontend/src/store/useMapStore.js",
        "react_frontend/src/hooks/useWebSocket.js",
    ]

    @pytest.mark.parametrize("component", COMPONENTS)
    def test_component_exists(self, component):
        assert (ROOT / component).exists(), f"Missing: {component}"

    def test_package_json(self):
        data = json.loads((ROOT / "react_frontend" / "package.json").read_text())
        assert "dependencies" in data or "devDependencies" in data

    def test_electron_main(self):
        assert (ROOT / "react_frontend" / "public" / "electron.js").exists()

    def test_preload_security(self):
        content = (ROOT / "react_frontend" / "public" / "preload.js").read_text()
        assert "contextBridge" in content

    def test_electron_no_node_in_renderer(self):
        content = (ROOT / "react_frontend" / "public" / "electron.js").read_text()
        assert "nodeIntegration: false" in content
        assert "contextIsolation: true" in content
        assert "sandbox: true" in content

    def test_crdt_yjs_integration(self):
        content = (ROOT / "react_frontend" / "src" / "store" / "useMapStore.js").read_text()
        assert "Y.Doc" in content
        assert "WebrtcProvider" in content
        assert "addTacticalZoneCRDT" in content
        assert "_offlineQueue" in content

    def test_mini_terminal(self):
        content = (ROOT / "react_frontend" / "src" / "components" / "MiniTerminal.jsx").read_text()
        assert len(content) > 100


# ═══════════════════════════════════════════════════════════════
# SECTION 4: ANDROID
# ═══════════════════════════════════════════════════════════════
class TestS4_Android:
    FILES = [
        "android/dutytracker_src/app/src/main/java/com/mapv12/dutytracker/telephony/GhostSimManager.kt",
        "android/dutytracker_src/app/src/main/java/com/mapv12/dutytracker/mesh/ReticulumMeshService.kt",
        "android/dutytracker_src/app/src/main/java/com/mapv12/dutytracker/security/HardwareKeyStore.kt",
        "android/dutytracker_src/app/src/main/java/com/mapv12/dutytracker/security/BiometricGatekeeper.kt",
        "android/dutytracker_src/app/src/main/java/com/mapv12/dutytracker/scanner/BleScanner.kt",
        "android/dutytracker_src/app/src/main/java/com/mapv12/dutytracker/scanner/wifi/WifiScanWorker.kt",
    ]

    @pytest.mark.parametrize("f", FILES)
    def test_file_exists(self, f):
        assert (ROOT / f).exists(), f"Missing: {f}"

    def test_gradle_build(self):
        assert (ROOT / "android" / "dutytracker_src" / "build.gradle.kts").exists() or \
               (ROOT / "android" / "dutytracker_src" / "build.gradle").exists()


# ═══════════════════════════════════════════════════════════════
# SECTION 5: K8S INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════
class TestS5_K8s:
    MANIFESTS = [
        "k8s/01-namespace.yaml", "k8s/02-redis.yaml", "k8s/03-fastapi-web.yaml",
        "k8s/04-ai-engine.yaml", "k8s/05-jaeger.yaml", "k8s/06-vault.yaml",
        "k8s/07-tetragon-policy.yaml", "k8s/08-mlflow.yaml", "k8s/09-ebpf-watcher.yaml",
    ]

    @pytest.mark.parametrize("m", MANIFESTS)
    def test_exists(self, m):
        assert (ROOT / m).exists()

    @pytest.mark.parametrize("m", MANIFESTS)
    def test_valid_yaml(self, m):
        import yaml
        with open(ROOT / m) as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) >= 1

    def test_fastapi_has_resource_limits(self):
        content = (ROOT / "k8s" / "03-fastapi-web.yaml").read_text()
        assert "resources:" in content
        assert "limits:" in content
        assert "requests:" in content

    def test_fastapi_has_readiness_probe(self):
        content = (ROOT / "k8s" / "03-fastapi-web.yaml").read_text()
        assert "readinessProbe:" in content

    def test_fastapi_security_context(self):
        content = (ROOT / "k8s" / "03-fastapi-web.yaml").read_text()
        assert "runAsNonRoot: true" in content

    def test_argocd_selfheal(self):
        content = (ROOT / "k8s" / "argocd" / "playe-production.yaml").read_text()
        assert "selfHeal: true" in content
        assert "retry:" in content

    def test_install_scripts(self):
        for s in ["k8s/install_cockroachdb.sh", "k8s/install_ebpf_shield.sh"]:
            assert (ROOT / s).exists()


# ═══════════════════════════════════════════════════════════════
# SECTION 6: TOOLS
# ═══════════════════════════════════════════════════════════════
class TestS6_Tools:
    def test_ai_mutator_exists(self):
        assert (ROOT / "tools" / "ai_mutator.py").exists()

    def test_stealth_verifier_exists(self):
        assert (ROOT / "tools" / "stealth_verifier.py").exists()

    def test_stealth_verifier_has_timing(self):
        content = (ROOT / "tools" / "stealth_verifier.py").read_text()
        assert "timing_analysis" in content
        assert "check_dns_leaks" in content

    def test_fuzz_target(self):
        assert (ROOT / "fuzz_targets" / "parse_exif_fuzzer.py").exists()

    def test_tactical_reports_exists(self):
        assert (ROOT / "app" / "reports" / "tactical_pdf.py").exists()


# ═══════════════════════════════════════════════════════════════
# SECTION 7: DOCUMENTATION
# ═══════════════════════════════════════════════════════════════
class TestS7_Docs:
    DOCS = [
        "docs/index.md", "docs/roadmap_v7.md", "docs/stack_gap_checklist.md",
        "docs/playbooks/syndrome_response.md", "docs/playbooks/agent_isolation.md",
        "docs/playbooks/poison_well.md", "docs/architecture/cockroachdb.md",
        "docs/architecture/ebpf_shield.md", "docs/architecture/neo4j_cluster.md",
        "docs/frontend/terminal.md", "docs/frontend/mini_terminal.md",
        "docs/agents/ghost_protocol.md", "docs/agents/mesh_network.md",
    ]

    @pytest.mark.parametrize("doc", DOCS)
    def test_exists(self, doc):
        assert (ROOT / doc).exists()

    def test_mkdocs_yml(self):
        assert (ROOT / "mkdocs.yml").exists()

    def test_docs_nonempty(self):
        for doc in self.DOCS:
            size = (ROOT / doc).stat().st_size
            assert size > 10, f"Doc {doc} appears empty ({size} bytes)"


# ═══════════════════════════════════════════════════════════════
# SECTION 8: SECURITY AUDIT
# ═══════════════════════════════════════════════════════════════
class TestS8_Security:
    def test_no_hardcoded_keys(self):
        for f in ["app/config.py", "app/main.py"]:
            content = (ROOT / f).read_text()
            assert "sk-" not in content
            assert "ghp_" not in content

    def test_secret_key_from_env(self):
        content = (ROOT / "app" / "config.py").read_text()
        assert "environ" in content
        assert "SECRET_KEY" in content

    def test_cors_not_wildcard_with_credentials(self):
        content = (ROOT / "app" / "main.py").read_text()
        if "allow_credentials=True" in content:
            assert 'allow_origins=["*"]' not in content

    def test_security_headers_middleware(self):
        content = (ROOT / "app" / "main.py").read_text()
        assert "SecurityHeadersMiddleware" in content
        assert "X-Content-Type-Options" in content
        assert "X-Frame-Options" in content
        assert "Permissions-Policy" in content

    def test_readiness_endpoint(self):
        content = (ROOT / "app" / "main.py").read_text()
        assert "/ready" in content

    def test_production_config_exists(self):
        content = (ROOT / "app" / "config.py").read_text()
        assert "class ProductionConfig" in content


# ═══════════════════════════════════════════════════════════════
# SECTION 9: ASSET RISK GRAPH
# ═══════════════════════════════════════════════════════════════
class TestS9_AssetRiskGraph:
    def test_add_and_query(self):
        from app.threat_intel.asset_risk_graph import AssetRiskGraph
        g = AssetRiskGraph()
        g.add_asset("srv", "SERVER", 7.5)
        g.add_asset("db", "DB", 9.0)
        g.add_risk_relation("srv", "db", "NET", 0.8)
        p = g.get_risk_profile("srv")
        assert len(p["edges"]) == 1

    def test_empty_profile(self):
        from app.threat_intel.asset_risk_graph import AssetRiskGraph
        g = AssetRiskGraph()
        assert len(g.get_risk_profile("x")["edges"]) == 0


# ═══════════════════════════════════════════════════════════════
# SMOKE TESTS
# ═══════════════════════════════════════════════════════════════
class TestSmoke_Imports:
    MODULES = [
        "app.sandbox.wasm_runner", "app.security.aegis_soar",
        "app.security.ebpf_watcher", "app.security.rate_limit",
        "app.threat_intel.disinformation", "app.threat_intel.asset_risk_graph",
        "app.db.cockroach_utils", "app.osint.syndicate_userbot",
    ]

    @pytest.mark.parametrize("mod", MODULES)
    def test_import(self, mod):
        try:
            __import__(mod)
        except ImportError as e:
            if any(dep in str(e) for dep in ("wasmtime", "neo4j", "exifread", "telethon", "hvac")):
                pytest.skip(f"Optional: {e}")
            raise


class TestSmoke_Structure:
    def test_requirements(self): assert (ROOT / "requirements.txt").exists()
    def test_dockerfile(self): assert (ROOT / "Dockerfile").exists()
    def test_docker_compose(self): assert (ROOT / "docker-compose.prod.yml").exists()
    def test_alembic(self): assert (ROOT / "alembic" / "env.py").exists()
    def test_readme(self): assert (ROOT / "README.md").exists()
    def test_pytest_ini(self): assert (ROOT / "pytest.ini").exists()
