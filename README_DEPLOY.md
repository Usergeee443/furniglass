# Furniglass.uz - Render.com Deploy Qo'llanmasi

## Tezkor Bosqichlar

### 1. GitHub'ga Push Qilish

```bash
git add .
git commit -m "Ready for Render deployment"
git push origin main
```

### 2. Render.com'da Service Yaratish

1. [Render.com](https://render.com) ga kiring
2. "New +" → "Web Service" ni tanlang
3. GitHub repository'ni ulang
4. Quyidagi sozlamalarni kiriting:

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
gunicorn app:app
```

### 3. Environment Variables

Render dashboard'da quyidagi environment variables'ni qo'shing:

```bash
SECRET_KEY=<xavfsiz-32-char-secret-key>
RENDER=true
```

**SECRET_KEY yaratish:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. PostgreSQL Database (Tavsiya)

1. Render dashboard'da "New +" → "PostgreSQL" ni tanlang
2. Database yaratilgandan keyin, `DATABASE_URL` avtomatik qo'shiladi
3. Agar qo'shilmagan bo'lsa, manual qo'shing

### 5. Deploy

"Create Web Service" tugmasini bosing va kutib turing.

### 6. Database Migration

Birinchi deploy'dan keyin, database avtomatik yaratiladi (app.py ichida migration kodlari mavjud).

### 7. Admin Account

Default admin account:
- Username: `admin`
- Password: `admin123`

**Muhim:** Birinchi login qilgandan keyin parolni o'zgartiring!

---

## Fayl Strukturasi

```
furniglass.uz/
├── app.py                 # Asosiy Flask app
├── config.py             # Konfiguratsiya
├── models.py             # Database modellar
├── requirements.txt      # Python dependencies
├── Procfile             # Render start command
├── runtime.txt          # Python versiyasi
├── render.yaml          # Render konfiguratsiyasi (ixtiyoriy)
├── .gitignore           # Git ignore fayllar
└── static/              # Static files
    └── uploads/         # Upload qilingan fayllar
```

---

## Muhim Eslatmalar

1. **Free Plan:** 15 daqiqadan keyin app uxlab qoladi
2. **Static Files:** `static/uploads/` papkasi ephemeral storage'da (restart qilinganda yo'qolishi mumkin)
3. **Production:** Cloud storage (S3, Cloudinary) ishlatish tavsiya etiladi
4. **Database:** PostgreSQL production uchun tavsiya etiladi

---

## Troubleshooting

### App ishlamayapti
- Logs ni tekshiring: Render Dashboard > Logs
- Environment variables to'g'ri ekanligini tekshiring

### Database xatolari
- `DATABASE_URL` to'g'ri formatda ekanligini tekshiring
- Migration kodlari ishlayotganini tekshiring

### Static files ko'rinmayapti
- `static/` papkasi repository'da borligini tekshiring
- File permissions ni tekshiring

---

## Qo'shimcha Ma'lumot

Batafsil qo'llanma uchun `DEPLOY.md` yoki `RENDER_DEPLOY.md` fayllarini ko'ring.
