import os
from urllib.parse import urlparse

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'furniglass-secret-key-2025'
    
    # Database URL - Render.com PostgreSQL yoki SQLite
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # PostgreSQL URL ni to'g'ri formatlash (Render.com uchun)
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        # SQLite uchun local development
        basedir = os.path.abspath(os.path.dirname(__file__))
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(basedir, "instance", "furniglass.db")}'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or ''
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID') or ''

