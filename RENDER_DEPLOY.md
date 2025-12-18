# Render.com Deployment Guide

Bu loyihani Render.com ga deploy qilish uchun qo'llanma.

## 1. GitHub ga Push qilish

Avval loyihani GitHub ga push qiling:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-github-repo-url>
git push -u origin main
```

## 2. Render.com da Yangi Web Service Yaratish

1. [Render.com](https://render.com) ga kiring va sign up qiling
2. Dashboard dan "New +" tugmasini bosing
3. "Web Service" ni tanlang
4. GitHub repository ni ulang
5. Quyidagi sozlamalarni kiriting:

### Basic Settings:
- **Name**: `furniglass` (yoki istalgan nom)
- **Region**: `Singapore` (yoki yaqin region)
- **Branch**: `main` (yoki asosiy branch)
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app`

### Environment Variables:
Quyidagi environment variables ni qo'shing:

```
SECRET_KEY=your-secret-key-here-minimum-32-characters
DATABASE_URL=sqlite:///furniglass.db
RENDER=true
```

**SECRET_KEY** uchun quyidagi buyruqni ishlatib, xavfsiz key yarating:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Advanced Settings:
- **Instance Type**: `Free` (yoki `Starter` - $7/oy)
- **Auto-Deploy**: `Yes` (GitHub ga push qilganda avtomatik deploy)

## 3. Database Migration

Loyiha birinchi marta ishga tushganda, `app.py` ichidagi migration kodlari avtomatik ishlaydi va:
- Database yaratiladi
- Kerakli jadvallar yaratiladi
- Default admin user yaratiladi (username: `admin`, password: `admin123`)
- Default exchange rate yaratiladi (1 USD = 12000 UZS)

## 4. Static Files va Uploads

Render.com da static files uchun:
- `static/uploads/` papkasi avtomatik saqlanadi
- Lekin production da yuklangan rasmlar diskda saqlanadi (ephemeral storage)
- **Tavsiya**: Production da rasmlarni cloud storage (AWS S3, Cloudinary) ga yuklash

## 5. Admin Panel

Deploy qilingandan keyin:
- Admin panel: `https://your-app.onrender.com/admin`
- Default login: `admin` / `admin123`
- **Muhim**: Birinchi login qilgandan keyin parolni o'zgartiring!

## 6. Environment Variables (Production)

Production uchun quyidagi environment variables ni sozlang:

```
SECRET_KEY=<xavfsiz-secret-key>
DATABASE_URL=sqlite:///furniglass.db
RENDER=true
FLASK_ENV=production
```

## 7. PostgreSQL (Ixtiyoriy, Tavsiya)

Production uchun PostgreSQL ishlatish tavsiya qilinadi:

1. Render.com da "New PostgreSQL" yarating
2. Database URL ni oling
3. Environment variable da `DATABASE_URL` ni PostgreSQL URL ga o'zgartiring:
   ```
   DATABASE_URL=postgresql://user:password@host:port/dbname
   ```

**Eslatma**: PostgreSQL uchun `requirements.txt` ga `psycopg2-binary==2.9.9` qo'shing.

## 8. Troubleshooting

### App ishlamayapti:
- Logs ni tekshiring: Render Dashboard > Logs
- Build command to'g'ri ishlayotganini tekshiring
- Environment variables to'g'ri sozlanganini tekshiring

### Database xatolari:
- Migration kodlari ishlayotganini tekshiring
- Database file yaratilganini tekshiring

### Static files ko'rinmayapti:
- `static/uploads/` papkasi mavjudligini tekshiring
- File permissions ni tekshiring

## 9. Custom Domain (Ixtiyoriy)

1. Render Dashboard > Settings > Custom Domain
2. Domain ni qo'shing va DNS sozlamalarini bajarish

## 10. Monitoring

- Render.com avtomatik monitoring taqdim etadi
- Logs real-time ko'rinadi
- Metrics dashboard mavjud

---

**Muhim Eslatmalar:**
- Free tier da app 15 daqiqa ishlatilmasa uyquga ketadi
- Birinchi so'rov sekin bo'lishi mumkin (cold start)
- Static files ephemeral storage da saqlanadi (app restart qilinganda yo'qolishi mumkin)
- Production uchun cloud storage ishlatish tavsiya qilinadi

