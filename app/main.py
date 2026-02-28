import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.alerting.routes import router as alerting_router
from app.diagnostics.routes import router as diagnostics_router
from app.osint.routes import router as osint_router
from app.threat_intel.routes import router as threat_intel_router
from app.tracker.routes import router as tracker_router

logger = logging.getLogger(__name__)


# OpenTelemetry setup
JAEGER_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger-collector:4317")
resource = Resource.create({"service.name": "playe-api-gateway"})
tracer_provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(endpoint=JAEGER_ENDPOINT, insecure=True)
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(tracer_provider)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.warning("[SYSTEM] Инициализация PLAYE STUDIO PRO v5.0 (FastAPI Core)")
    yield
    logger.warning("[SYSTEM] Остановка систем...")


app = FastAPI(
    title="PLAYE CTI COMMAND CENTER",
    description="Military-Grade API for Threat Intelligence & Field Operations",
    version="5.0.0",
    lifespan=lifespan,
)

# ═══ CORS — env-based, no wildcard with credentials ═══
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "https://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-API-KEY"],
)

app.include_router(tracker_router, prefix="/api/v1/tracker", tags=["Field Tracker"])
app.include_router(diagnostics_router, prefix="/api/v1/diagnostics", tags=["Cyber-Physical Scanners"])
app.include_router(threat_intel_router, prefix="/api/v1/threat_intel", tags=["OSINT & Attribution Kraken"])
app.include_router(alerting_router, prefix="/api/v1/alerting", tags=["SOAR & Alerts"])
app.include_router(osint_router, prefix="/api/v1/osint", tags=["OSINT"])

# ═══ Security Headers Middleware ═══
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' wss: ws:; "
            "font-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)

# ═══ Security Headers Middleware ═══
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response: StarletteResponse = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src \'self\'; script-src \'self\'; "
            "style-src \'self\' \'unsafe-inline\'; "
            "img-src \'self\' data: https:; "
            "connect-src \'self\' wss: https:; "
            "font-src \'self\'; object-src \'none\'"
        )
        # Remove tech fingerprint headers
        response.headers.pop("server", None)
        response.headers.pop("x-powered-by", None)
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Automatic tracing
FastAPIInstrumentor.instrument_app(app)
HTTPXInstrumentor().instrument()


@app.get("/health", tags=["System"])
async def health_check():
    """Проверка состояния орбитального ядра"""
    return {"status": "online", "core": "FastAPI"}


@app.get("/ready", tags=["System"])
async def readiness_check():
    """K8s readiness probe"""
    return {"status": "ready", "version": "5.0.0"}
