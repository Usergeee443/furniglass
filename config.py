import os
from pathlib import Path
from urllib.parse import urlparse

# Lokal: pip install python-dotenv — .env yuklanadi.
# Render: o'zgaruvchilar dashboard Environment da; dotenv bo'lmasa ham ishlaydi.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass


def _postgres_host_valid(url: str) -> bool:
    """
    Tashqi URL: hostname odatda ...postgres.render.com (nuqta bilan).
    Render **Internal** PostgreSQL: hostname nuqtasiz bo'lishi mumkin (masalan dpg-xxxxx-a) —
    bu faqat Render tarmog'ida ishlaydi; Render RENDER=true muhit o'zgaruvchisini qo'yadi.
    """
    try:
        u = urlparse(url.replace("postgres://", "postgresql://", 1))
        host = (u.hostname or "").strip().lower()
        if not host:
            return False
        if host in ("localhost", "127.0.0.1", "::1"):
            return True
        if "." in host:
            return True
        # Render.com Web Service: ichki DNS (Internal Database URL)
        if (os.environ.get("RENDER") or "").lower() in ("true", "1", "yes"):
            if host.startswith("dpg-") and len(host) >= 10:
                return True
        return False
    except Exception:
        return False


class Config:
    # SECRET_KEY: productionda .env orqali majburiy qoldiring
    SECRET_KEY = os.environ.get("SECRET_KEY") or "furniglass-dev-only-sqlite"

    # Database: DATABASE_URL bo'lsa PostgreSQL, bo'lmasa lokal SQLite
    # USE_SQLITE=1 bo'lsa DATABASE_URL e'tiborsiz qoldiriladi (lokal test uchun).
    # Render ichida: "Internal Database URL" yoki tashqaridan "External Database URL" — hostname
    # to'liq bo'lishi kerak: dpg-xxx-a.<region>-postgres.render.com
    _use_sqlite = os.environ.get("USE_SQLITE", "").strip().lower() in ("1", "true", "yes")
    database_url = None if _use_sqlite else os.environ.get("DATABASE_URL")
    if not _use_sqlite and not (database_url or "").strip():
        raise ValueError(
            "USE_SQLITE=0 qilib qo'yilgan, lekin DATABASE_URL bo'sh. "
            ".env fayliga Render → PostgreSQL → External Database URL ni qo'ying."
        )
    SQLALCHEMY_ENGINE_OPTIONS = {}
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        if database_url.startswith("postgresql") and not _postgres_host_valid(database_url):
            raise ValueError(
                "DATABASE_URL hostname noto'liq yoki lokal muhitda ichki URL ishlatilmoqda. "
                "Lokal: External Database URL (hostname ...postgres.render.com) yoki USE_SQLITE=1. "
                "Render serverda: Internal yoki External URL to'liq bo'lishi kerak."
            )
        # SQLAlchemy: psycopg (v3) drayver — Python 3.13 / Render muvofiqligi
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        SQLALCHEMY_DATABASE_URI = database_url
        # PostgreSQL: ulanish havzasi — uzoq masofali PG uchun sekinlikni kamaytiradi
        if database_url.startswith("postgresql"):
            SQLALCHEMY_ENGINE_OPTIONS = {
                "pool_pre_ping": True,
                "pool_recycle": int(os.environ.get("SQLALCHEMY_POOL_RECYCLE", "280")),
                "pool_size": int(os.environ.get("SQLALCHEMY_POOL_SIZE", "5")),
                "max_overflow": int(os.environ.get("SQLALCHEMY_MAX_OVERFLOW", "10")),
            }
    else:
        basedir = os.path.abspath(os.path.dirname(__file__))
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(basedir, 'instance', 'furniglass.db')}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = "static/uploads"
    _max_upload_mb = int(os.environ.get("MAX_UPLOAD_MB", "32"))
    MAX_CONTENT_LENGTH = max(1, _max_upload_mb) * 1024 * 1024

    # Telegram — faqat .env dan (kodda token qolmadi)
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

    # Supabase Storage — rasmlar/fayllar bucketda (USE_SUPABASE_STORAGE=0 bo'lsa mahalliy disk)
    SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").strip() or None
    _supabase_key = (
        (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        or (os.environ.get("SUPABASE_KEY") or "").strip()
    )
    SUPABASE_KEY = _supabase_key or None
    SUPABASE_STORAGE_BUCKET = (os.environ.get("SUPABASE_STORAGE_BUCKET") or "media").strip() or "media"
    _sb_off = os.environ.get("USE_SUPABASE_STORAGE", "").strip().lower() in ("0", "false", "no")
    USE_SUPABASE_STORAGE = bool(SUPABASE_URL and SUPABASE_KEY) and not _sb_off
