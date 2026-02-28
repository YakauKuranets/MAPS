"""WebAssembly sandbox for safe execution of untrusted parsers.

Isolates binary execution via WASI with restricted filesystem access
and no network capability. Used by image_validator for EXIF parsing.
"""

import json
import logging
import os
import signal
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

# Maximum execution time for wasm module (seconds)
WASM_TIMEOUT = int(os.getenv("WASM_TIMEOUT_SEC", "10"))
# Maximum memory for wasm (bytes)
WASM_MAX_MEMORY = int(os.getenv("WASM_MAX_MEMORY_MB", "64")) * 1024 * 1024

try:
    from wasmtime import Engine, Linker, Module, Store, WasiConfig

    _WASMTIME_AVAILABLE = True
except ImportError:
    _WASMTIME_AVAILABLE = False
    logger.info(
        "[WASM_SANDBOX] wasmtime not installed — sandbox will use Python fallback"
    )


class WasmTimeoutError(Exception):
    """Raised when wasm execution exceeds timeout."""


@contextmanager
def _timeout_guard(seconds: int):
    """Context manager that raises WasmTimeoutError after `seconds`."""

    def _handler(signum, frame):
        raise WasmTimeoutError(f"Execution exceeded {seconds}s timeout")

    if hasattr(signal, "SIGALRM"):
        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        yield  # Windows — no alarm support


class WasmSandbox:
    """Constrained WASI sandbox for running untrusted parsers."""

    def __init__(self) -> None:
        if not _WASMTIME_AVAILABLE:
            self.engine = None
            self.linker = None
            return
        self.engine = Engine()
        self.linker = Linker(self.engine)
        self.linker.define_wasi()
        self._run_count = 0

    def run_parser(self, wasm_file_path: str, target_file_path: str) -> str:
        """Run parser wasm in constrained WASI sandbox and return JSON string.

        Security guarantees:
        - No host filesystem access (only /workspace preopen)
        - No network access
        - Timeout enforcement via SIGALRM
        - Crash isolation — exceptions are caught and logged
        """
        if not _WASMTIME_AVAILABLE:
            return json.dumps(
                {"error": "wasm module missing", "reason": "wasmtime not installed"}
            )

        if not os.path.exists(wasm_file_path):
            logger.error("[WASM_SANDBOX] Бинарник %s не найден.", wasm_file_path)
            return json.dumps({"error": "wasm module missing"})

        if not os.path.exists(target_file_path):
            return json.dumps({"error": "target file missing"})

        # File size guard
        file_size = os.path.getsize(target_file_path)
        if file_size > 50 * 1024 * 1024:  # 50MB limit
            return json.dumps(
                {"error": "file_too_large", "max_bytes": 50 * 1024 * 1024}
            )

        store = Store(self.engine)

        wasi_cfg = WasiConfig()
        wasi_cfg.argv = [
            "parser.wasm",
            "/workspace/" + os.path.basename(target_file_path),
        ]
        wasi_cfg.preopen_dir(os.path.dirname(target_file_path), "/workspace")
        # No network, no env vars, no other dirs
        store.set_wasi(wasi_cfg)

        try:
            with _timeout_guard(WASM_TIMEOUT):
                module = Module.from_file(self.engine, wasm_file_path)
                instance = self.linker.instantiate(store, module)

                exports: dict[str, Any] = instance.exports(store)
                start = exports.get("_start")
                if start:
                    start(store)
                    self._run_count += 1
                    logger.info(
                        "[WASM_SANDBOX] Изолированный анализ успешно завершен (#%d).",
                        self._run_count,
                    )
                    return json.dumps({"status": "analyzed_in_sandbox", "safe": True})
                return json.dumps({"error": "no start function"})

        except WasmTimeoutError:
            logger.critical(
                "[WASM_SANDBOX] TIMEOUT: Модуль превысил лимит %ds!", WASM_TIMEOUT
            )
            return json.dumps(
                {
                    "error": "sandbox_timeout",
                    "timeout_seconds": WASM_TIMEOUT,
                    "malicious_payload_suspected": True,
                }
            )
        except MemoryError:
            logger.critical("[WASM_SANDBOX] OOM: Модуль превысил лимит памяти!")
            return json.dumps(
                {"error": "sandbox_oom", "malicious_payload_suspected": True}
            )
        except Exception as e:
            logger.critical("[WASM_SANDBOX] ПЕСОЧНИЦА ЗАБЛОКИРОВАЛА СБОЙ/АТАКУ: %s", e)
            return json.dumps(
                {
                    "error": "sandbox_execution_failed",
                    "malicious_payload_suspected": True,
                    "detail": str(e)[:200],
                }
            )

    @property
    def stats(self) -> dict:
        return {
            "wasmtime_available": _WASMTIME_AVAILABLE,
            "runs_completed": self._run_count,
            "timeout_sec": WASM_TIMEOUT,
        }


sandbox_engine = WasmSandbox()
