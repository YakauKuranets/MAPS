"""WSGI entrypoint for production deployment.

Usage:
    gunicorn -c deploy/gunicorn.conf.py wsgi:app
    # or
    uvicorn app.main:app --host 0.0.0.0 --port 8000  (FastAPI)
"""

from env_loader import load_dotenv_like
load_dotenv_like()

from app import create_app  # noqa: E402
from app.config import ProductionConfig  # noqa: E402

app = create_app(ProductionConfig)
