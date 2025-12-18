# Furni Glass - Premium Mebel Veb-sayti

Furni Glass - Python Flask asosida yaratilgan premium mebel va ichki dizayn veb-sayti.

## O'rnatish

1. Virtual environment yaratish (tavsiya etiladi):
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# yoki
venv\Scripts\activate  # Windows
```

2. Kerakli paketlarni o'rnatish:
```bash
pip install -r requirements.txt
```

3. Loyihani ishga tushirish:
```bash
python app.py
```

4. Brauzerda oching: `http://localhost:5000`

## Admin Panel

Admin panelga kirish: `http://localhost:5000/admin`

**Default login:**
- Username: `admin`
- Password: `admin123`

⚠️ **Xavfsizlik uchun**: Production muhitida parolni o'zgartirishni unutmang!

## Loyiha Strukturasi

```
furniglass.uz/
├── app.py                 # Asosiy Flask aplikatsiyasi
├── config.py             # Konfiguratsiya
├── models.py             # Ma'lumotlar bazasi modellari
├── db.py                 # SQLAlchemy sozlash
├── requirements.txt      # Python paketlari
├── templates/           # HTML shablonlar
│   ├── base.html
│   ├── index.html
│   ├── products.html
│   ├── product_detail.html
│   ├── portfolio.html
│   ├── about.html
│   ├── why_us.html
│   ├── order.html
│   ├── contact.html
│   ├── faq.html
│   └── admin/
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── products.html
│       ├── product_form.html
│       ├── categories.html
│       ├── category_form.html
│       └── orders.html
└── static/              # Statik fayllar
    └── uploads/         # Yuklangan rasmlar
```

## Sahifalar

### Frontend
- **Home** (`/`) - Bosh sahifa
- **Mahsulotlar** (`/products`) - Mahsulotlar ro'yxati
- **Mahsulot detail** (`/product/<id>`) - Mahsulot haqida batafsil
- **Portfolio** (`/portfolio`) - Loyihalar
- **Biz haqimizda** (`/about`) - Kompaniya haqida
- **Nima uchun biz?** (`/why-us`) - Afzalliklarimiz
- **Buyurtma** (`/order`) - Individual buyurtma
- **Aloqa** (`/contact`) - Aloqa ma'lumotlari
- **FAQ** (`/faq`) - Ko'p so'raladigan savollar

### Admin Panel (`/admin`)
- Dashboard - Statistikalar
- Mahsulotlar - CRUD operatsiyalari
- Kategoriyalar - CRUD operatsiyalari
- Buyurtmalar - Buyurtmalarni ko'rish va boshqarish

## Ma'lumotlar Bazasi

Loyiha SQLite ma'lumotlar bazasidan foydalanadi. Birinchi marta ishga tushganda avtomatik yaratiladi.

Modellar:
- Admin - Admin foydalanuvchilar
- Category - Mahsulot kategoriyalari
- Product - Mahsulotlar
- Order - Buyurtmalar
- Review - Mijoz sharhlari
- Portfolio - Loyihalar
- FAQ - Savollar va javoblar

## Texnologiyalar

- **Backend**: Python Flask
- **Database**: SQLite (SQLAlchemy ORM)
- **Frontend**: HTML, Tailwind CSS
- **Authentication**: Flask-Login

## Deployment (Render.com)

Loyiha Render.com ga deploy qilish uchun tayyor. Batafsil qo'llanma: [RENDER_DEPLOY.md](RENDER_DEPLOY.md)

### Tezkor bosqichlar:

1. **GitHub ga push qiling:**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-github-repo-url>
git push -u origin main
```

2. **Render.com da Web Service yarating:**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
   - Environment Variables:
     - `SECRET_KEY` - xavfsiz secret key
     - `DATABASE_URL` - `sqlite:///furniglass.db` (yoki PostgreSQL)
     - `RENDER=true`

3. **Deploy!**

Batafsil qo'llanma: [RENDER_DEPLOY.md](RENDER_DEPLOY.md)

## Litsenziya

Bu loyiha Furni Glass kompaniyasi uchun yaratilgan.

