"""
Fayl yuklash: mahalliy disk yoki Supabase Storage (S3-ga o'xshash bucket).
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask
    from werkzeug.datastructures import FileStorage


def _normalize_key(relative_path: str) -> str:
    return relative_path.replace("\\", "/").lstrip("/")


def public_storage_url(app: "Flask", relative_path: str) -> str:
    """Brauzer uchun rasm URL (Supabase yoki /uploads/...)."""
    if not relative_path:
        return ""
    p = relative_path.strip()
    if p.startswith("http://") or p.startswith("https://"):
        return p
    key = _normalize_key(p)
    if app.config.get("USE_SUPABASE_STORAGE"):
        base = (app.config.get("SUPABASE_URL") or "").rstrip("/")
        bucket = app.config.get("SUPABASE_STORAGE_BUCKET") or "media"
        return f"{base}/storage/v1/object/public/{bucket}/{key}"
    return f"/uploads/{key}"


def save_uploaded_file(app: "Flask", file_storage: "FileStorage", relative_path: str) -> None:
    """Werkzeug FileStorage ni disk yoki Supabase ga yozadi."""
    key = _normalize_key(relative_path)

    if app.config.get("USE_SUPABASE_STORAGE"):
        data = file_storage.read()
        content_type = file_storage.mimetype or "application/octet-stream"
        supabase = _get_supabase(app)
        bucket = app.config["SUPABASE_STORAGE_BUCKET"]
        supabase.storage.from_(bucket).upload(
            key,
            data,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return

    full = os.path.join(app.config["UPLOAD_FOLDER"], key)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    try:
        file_storage.seek(0)
    except Exception:
        try:
            file_storage.stream.seek(0)
        except Exception:
            pass
    file_storage.save(full)


def delete_uploaded_file(app: "Flask", relative_path: str) -> None:
    """Faylni disk yoki bucketdan o'chiradi."""
    if not relative_path:
        return
    key = _normalize_key(relative_path)

    if app.config.get("USE_SUPABASE_STORAGE"):
        try:
            supabase = _get_supabase(app)
            bucket = app.config["SUPABASE_STORAGE_BUCKET"]
            supabase.storage.from_(bucket).remove([key])
        except Exception:
            pass
        return

    full = os.path.join(app.config["UPLOAD_FOLDER"], key)
    try:
        if os.path.isfile(full):
            os.remove(full)
    except OSError:
        pass


def _get_supabase(app: "Flask"):
    from supabase import create_client

    url = app.config["SUPABASE_URL"]
    key = app.config["SUPABASE_KEY"]
    if not url or not key:
        raise RuntimeError("SUPABASE_URL va SUPABASE_KEY sozlanmagan")
    return create_client(url, key)
