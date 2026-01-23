# Render.com'ga Deploy Qilish Qo'llanmasi

## 1. Render.com'da Yangi Web Service Yaratish

1. [Render.com](https://render.com) saytiga kiring va account yarating
2. Dashboard'da "New +" tugmasini bosing
3. "Web Service" ni tanlang
4. GitHub repository'ni ulang yoki manual deploy qiling

## 2. Environment Variables (Muhim!)

Render dashboard'da quyidagi environment variables'ni qo'shing:

```
SECRET_KEY=your-very-secret-key-here-minimum-32-characters
DATABASE_URL=postgresql://user:password@host:port/database (Render PostgreSQL uchun avtomatik)
PYTHON_VERSION=3.11.0
```

**SECRET_KEY** uchun quyidagi buyruqni ishlatib, xavfsiz key yarating:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## 3. Database (PostgreSQL)

Render.com'da PostgreSQL database yaratish:

1. Dashboard'da "New +" → "PostgreSQL" ni tanlang
2. Database nomini kiriting (masalan: `furniglass-db`)
3. Plan tanlang (Free plan mavjud)
4. Database yaratilgandan keyin, `DATABASE_URL` ni environment variables'ga qo'shing

## 4. Build va Start Commands

Render dashboard'da quyidagi buyruqlarni kiriting:

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
gunicorn app:app
```

## 5. Static Files va Media Files

**Muhim:** Render.com'da static files va media files uchun quyidagilarni qiling:

1. **Static Files** - `static/` papkasi avtomatik serve qilinadi
2. **Media Files** - Upload qilingan fayllar uchun Render Disk Storage yoki S3 ishlatish tavsiya etiladi

**Tavsiya:** Production'da media files uchun AWS S3 yoki Cloudinary ishlatish yaxshiroq.

## 6. Deploy Qilish

1. GitHub repository'ni ulang
2. Branch tanlang (odatda `main` yoki `master`)
3. "Create Web Service" tugmasini bosing
4. Render avtomatik build va deploy qiladi

## 7. Database Migration

Birinchi marta deploy qilgandan keyin, database migration qilish kerak:

1. Render dashboard'da "Shell" ni oching
2. Quyidagi buyruqni ishlating:
```bash
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

Yoki app.py ichida avtomatik migration mavjud bo'lsa, u ishlaydi.

## 8. Admin Account Yaratish

Birinchi marta deploy qilgandan keyin, admin account yaratish:

1. Render dashboard'da "Shell" ni oching
2. Quyidagi buyruqni ishlating:
```python
python -c "from app import app, db; from models import Admin; from werkzeug.security import generate_password_hash; app.app_context().push(); admin = Admin(username='admin', password_hash=generate_password_hash('your-password')); db.session.add(admin); db.session.commit(); print('Admin created!')"
```

## 9. Troubleshooting

### Port Error
Agar port xatosi bo'lsa, `Procfile` da `gunicorn app:app` ishlatilganligini tekshiring.

### Database Connection Error
- `DATABASE_URL` to'g'ri formatda ekanligini tekshiring
- PostgreSQL URL `postgresql://` bilan boshlanishi kerak (Render avtomatik `postgres://` ni `postgresql://` ga o'zgartiradi)

### Static Files Not Loading
- `static/` papkasi repository'da borligini tekshiring
- Flask'ning static files konfiguratsiyasini tekshiring

## 10. Monitoring

Render dashboard'da quyidagilarni kuzatishingiz mumkin:
- Logs
- Metrics
- Environment variables
- Database connections

## 11. Custom Domain

Render.com'da custom domain qo'shish:
1. Dashboard'da service'ni oching
2. "Settings" → "Custom Domains" ga o'ting
3. Domain'ni qo'shing va DNS sozlamalarini qiling

---

**Eslatma:** Free plan'da service uxlab qolishi mumkin (15 daqiqadan keyin). Production uchun paid plan tavsiya etiladi.
