from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from sqlalchemy.exc import OperationalError
from config import Config
from db import db
from models import Admin, Product, Category, Order, Review, Portfolio, FAQ, ExchangeRate, Collection, Store, SampleRequest, Article, DesignConsultation, UserActivity, MainCategory, Brand, Client, FirstVisit
from translations import TRANSLATIONS, get_translation, t
import os
import json
import re
import urllib.request
import urllib.parse
import requests

# ============ AUTO-TRANSLATE FUNCTION (FREE) ============
def auto_translate(text, target_lang='ru'):
    """
    Avtomatik tarjima qilish (Google Translate API - bepul)
    text: o'zbek tilidagi matn
    target_lang: maqsad til ('ru' yoki 'en')
    """
    if not text or not text.strip():
        return text
    
    try:
        # Google Translate API (bepul, cheklangan)
        base_url = "https://translate.googleapis.com/translate_a/single"
        params = {
            'client': 'gtx',
            'sl': 'uz',  # source language: Uzbek
            'tl': target_lang,  # target language
            'dt': 't',
            'q': text
        }
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req, timeout=5)
        result = json.loads(response.read().decode('utf-8'))
        
        # Tarjima natijasini olish
        if result and result[0]:
            translated = ''.join([item[0] for item in result[0] if item[0]])
            return translated
        return text
    except Exception as e:
        print(f"Translation error: {e}")
        return text  # Xato bo'lsa, asl matnni qaytarish

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))

# Jinja2 filter for JSON parsing
@app.template_filter('from_json')
def from_json_filter(value):
    try:
        return json.loads(value) if value else []
    except:
        return []

# Helper function to get translated text based on language
def get_translated_text(obj, field_base, lang=None):
    """
    Get translated text from object based on language.
    obj: Product or Category object
    field_base: base field name (e.g., 'name', 'description', 'material')
    lang: language code ('uz', 'ru', 'en')
    """
    if not obj:
        return ''
    
    if lang is None:
        lang = get_locale()
    
    # Try to get language-specific field
    field_name = f"{field_base}_{lang}"
    if hasattr(obj, field_name):
        value = getattr(obj, field_name)
        if value:
            return value
    
    # Fallback to Uzbek
    field_uz = f"{field_base}_uz"
    if hasattr(obj, field_uz):
        value = getattr(obj, field_uz)
        if value:
            return value
    
    # Final fallback to base field
    if hasattr(obj, field_base):
        return getattr(obj, field_base) or ''
    
    return ''

@app.template_filter('t')
def translate_filter(obj, field_base):
    """Template filter for getting translated text"""
    return get_translated_text(obj, field_base, get_locale())

# Ensure upload directories exist
def ensure_upload_dirs():
    """Create upload directories if they don't exist"""
    upload_folder = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(os.path.join(upload_folder, 'products'), exist_ok=True)
    os.makedirs(os.path.join(upload_folder, 'categories'), exist_ok=True)
    os.makedirs(os.path.join(upload_folder, 'main_categories'), exist_ok=True)
    os.makedirs(os.path.join(upload_folder, 'portfolio'), exist_ok=True)
    os.makedirs(os.path.join(upload_folder, 'designs'), exist_ok=True)
    os.makedirs(os.path.join(upload_folder, 'icons'), exist_ok=True)
    os.makedirs(os.path.join(upload_folder, 'brands'), exist_ok=True)

# Initialize upload directories
ensure_upload_dirs()

# Ensure all tables exist (protect against missing tables in existing DB)
def ensure_tables():
    try:
        with app.app_context():
            db.create_all()
    except OperationalError as e:
        print(f"DB init error: {e}")

# Run once on startup
ensure_tables()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============ CURRENCY / EXCHANGE RATE HELPERS ============

def get_exchange_rate() -> float:
    """
    Joriy dollar kursini olish (1 USD = N so'm).
    Agar bazada yo'q bo'lsa, default qiymat yaratadi.
    """
    rate = ExchangeRate.query.first()
    if not rate:
        rate = ExchangeRate(value=12000.0)
        db.session.add(rate)
        db.session.commit()
    return rate.value

# ============ USER ACTIVITY TRACKING ============

@app.before_request
def track_user_activity():
    """Track user activity - sahifalar va mahsulotlar ko'rish (refreshlarni filtrlash)"""
    # Admin panel va static fayllarni kuzatmaymiz
    if request.path.startswith('/admin') or request.path.startswith('/static') or request.path.startswith('/uploads'):
        return
    
    # API endpointlarni ham kuzatmaymiz
    if request.path.startswith('/api') or request.path.startswith('/search'):
        return
    
    # Refreshlarni filtrlash - bir xil sahifaga 30 soniya ichida qayta kirishni sanamaslik
    try:
        from datetime import datetime, timedelta
        
        # Session ID olish yoki yaratish
        if 'session_id' not in session:
            import uuid
            session['session_id'] = str(uuid.uuid4())
            session['last_page'] = None
            session['last_page_time'] = None
        
        session_id = session.get('session_id')
        current_page = request.path
        current_time = datetime.utcnow()
        
        # Refreshlarni tekshirish - bir xil sahifaga qayta kirishni hisobga olmaslik
        last_page = session.get('last_page')
        last_page_time = session.get('last_page_time')
        
        # Agar bir xil sahifaga qayta kirilgan bo'lsa (refresh), kuzatmaymiz
        if last_page == current_page and last_page_time:
            try:
                # Session'dan kelgan vaqt offset-aware bo'lishi mumkin
                if hasattr(last_page_time, 'tzinfo') and last_page_time.tzinfo is not None:
                    last_page_time = last_page_time.replace(tzinfo=None)
                time_diff = (current_time - last_page_time).total_seconds()
                # 60 soniya ichida refresh bo'lsa, hisobga olmaymiz
                if time_diff < 60:
                    return
            except (TypeError, AttributeError):
                pass
        
        # Yangi sahifa yoki vaqt o'tgan - kuzatamiz
        session['last_page'] = current_page
        session['last_page_time'] = current_time
        
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')[:500]
        page_url = request.url
        referrer = request.headers.get('Referer', '')
        
        # Sahifa nomini aniqlash
        page_name = 'Bosh sahifa'
        activity_type = 'page_view'
        product_id = None
        product_name = None
        
        if request.path == '/':
            page_name = 'Bosh sahifa'
        elif request.path.startswith('/products'):
            page_name = 'Mahsulotlar'
        elif request.path.startswith('/product/'):
            # Mahsulot ko'rish
            try:
                product_id_str = request.path.split('/product/')[1].split('/')[0]
                product_id = int(product_id_str)
                product = Product.query.get(product_id)
                if product:
                    activity_type = 'product_view'
                    product_name = product.name_uz or product.name
                    page_name = f'Mahsulot: {product_name}'
            except:
                pass
        elif request.path.startswith('/portfolio'):
            page_name = 'Portfolio'
        elif request.path.startswith('/collections'):
            page_name = 'Kolleksiyalar'
        elif request.path.startswith('/about'):
            page_name = 'Biz haqimizda'
        elif request.path.startswith('/contact'):
            page_name = 'Kontakt'
        elif request.path.startswith('/faq'):
            page_name = 'FAQ'
        elif request.path.startswith('/services'):
            page_name = 'Xizmatlar'
        elif request.path.startswith('/why-us'):
            page_name = 'Nima uchun biz'
        elif request.path.startswith('/interior-design'):
            page_name = 'Interer dizayn'
        elif request.path.startswith('/order'):
            page_name = 'Buyurtma'
        elif request.path.startswith('/cart'):
            page_name = 'Savatcha'
        
        # Activity yozish
        activity = UserActivity(
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            activity_type=activity_type,
            page_url=page_url,
            page_name=page_name,
            product_id=product_id,
            product_name=product_name,
            referrer=referrer[:500]
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        # Xatolarni log qilish, lekin sayt ishlashini to'xtatmaslik
        print(f"Activity tracking error: {e}")
        try:
            db.session.rollback()
        except:
            pass

# ============ FRONTEND ROUTES ============

@app.route('/')
def index():
    main_categories = MainCategory.query.order_by(MainCategory.order).all()
    categories = Category.query.all()  # Barcha kategoriyalar
    # Ko'proq mahsulotlar - avval bestsellerlar, keyin boshqalar
    bestsellers = Product.query.filter_by(is_bestseller=True).limit(30).all()
    if len(bestsellers) < 30:
        remaining = 30 - len(bestsellers)
        other_products = Product.query.filter(Product.is_bestseller != True).order_by(Product.created_at.desc()).limit(remaining).all()
        bestsellers.extend(other_products)
    reviews = Review.query.order_by(Review.created_at.desc()).limit(5).all()
    portfolios = Portfolio.query.order_by(Portfolio.created_at.desc()).limit(3).all()
    collections = Collection.query.limit(3).all()
    articles = Article.query.filter_by(featured=True).limit(2).all()
    brands = Brand.query.filter_by(is_active=True).order_by(Brand.order).all()  # Faol brendlar
    clients = Client.query.filter_by(is_active=True).order_by(Client.order).all()  # Faol mijozlar
    return render_template('index.html', main_categories=main_categories, categories=categories, bestsellers=bestsellers, 
                         reviews=reviews, portfolios=portfolios, collections=collections, articles=articles, brands=brands, clients=clients)

@app.route('/search')
def search():
    """Global search endpoint"""
    query = request.args.get('q', '').strip()
    
    if not query or len(query) < 2:
        return jsonify({
            'products': [],
            'categories': [],
            'portfolios': []
        })
    
    # Search products
    products = Product.query.filter(
        or_(
            Product.name_uz.contains(query),
            Product.name.contains(query),
            Product.description_uz.contains(query),
            Product.description.contains(query),
            Product.material_uz.contains(query),
            Product.material.contains(query)
        )
    ).limit(10).all()
    
    # Search categories
    categories = Category.query.filter(
        or_(
            Category.name_uz.contains(query),
            Category.name.contains(query)
        )
    ).limit(5).all()
    
    # Search portfolios
    portfolios = Portfolio.query.filter(
        or_(
            Portfolio.title_uz.contains(query),
            Portfolio.title.contains(query),
            Portfolio.description_uz.contains(query),
            Portfolio.description.contains(query)
        )
    ).limit(5).all()
    
    # Joriy kurs
    rate = get_exchange_rate()

    # Format results (narx so'mda)
    results = {
        'products': [{
            'id': p.id,
            'name': p.name_uz,
            'price': round(p.price * rate) if p.price is not None else None,
            'image': json.loads(p.images)[0] if p.images else None,
            'category': p.category.name_uz if p.category else None,
            'url': f'/product/{p.id}'
        } for p in products],
        'categories': [{
            'id': c.id,
            'name': c.name_uz,
            'image': c.image,
            'url': f'/products?category={c.id}'
        } for c in categories],
        'portfolios': [{
            'id': p.id,
            'title': p.title_uz,
            'image': p.after_image,
            'url': f'/portfolio'
        } for p in portfolios]
    }
    
    return jsonify(results)

@app.route('/products')
def products():
    category_id = request.args.get('category', type=int)
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    material = request.args.get('material')
    size = request.args.get('size')
    search_query = request.args.get('q', '').strip()
    
    query = Product.query
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    rate = get_exchange_rate()

    # Filtrlar frontendda so'mda, bazada esa USD da saqlanadi
    if min_price:
        query = query.filter(Product.price >= (min_price / rate))
    if max_price:
        query = query.filter(Product.price <= (max_price / rate))
    if material:
        query = query.filter(Product.material.contains(material))
    if size:
        query = query.filter(Product.size.contains(size))
    if search_query:
        query = query.filter(
            or_(
                Product.name_uz.contains(search_query),
                Product.name.contains(search_query),
                Product.description_uz.contains(search_query),
                Product.description.contains(search_query)
            )
        )
    
    products = query.all()
    categories = Category.query.all()
    
    # Get unique materials and sizes for filters
    materials = db.session.query(Product.material).distinct().all()
    sizes = db.session.query(Product.size).distinct().all()
    
    return render_template('products.html', products=products, categories=categories,
                         materials=[m[0] for m in materials if m[0]], 
                         sizes=[s[0] for s in sizes if s[0]],
                         search_query=search_query,
                         usd_rate=rate)

@app.route('/main-category/<slug>')
def main_category_detail(slug):
    """Asosiy kategoriya sahifasi - kategoriyalar, mahsulotlar, sharhlar"""
    main_category = MainCategory.query.filter_by(slug=slug).first_or_404()
    lang = get_locale()
    
    # O'sha asosiy kategoriyaga tegishli kategoriyalar
    categories = Category.query.filter_by(main_category_id=main_category.id).all()
    
    # O'sha asosiy kategoriyaga tegishli mahsulotlar (kategoriyalar orqali)
    category_ids = [c.id for c in categories]
    all_products = Product.query.filter(Product.category_id.in_(category_ids)).all() if category_ids else []
    
    # O'sha asosiy kategoriyaga tegishli sharhlar
    reviews = Review.query.filter_by(main_category_id=main_category.id).order_by(Review.created_at.desc()).all()
    
    rate = get_exchange_rate()
    
    return render_template('main_category.html', 
                         main_category=main_category,
                         categories=categories,
                         all_products=all_products,
                         reviews=reviews,
                         rate=rate,
                         lang=lang)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    rate = get_exchange_rate()
    # Bog'liq mahsulotlar - bir xil kategoriyadagi boshqa mahsulotlar
    related_products = []
    if product.category:
        related_products = Product.query.filter(
            Product.category_id == product.category_id,
            Product.id != product.id
        ).limit(8).all()
    # Agar bog'liq mahsulotlar yetarli bo'lmasa, boshqa mahsulotlar qo'shish
    if len(related_products) < 8:
        remaining = 8 - len(related_products)
        other_products = Product.query.filter(
            Product.id != product.id
        ).order_by(Product.created_at.desc()).limit(remaining).all()
        related_products.extend(other_products)
    return render_template('product_detail.html', product=product, usd_rate=rate, related_products=related_products)

@app.route('/google9029ae48d4d9d006.html')
def google_verification():
    """Google Search Console verification file"""
    return 'google-site-verification: google9029ae48d4d9d006.html', 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/sitemap.xml')
def sitemap():
    """Generate sitemap.xml for SEO"""
    from datetime import datetime
    base_url = request.url_root.rstrip('/')
    
    # Static pages
    static_pages = [
        {'loc': base_url, 'changefreq': 'daily', 'priority': '1.0'},
        {'loc': f'{base_url}/products', 'changefreq': 'daily', 'priority': '0.9'},
        {'loc': f'{base_url}/custom', 'changefreq': 'weekly', 'priority': '0.9'},
        {'loc': f'{base_url}/portfolio', 'changefreq': 'weekly', 'priority': '0.8'},
        {'loc': f'{base_url}/about', 'changefreq': 'monthly', 'priority': '0.7'},
        {'loc': f'{base_url}/contact', 'changefreq': 'monthly', 'priority': '0.7'},
        {'loc': f'{base_url}/faq', 'changefreq': 'monthly', 'priority': '0.6'},
        {'loc': f'{base_url}/services', 'changefreq': 'monthly', 'priority': '0.7'},
        {'loc': f'{base_url}/stores', 'changefreq': 'weekly', 'priority': '0.7'},
    ]
    
    # Main categories
    try:
        main_categories = MainCategory.query.all()
        for mc in main_categories:
            if mc and mc.slug:
                static_pages.append({
                    'loc': f'{base_url}/main-category/{mc.slug}',
                    'changefreq': 'weekly',
                    'priority': '0.8'
                })
    except Exception as e:
        # Agar main categories'da muammo bo'lsa, o'tkazib yuboramiz
        pass
    
    # Products
    try:
        products = Product.query.all()  # is_active maydoni yo'q, barcha mahsulotlarni olamiz
        product_pages = []
        for product in products:
            try:
                lastmod = product.created_at.strftime('%Y-%m-%d') if product.created_at else datetime.now().strftime('%Y-%m-%d')
                if hasattr(product, 'updated_at') and product.updated_at:
                    lastmod = product.updated_at.strftime('%Y-%m-%d')
                product_pages.append({
                    'loc': f'{base_url}/product/{product.id}',
                    'changefreq': 'weekly',
                    'priority': '0.9',
                    'lastmod': lastmod
                })
            except Exception as e:
                # Agar biror mahsulotda muammo bo'lsa, o'tkazib yuboramiz
                continue
    except Exception as e:
        # Agar products query'da muammo bo'lsa, bo'sh ro'yxat qaytaramiz
        product_pages = []
    
    # Categories
    try:
        categories = Category.query.all()
        category_pages = []
        for category in categories:
            if category and category.id:
                category_pages.append({
                    'loc': f'{base_url}/products?category={category.id}',
                    'changefreq': 'weekly',
                    'priority': '0.8'
                })
    except Exception as e:
        # Agar categories'da muammo bo'lsa, bo'sh ro'yxat qaytaramiz
        category_pages = []
    
    # Portfolio items
    portfolios = Portfolio.query.all()
    portfolio_pages = []
    for portfolio in portfolios:
        portfolio_pages.append({
            'loc': f'{base_url}/portfolio',
            'changefreq': 'monthly',
            'priority': '0.7'
        })
    
    # Generate XML
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    # Add all pages
    all_pages = static_pages + product_pages + category_pages
    
    for page in all_pages:
        xml.append('  <url>')
        xml.append(f'    <loc>{page["loc"]}</loc>')
        xml.append(f'    <changefreq>{page["changefreq"]}</changefreq>')
        xml.append(f'    <priority>{page["priority"]}</priority>')
        if 'lastmod' in page:
            xml.append(f'    <lastmod>{page["lastmod"]}</lastmod>')
        xml.append('  </url>')
    
    xml.append('</urlset>')
    
    return '\n'.join(xml), 200, {'Content-Type': 'application/xml; charset=utf-8'}

@app.route('/robots.txt')
def robots():
    """Generate robots.txt for SEO"""
    base_url = request.url_root.rstrip('/')
    robots_txt = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /cart/
Disallow: /checkout/
Disallow: /api/

Sitemap: {base_url}/sitemap.xml
"""
    return robots_txt, 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route('/portfolio')
def portfolio():
    room_type = request.args.get('room_type')
    query = Portfolio.query
    if room_type:
        query = query.filter_by(room_type_uz=room_type)
    portfolios = query.order_by(Portfolio.created_at.desc()).all()
    return render_template('portfolio.html', portfolios=portfolios)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/why-us')
def why_us():
    return render_template('why_us.html')

@app.route('/order', methods=['GET', 'POST'])
def order():
    if request.method == 'POST':
        furniture_type = request.form.get('furniture_type')
        size = request.form.get('size')
        color = request.form.get('color')
        material = request.form.get('material')
        phone = request.form.get('phone')
        name = request.form.get('name')
        address = request.form.get('address')
        
        design_image = None
        if 'design_image' in request.files:
            file = request.files['design_image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join('designs', filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
                design_image = filepath
        
        order = Order(
            furniture_type=furniture_type,
            size=size,
            color=color,
            material=material,
            design_image=design_image,
            phone=phone,
            name=name,
            address=address
        )
        db.session.add(order)
        db.session.commit()
        flash('Buyurtmangiz qabul qilindi! Tez orada siz bilan bog\'lanamiz.', 'success')
        return redirect(url_for('order'))
    
    categories = Category.query.all()
    return render_template('order.html', categories=categories)

def send_telegram_message(message):
    """Telegram botga xabar yuborish"""
    try:
        token = app.config.get('TELEGRAM_BOT_TOKEN')
        chat_id = app.config.get('TELEGRAM_CHAT_ID')
        
        if not token or not chat_id:
            print("Telegram bot token yoki chat_id topilmadi")
            return False
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram xabar yuborishda xatolik: {e}")
        return False

@app.route('/custom')
def custom():
    """Individual mebel buyurtmasi sahifasi"""
    return render_template('custom.html')

@app.route('/api/custom-order', methods=['POST'])
def custom_order():
    """Individual mebel buyurtmasini qabul qilish va Telegram'ga yuborish"""
    try:
        data = request.get_json()
        
        legs = data.get('legs', '')
        seat = data.get('seat', '')
        backrest = data.get('backrest', '')
        pattern = data.get('pattern', '')
        material = data.get('material', '')
        phone = data.get('phone', '')
        name = data.get('name', '')
        message = data.get('message', '')
        
        # Telefon raqam validatsiyasi
        phone_cleaned = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if not re.match(r'^(\+998|998)?[0-9]{9}$', phone_cleaned):
            return jsonify({
                'success': False,
                'message': 'To\'g\'ri telefon raqam kiriting (masalan: +998901234567)'
            }), 400
        
        # Default qiymatlar
        name_display = name if name else "Ko'rsatilmagan"
        phone_display = phone if phone else "Ko'rsatilmagan"
        message_display = message if message else "Qo'shimcha xabar yo'q"
        
        # Telegram xabari
        telegram_message = f"""
<b>🪑 Yangi Individual Mebel Buyurtmasi</b>

<b>Mijoz ma'lumotlari:</b>
👤 Ism: {name_display}
📞 Telefon: {phone_display}

<b>Konfiguratsiya:</b>
🦵 Oyoqlar: {legs}
🪑 O'rindiq: {seat}
🧱 Suyanchiq: {backrest}
✨ Naqsh: {pattern}
🎨 Rang: {material}

<b>Qo'shimcha xabar:</b>
{message_display}
"""
        
        # Telegram'ga yuborish
        telegram_sent = send_telegram_message(telegram_message)
        
        # Database'ga saqlash (ixtiyoriy)
        try:
            order = Order(
                furniture_type=f'Individual: {legs}, {seat}, {backrest}',
                size='',
                color=material,
                material=seat,
                phone=phone,
                name=name,
                address=message
            )
            db.session.add(order)
            db.session.commit()
        except Exception as e:
            print(f"Database'ga saqlashda xatolik: {e}")
            db.session.rollback()
        
        return jsonify({
            'success': True,
            'telegram_sent': telegram_sent,
            'message': 'Buyurtmangiz qabul qilindi! Tez orada siz bilan bog\'lanamiz.'
        })
    except Exception as e:
        print(f"Xatolik: {e}")
        return jsonify({
            'success': False,
            'message': 'Xatolik yuz berdi. Iltimos, qayta urinib ko\'ring.'
        }), 500

@app.route('/api/first-visit', methods=['POST'])
def first_visit():
    """Birinchi marta kirgan foydalanuvchi ma'lumotlarini qabul qilish"""
    try:
        from datetime import datetime
        data = request.get_json()
        
        name = data.get('name', '')
        phone = data.get('phone', '')
        interest = data.get('interest', '')
        
        # Telefon raqam validatsiyasi
        phone_cleaned = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if not re.match(r'^(\+998|998)?[0-9]{9}$', phone_cleaned):
            return jsonify({
                'success': False,
                'message': 'To\'g\'ri telefon raqam kiriting (masalan: +998901234567)'
            }), 400
        
        # Interest nomlarini o'zbek tiliga o'girish
        interest_names = {
            'clinic': 'Klinika uchun mebel',
            'restaurant': 'Restoran/kafe uchun mebel',
            'home': 'Uy uchun mebel'
        }
        interest_display = interest_names.get(interest, interest)
        
        # Telegram xabari
        telegram_message = f"""
<b>👋 Yangi Sayt Tashrifchisi</b>

<b>Ma'lumotlar:</b>
👤 Ism: {name if name else "Ko'rsatilmagan"}
📞 Telefon: {phone if phone else "Ko'rsatilmagan"}
🎯 Qiziqish: {interest_display}

<b>Vaqt:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        # Telegram'ga yuborish
        telegram_sent = send_telegram_message(telegram_message)
        
        # DB ga saqlash
        try:
            first_visit_record = FirstVisit(
                name=name,
                phone=phone,
                interest=interest
            )
            db.session.add(first_visit_record)
            db.session.commit()
        except Exception as db_error:
            print(f"DB saqlash xatolik: {db_error}")
            db.session.rollback()
        
        return jsonify({
            'success': True,
            'telegram_sent': telegram_sent,
            'message': 'Rahmat! Ma\'lumotlaringiz qabul qilindi.'
        })
    except Exception as e:
        print(f"Xatolik: {e}")
        return jsonify({
            'success': False,
            'message': 'Xatolik yuz berdi. Iltimos, qayta urinib ko\'ring.'
        }), 500

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Contact form
        phone = request.form.get('phone')
        name = request.form.get('name')
        subject = request.form.get('subject', '')
        message = request.form.get('message', '')
        
        # Telefon raqam validatsiyasi
        phone_cleaned = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if not re.match(r'^(\+998|998)?[0-9]{9}$', phone_cleaned):
            flash('To\'g\'ri telefon raqam kiriting (masalan: +998901234567)', 'error')
            return redirect(url_for('contact'))
        
        # Telegram xabari
        subject_display = {
            'order': 'Yangi buyurtma',
            'consultation': 'Maslahat',
            'price': 'Narx so\'rovi'
        }.get(subject, 'Umumiy so\'rov')
        
        telegram_message = f"""
<b>📧 Yangi Aloqa Formasi</b>

<b>Mijoz ma'lumotlari:</b>
👤 Ism: {name if name else "Ko'rsatilmagan"}
📞 Telefon: {phone if phone else "Ko'rsatilmagan"}
📋 Mavzu: {subject_display}

<b>Xabar:</b>
{message if message else "Qo'shimcha xabar yo'q"}
"""
        
        # Telegram'ga yuborish
        telegram_sent = send_telegram_message(telegram_message)
        
        # Database'ga saqlash
        order = Order(
            furniture_type=f'Aloqa: {subject_display}',
            phone=phone,
            name=name,
            address=message
        )
        db.session.add(order)
        db.session.commit()
        
        flash('Xabaringiz yuborildi! Tez orada siz bilan bog\'lanamiz.', 'success')
        return redirect(url_for('contact'))
    
    return render_template('contact.html')

@app.route('/faq')
def faq():
    faqs = FAQ.query.order_by(FAQ.order).all()
    return render_template('faq.html', faqs=faqs)

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/team')
def team():
    return render_template('team.html')

@app.route('/gallery')
def gallery():
    return render_template('gallery.html')

@app.route('/collections')
def collections():
    """Collections page - Sofa, Table, Chair collections"""
    collection_type = request.args.get('type', 'all')
    collections = Collection.query
    if collection_type != 'all':
        collections = collections.filter_by(category_type=collection_type)
    collections = collections.order_by(Collection.created_at.desc()).all()
    return render_template('collections.html', collections=collections, collection_type=collection_type)

@app.route('/rooms')
def rooms():
    """Rooms page - Living rooms, Dining rooms, Bedrooms, etc."""
    room_type = request.args.get('type', 'all')
    portfolios = Portfolio.query
    if room_type != 'all':
        portfolios = portfolios.filter_by(room_type_uz=room_type)
    portfolios = portfolios.order_by(Portfolio.created_at.desc()).all()
    
    # Room types
    room_types = {
        'living': {'uz': 'Zal', 'ru': 'Гостиная', 'en': 'Living Room'},
        'dining': {'uz': 'Oshxona', 'ru': 'Столовая', 'en': 'Dining Room'},
        'bedroom': {'uz': 'Yotoqxona', 'ru': 'Спальня', 'en': 'Bedroom'},
        'outdoor': {'uz': 'Tashqi maydon', 'ru': 'Наружное пространство', 'en': 'Outdoor Space'},
        'office': {'uz': 'Ofis', 'ru': 'Офис', 'en': 'Home Office'},
        'small': {'uz': 'Kichik xonalar', 'ru': 'Маленькие пространства', 'en': 'Small Spaces'}
    }
    
    return render_template('rooms.html', portfolios=portfolios, room_type=room_type, room_types=room_types)

@app.route('/interior-design', methods=['GET', 'POST'])
def interior_design():
    """Interior Design Service page"""
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        room_type = request.form.get('room_type')
        budget = request.form.get('budget')
        message = request.form.get('message')
        
        consultation = DesignConsultation(
            name=name,
            phone=phone,
            email=email,
            room_type=room_type,
            budget=budget,
            message=message
        )
        db.session.add(consultation)
        db.session.commit()
        flash('So\'rovingiz qabul qilindi! Tez orada siz bilan bog\'lanamiz.', 'success')
        return redirect(url_for('interior_design'))
    
    return render_template('interior_design.html')


@app.route('/samples', methods=['GET', 'POST'])
def samples():
    """Free samples request page"""
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        product_id = request.form.get('product_id', type=int)
        message = request.form.get('message')
        
        sample = SampleRequest(
            name=name,
            phone=phone,
            email=email,
            product_id=product_id,
            message=message
        )
        db.session.add(sample)
        db.session.commit()
        flash('So\'rovingiz qabul qilindi! Tez orada siz bilan bog\'lanamiz.', 'success')
        return redirect(url_for('samples'))
    
    products = Product.query.all()
    return render_template('samples.html', products=products)

@app.route('/inspiration')
def inspiration():
    """Inspiration/Articles page"""
    category = request.args.get('category', 'all')
    articles = Article.query
    if category != 'all':
        articles = articles.filter_by(category=category)
    articles = articles.order_by(Article.created_at.desc()).all()
    featured = Article.query.filter_by(featured=True).order_by(Article.created_at.desc()).limit(3).all()
    return render_template('inspiration.html', articles=articles, featured=featured, category=category)

# ============ CART ROUTES ============

def get_cart():
    """Get cart from session"""
    if 'cart' not in session:
        session['cart'] = []
    return session['cart']

def get_cart_count():
    """Get total items count in cart"""
    cart = get_cart()
    return sum(item['quantity'] for item in cart)

def get_cart_total():
    """Get cart total price"""
    cart = get_cart()
    total = 0
    rate = get_exchange_rate()
    for item in cart:
        product = Product.query.get(item['product_id'])
        if product:
            total += product.price * rate * item['quantity']
    return total

@app.context_processor
def cart_context():
    """Make cart count available in all templates"""
    return {'cart_count': get_cart_count()}


@app.context_processor
def currency_context():
    """
    Valyuta kursini barcha shablonlarga uzatish.
    product.price USD da, shablonlarda price * usd_rate ko'rinadi.
    """
    try:
        rate = get_exchange_rate()
    except Exception:
        rate = 12000.0
    return {'usd_rate': rate}

# ============ LANGUAGE ROUTES ============

SUPPORTED_LANGUAGES = ['uz', 'ru', 'en']
DEFAULT_LANGUAGE = 'uz'

def get_locale():
    """Get current language from session"""
    return session.get('lang', DEFAULT_LANGUAGE)

@app.context_processor
def language_context():
    """Make language and translations available in all templates"""
    current_lang = get_locale()
    
    def translate(key_path):
        """Template helper for translations"""
        return get_translation(key_path, current_lang)
    
    return {
        'lang': current_lang, 
        'languages': SUPPORTED_LANGUAGES,
        't': translate,
        'T': TRANSLATIONS
    }

@app.route('/set-language/<lang>')
def set_language(lang):
    """Set language preference"""
    if lang in SUPPORTED_LANGUAGES:
        session['lang'] = lang
        session.modified = True
    return redirect(request.referrer or url_for('index'))

@app.route('/cart')
def cart():
    cart_items = get_cart()
    products = []
    total = 0
    
    for item in cart_items:
        product = Product.query.get(item['product_id'])
        if product:
            subtotal = product.price * get_exchange_rate() * item['quantity']
            total += subtotal
            products.append({
                'product': product,
                'quantity': item['quantity'],
                'subtotal': subtotal
            })
    
    return render_template('cart.html', cart_items=products, total=total)

@app.route('/cart/add/<int:product_id>', methods=['POST'])
def cart_add(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = int(request.form.get('quantity', 1))
    selected_color = request.form.get('color', '')  # Rang tanlash
    
    cart = get_cart()
    
    # Check if product with same color already in cart
    for item in cart:
        if item['product_id'] == product_id and item.get('color') == selected_color:
            item['quantity'] += quantity
            session.modified = True
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'cart_count': get_cart_count(), 'message': 'Mahsulot savatchaga qo\'shildi!'})
            flash('Mahsulot savatchaga qo\'shildi!', 'success')
            return redirect(request.referrer or url_for('products'))
    
    # Add new item
    cart.append({
        'product_id': product_id,
        'quantity': quantity,
        'color': selected_color
    })
    session['cart'] = cart
    session.modified = True
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'cart_count': get_cart_count(), 'message': 'Mahsulot savatchaga qo\'shildi!'})
    
    flash('Mahsulot savatchaga qo\'shildi!', 'success')
    return redirect(request.referrer or url_for('products'))

@app.route('/cart/update/<int:product_id>', methods=['POST'])
def cart_update(product_id):
    quantity = int(request.form.get('quantity', 1))
    cart = get_cart()
    
    for item in cart:
        if item['product_id'] == product_id:
            if quantity > 0:
                item['quantity'] = quantity
            else:
                cart.remove(item)
            break
    
    session['cart'] = cart
    session.modified = True
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'cart_count': get_cart_count(), 'total': get_cart_total()})
    
    return redirect(url_for('cart'))

@app.route('/cart/remove/<int:product_id>', methods=['POST'])
def cart_remove(product_id):
    cart = get_cart()
    cart = [item for item in cart if item['product_id'] != product_id]
    session['cart'] = cart
    session.modified = True
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'cart_count': get_cart_count(), 'total': get_cart_total()})
    
    flash('Mahsulot savatchadan o\'chirildi!', 'success')
    return redirect(url_for('cart'))

@app.route('/cart/clear', methods=['POST'])
def cart_clear():
    session['cart'] = []
    session.modified = True
    flash('Savatcha tozalandi!', 'success')
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart_items = get_cart()
    if not cart_items:
        flash('Savatchingiz bo\'sh!', 'error')
        return redirect(url_for('cart'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        comment = request.form.get('comment', '')
        payment = request.form.get('payment', 'cash')
        
        # Telefon raqam validatsiyasi
        phone_cleaned = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if not re.match(r'^(\+998|998)?[0-9]{9}$', phone_cleaned):
            flash('To\'g\'ri telefon raqam kiriting (masalan: +998901234567)', 'error')
            return redirect(url_for('checkout'))
        
        # Get cart products for order
        products_list = []
        total = 0
        rate = get_exchange_rate()
        for item in cart_items:
            product = Product.query.get(item['product_id'])
            if product:
                products_list.append(f"{product.name_uz} x{item['quantity']}")
                total += product.price * rate * item['quantity']
        
        # Telegram xabari
        payment_display = {
            'cash': 'Naqd pul',
            'card': 'Plastik karta'
        }.get(payment, 'Naqd pul')
        
        products_text = '\n'.join([f"  • {p}" for p in products_list])
        
        telegram_message = f"""
<b>🛒 Yangi Savatcha Buyurtmasi</b>

<b>Mijoz ma'lumotlari:</b>
👤 Ism: {name if name else "Ko'rsatilmagan"}
📞 Telefon: {phone if phone else "Ko'rsatilmagan"}
📍 Manzil: {address if address else "Ko'rsatilmagan"}
💳 To'lov usuli: {payment_display}

<b>Mahsulotlar:</b>
{products_text}

<b>Jami:</b> {total:,.0f} so'm

<b>Qo'shimcha izoh:</b>
{comment if comment else "Qo'shimcha izoh yo'q"}
"""
        
        # Telegram'ga yuborish
        telegram_sent = send_telegram_message(telegram_message)
        
        # Create order
        order = Order(
            furniture_type=', '.join(products_list),
            phone=phone,
            name=name,
            address=address + (f"\n\nIzoh: {comment}" if comment else ""),
            status='Yangi'
        )
        db.session.add(order)
        db.session.commit()
        
        # Clear cart
        session['cart'] = []
        session.modified = True
        
        flash('Buyurtmangiz qabul qilindi! Tez orada siz bilan bog\'lanamiz.', 'success')
        return redirect(url_for('checkout_success'))
    
    # Get products for display
    products = []
    total = 0
    rate = get_exchange_rate()
    for item in cart_items:
        product = Product.query.get(item['product_id'])
        if product:
            subtotal = product.price * rate * item['quantity']
            total += subtotal
            products.append({
                'product': product,
                'quantity': item['quantity'],
                'subtotal': subtotal
            })
    
    return render_template('checkout.html', cart_items=products, total=total)

@app.route('/checkout/success')
def checkout_success():
    return render_template('checkout_success.html')

# ============ ADMIN ROUTES ============

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password, password):
            login_user(admin)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Noto\'g\'ri foydalanuvchi nomi yoki parol', 'error')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin_login'))

@app.route('/admin')
@login_required
def admin_dashboard():
    stats = {
        'products': Product.query.count(),
        'orders': Order.query.count(),
        'categories': Category.query.count(),
        'portfolios': Portfolio.query.count()
    }
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    rate = get_exchange_rate()
    return render_template('admin/dashboard.html', stats=stats, recent_orders=recent_orders, usd_rate=rate)


@app.route('/admin/settings/currency', methods=['GET', 'POST'])
@login_required
def admin_currency_settings():
    """
    Dollar kursini qo'lda boshqarish sahifasi.
    1 USD = N so'm qiymati shu yerda saqlanadi.
    """
    rate = ExchangeRate.query.first()
    if not rate:
        rate = ExchangeRate(value=12000.0)
        db.session.add(rate)
        db.session.commit()

    if request.method == 'POST':
        try:
            value = float(request.form.get('value', '').replace(' ', '').replace(',', ''))
            if value <= 0:
                raise ValueError()
        except Exception:
            flash("Dollar kursini to'g'ri kiriting.", 'error')
            return redirect(url_for('admin_currency_settings'))

        rate.value = value
        db.session.commit()
        flash("Dollar kursi yangilandi.", 'success')
        return redirect(url_for('admin_currency_settings'))

    return render_template('admin/currency_settings.html', rate=rate)

@app.route('/admin/products')
@login_required
def admin_products():
    products = Product.query.all()
    rate = get_exchange_rate()
    return render_template('admin/products.html', products=products, usd_rate=rate)

@app.route('/admin/product/add', methods=['GET', 'POST'])
@login_required
def admin_product_add():
    if request.method == 'POST':
        name_uz = request.form.get('name_uz')
        description_uz = request.form.get('description_uz')
        material_uz = request.form.get('material_uz')
        warranty_uz = request.form.get('warranty_uz')
        
        # Auto-translate to Russian and English
        name_ru = auto_translate(name_uz, 'ru')
        name_en = auto_translate(name_uz, 'en')
        description_ru = auto_translate(description_uz, 'ru') if description_uz else None
        description_en = auto_translate(description_uz, 'en') if description_uz else None
        material_ru = auto_translate(material_uz, 'ru') if material_uz else None
        material_en = auto_translate(material_uz, 'en') if material_uz else None
        
        price = float(request.form.get('price'))
        discount = int(request.form.get('discount', 0))
        size = request.form.get('size')
        category_id = int(request.form.get('category_id'))
        is_bestseller = request.form.get('is_bestseller') == 'on'
        colors = request.form.get('colors', '').strip()
        
        # Validate colors JSON
        colors_json = None
        if colors:
            try:
                colors_data = json.loads(colors)
                if isinstance(colors_data, list):
                    colors_json = colors
            except:
                flash('Ranglar formati noto\'g\'ri! JSON formatida kiriting.', 'error')
        
        images = []
        # Debug: barcha fayllarni ko'rish
        print(f"DEBUG: request.files keys: {list(request.files.keys())}")
        print(f"DEBUG: 'images' in request.files: {'images' in request.files}")
        
        if 'images' in request.files:
            files = request.files.getlist('images')
            print(f"DEBUG: files list length: {len(files)}")
            print(f"DEBUG: files: {[f.filename for f in files if f.filename]}")
            
            # 5 tagacha rasm cheklash
            files = files[:5]
            
            # Asosiy rasm indexini olish (yangi rasmlar uchun)
            new_main_image_index = request.form.get('new_main_image_index')
            if new_main_image_index:
                main_image_index = int(new_main_image_index)
            else:
                main_image_index = 0
            
            for idx, file in enumerate(files):
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Unique filename yaratish
                    import uuid
                    unique_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
                    filepath = os.path.join('products', unique_filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
                    images.append(filepath)
                    print(f"DEBUG: Saved image {idx+1}: {filepath}")
            
            # Asosiy rasmni birinchi o'ringa qo'yish
            if images and main_image_index > 0 and main_image_index < len(images):
                main_image = images.pop(main_image_index)
                images.insert(0, main_image)
        
        print(f"DEBUG: Total images saved: {len(images)}")
        
        product = Product(
            name=name_uz,  # Default name
            name_uz=name_uz,
            name_ru=name_ru,
            name_en=name_en,
            description=description_uz,
            description_uz=description_uz,
            description_ru=description_ru,
            description_en=description_en,
            price=price,
            size=size,
            material=material_uz,
            material_uz=material_uz,
            material_ru=material_ru,
            material_en=material_en,
            category_id=category_id,
            is_bestseller=is_bestseller,
            discount=discount,
            warranty=warranty_uz,
            warranty_uz=warranty_uz,
            images=json.dumps(images),
            colors=colors_json
        )
        db.session.add(product)
        db.session.commit()
        flash('Mahsulot qo\'shildi!', 'success')
        return redirect(url_for('admin_products'))
    
    categories = Category.query.all()
    return render_template('admin/product_form.html', categories=categories)

@app.route('/admin/product/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        product.name_uz = request.form.get('name_uz')
        product.name = product.name_uz
        product.description_uz = request.form.get('description_uz')
        product.description = product.description_uz
        product.material_uz = request.form.get('material_uz')
        product.material = product.material_uz
        product.warranty_uz = request.form.get('warranty_uz')
        product.warranty = product.warranty_uz
        
        # Auto-translate to Russian and English
        product.name_ru = auto_translate(product.name_uz, 'ru')
        product.name_en = auto_translate(product.name_uz, 'en')
        product.description_ru = auto_translate(product.description_uz, 'ru') if product.description_uz else None
        product.description_en = auto_translate(product.description_uz, 'en') if product.description_uz else None
        product.material_ru = auto_translate(product.material_uz, 'ru') if product.material_uz else None
        product.material_en = auto_translate(product.material_uz, 'en') if product.material_uz else None
        
        product.price = float(request.form.get('price'))
        product.discount = int(request.form.get('discount', 0))
        product.size = request.form.get('size')
        product.category_id = int(request.form.get('category_id'))
        product.is_bestseller = request.form.get('is_bestseller') == 'on'
        
        # Colors
        colors = request.form.get('colors', '').strip()
        colors_json = None
        if colors:
            try:
                colors_data = json.loads(colors)
                if isinstance(colors_data, list):
                    colors_json = colors
            except:
                flash('Ranglar formati noto\'g\'ri! JSON formatida kiriting.', 'error')
        product.colors = colors_json
        
        images = json.loads(product.images) if product.images else []
        
        # Mavjud rasmlar uchun asosiy rasm indexini olish
        main_image_index = request.form.get('main_image_index')
        if main_image_index is not None and main_image_index != '':
            main_image_index = int(main_image_index)
            # Mavjud rasmlarda asosiy rasmni birinchi o'ringa qo'yish
            if images and main_image_index > 0 and main_image_index < len(images):
                main_image = images.pop(main_image_index)
                images.insert(0, main_image)
        
        # Yangi rasmlar qo'shish
        if 'images' in request.files:
            files = request.files.getlist('images')
            # 5 tagacha rasm cheklash (mavjud + yangi)
            remaining_slots = 5 - len(images)
            if remaining_slots > 0:
                files = files[:remaining_slots]
                
                # Yangi rasmlar uchun asosiy rasm indexini olish
                new_main_index = int(request.form.get('new_main_image_index', 0))
                
                new_images = []
                for idx, file in enumerate(files):
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        # Unique filename yaratish
                        import uuid
                        unique_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
                        filepath = os.path.join('products', unique_filename)
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
                        new_images.append(filepath)
                
                # Yangi rasmlarda asosiy rasmni birinchi o'ringa qo'yish
                if new_images and new_main_index > 0 and new_main_index < len(new_images):
                    new_main_image = new_images.pop(new_main_index)
                    new_images.insert(0, new_main_image)
                
                # Yangi rasmlarni mavjud rasmlarga qo'shish (birinchi o'ringa)
                # Agar yangi rasmlar bo'lsa va ularning asosiy rasmi bo'lsa, uni eng boshiga qo'yish
                if new_images:
                    images = new_images + images
                    # Jami 5 tagacha cheklash
                    images = images[:5]
        
        product.images = json.dumps(images)
        db.session.commit()
        flash('Mahsulot yangilandi!', 'success')
        return redirect(url_for('admin_products'))
    
    categories = Category.query.all()
    return render_template('admin/product_form.html', product=product, categories=categories)

@app.route('/admin/product/<int:product_id>/delete', methods=['POST'])
@login_required
def admin_product_delete(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash('Mahsulot o\'chirildi!', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/main-categories')
@login_required
def admin_main_categories():
    main_categories = MainCategory.query.order_by(MainCategory.order).all()
    return render_template('admin/main_categories.html', main_categories=main_categories)

@app.route('/admin/main-category/add', methods=['GET', 'POST'])
@login_required
def admin_main_category_add():
    if request.method == 'POST':
        name_uz = request.form.get('name_uz')
        
        # Auto-translate to Russian and English
        name_ru = auto_translate(name_uz, 'ru')
        name_en = auto_translate(name_uz, 'en')
        
        slug = request.form.get('slug') or name_uz.lower().replace(' ', '-').replace('&', 'and')
        description_uz = request.form.get('description_uz', '')
        description_ru = auto_translate(description_uz, 'ru') if description_uz else ''
        description_en = auto_translate(description_uz, 'en') if description_uz else ''
        order = request.form.get('order', type=int) or 0
        
        image = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join('main_categories', filename)
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'main_categories'), exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
                image = filepath
        
        main_category = MainCategory(
            name_uz=name_uz,
            name_ru=name_ru,
            name_en=name_en,
            slug=slug,
            description_uz=description_uz,
            description_ru=description_ru,
            description_en=description_en,
            image=image,
            order=order
        )
        db.session.add(main_category)
        db.session.commit()
        flash('Asosiy kategoriya qo\'shildi!', 'success')
        return redirect(url_for('admin_main_categories'))
    
    return render_template('admin/main_category_form.html')

@app.route('/admin/main-category/<int:main_category_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_main_category_edit(main_category_id):
    main_category = MainCategory.query.get_or_404(main_category_id)
    
    if request.method == 'POST':
        main_category.name_uz = request.form.get('name_uz')
        
        # Auto-translate if fields are empty
        if not request.form.get('name_ru'):
            main_category.name_ru = auto_translate(main_category.name_uz, 'ru')
        else:
            main_category.name_ru = request.form.get('name_ru')
            
        if not request.form.get('name_en'):
            main_category.name_en = auto_translate(main_category.name_uz, 'en')
        else:
            main_category.name_en = request.form.get('name_en')
        
        main_category.slug = request.form.get('slug') or main_category.name_uz.lower().replace(' ', '-').replace('&', 'and')
        main_category.description_uz = request.form.get('description_uz', '')
        
        if not request.form.get('description_ru'):
            main_category.description_ru = auto_translate(main_category.description_uz, 'ru') if main_category.description_uz else ''
        else:
            main_category.description_ru = request.form.get('description_ru')
            
        if not request.form.get('description_en'):
            main_category.description_en = auto_translate(main_category.description_uz, 'en') if main_category.description_uz else ''
        else:
            main_category.description_en = request.form.get('description_en')
        
        main_category.order = request.form.get('order', type=int) or 0
        
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join('main_categories', filename)
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'main_categories'), exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
                main_category.image = filepath
        
        db.session.commit()
        flash('Asosiy kategoriya yangilandi!', 'success')
        return redirect(url_for('admin_main_categories'))
    
    return render_template('admin/main_category_form.html', main_category=main_category)

@app.route('/admin/main-category/<int:main_category_id>/delete', methods=['POST'])
@login_required
def admin_main_category_delete(main_category_id):
    main_category = MainCategory.query.get_or_404(main_category_id)
    
    # Check if main category has categories
    if main_category.categories:
        flash('Bu asosiy kategoriyada kategoriyalar bor. Avval kategoriyalarni o\'chiring yoki boshqa asosiy kategoriyaga ko\'chiring!', 'error')
        return redirect(url_for('admin_main_categories'))
    
    db.session.delete(main_category)
    db.session.commit()
    flash('Asosiy kategoriya o\'chirildi!', 'success')
    return redirect(url_for('admin_main_categories'))

@app.route('/admin/categories')
@login_required
def admin_categories():
    categories = Category.query.all()
    main_categories = MainCategory.query.all()
    return render_template('admin/categories.html', categories=categories, main_categories=main_categories)

@app.route('/admin/brands')
@login_required
def admin_brands():
    brands = Brand.query.order_by(Brand.order).all()
    return render_template('admin/brands.html', brands=brands)

@app.route('/admin/brand/add', methods=['GET', 'POST'])
@login_required
def admin_brand_add():
    if request.method == 'POST':
        name_uz = request.form.get('name_uz')
        name_ru = request.form.get('name_ru')
        name_en = request.form.get('name_en')
        website = request.form.get('website', '')
        order = int(request.form.get('order', 0))
        is_active = request.form.get('is_active') == 'on'
        
        # Logo fayl yuklash
        logo_file = request.files.get('logo')
        if not logo_file or not logo_file.filename:
            flash('Logo fayl yuklash majburiy!', 'error')
            return redirect(url_for('admin_brand_add'))
        
        filename = secure_filename(logo_file.filename)
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join('brands', filename)
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'brands'), exist_ok=True)
        logo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
        
        brand = Brand(
            name=name_uz,
            name_uz=name_uz,
            name_ru=name_ru,
            name_en=name_en,
            logo=filepath,
            website=website,
            order=order,
            is_active=is_active
        )
        db.session.add(brand)
        db.session.commit()
        flash('Brend qo\'shildi!', 'success')
        return redirect(url_for('admin_brands'))
    
    return render_template('admin/brand_form.html', brand=None)

@app.route('/admin/brand/<int:brand_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_brand_edit(brand_id):
    brand = Brand.query.get_or_404(brand_id)
    
    if request.method == 'POST':
        brand.name_uz = request.form.get('name_uz')
        brand.name_ru = request.form.get('name_ru')
        brand.name_en = request.form.get('name_en')
        brand.name = brand.name_uz
        brand.website = request.form.get('website', '')
        brand.order = int(request.form.get('order', 0))
        brand.is_active = request.form.get('is_active') == 'on'
        
        # Logo fayl yangilash
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename:
            filename = secure_filename(logo_file.filename)
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            filepath = os.path.join('brands', filename)
            os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'brands'), exist_ok=True)
            logo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
            brand.logo = filepath
        
        db.session.commit()
        flash('Brend yangilandi!', 'success')
        return redirect(url_for('admin_brands'))
    
    return render_template('admin/brand_form.html', brand=brand)

@app.route('/admin/brand/<int:brand_id>/delete', methods=['POST'])
@login_required
def admin_brand_delete(brand_id):
    brand = Brand.query.get_or_404(brand_id)
    db.session.delete(brand)
    db.session.commit()
    flash('Brend o\'chirildi!', 'success')
    return redirect(url_for('admin_brands'))

# ==================== Mijozlar CRUD ====================
@app.route('/admin/clients')
@login_required
def admin_clients():
    clients = Client.query.order_by(Client.order).all()
    return render_template('admin/clients.html', clients=clients)

@app.route('/admin/client/add', methods=['GET', 'POST'])
@login_required
def admin_client_add():
    if request.method == 'POST':
        name_uz = request.form.get('name_uz')
        name_ru = request.form.get('name_ru') or auto_translate(name_uz, 'ru')
        name_en = request.form.get('name_en') or auto_translate(name_uz, 'en')
        description_uz = request.form.get('description_uz')
        description_ru = request.form.get('description_ru') or (auto_translate(description_uz, 'ru') if description_uz else '')
        description_en = request.form.get('description_en') or (auto_translate(description_uz, 'en') if description_uz else '')
        order = int(request.form.get('order', 0))
        is_active = request.form.get('is_active') == 'on'
        
        # Rasm yuklash
        photo_file = request.files.get('photo')
        filepath = None
        if photo_file and photo_file.filename:
            filename = secure_filename(photo_file.filename)
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            filepath = os.path.join('clients', filename)
            os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'clients'), exist_ok=True)
            photo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
        
        client = Client(
            name=name_uz,
            name_uz=name_uz,
            name_ru=name_ru,
            name_en=name_en,
            description_uz=description_uz,
            description_ru=description_ru,
            description_en=description_en,
            photo=filepath,
            order=order,
            is_active=is_active
        )
        db.session.add(client)
        db.session.commit()
        flash('Mijoz qo\'shildi!', 'success')
        return redirect(url_for('admin_clients'))
    
    return render_template('admin/client_form.html', client=None)

@app.route('/admin/client/<int:client_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_client_edit(client_id):
    client = Client.query.get_or_404(client_id)
    
    if request.method == 'POST':
        client.name_uz = request.form.get('name_uz')
        client.name = client.name_uz
        client.name_ru = request.form.get('name_ru') or auto_translate(client.name_uz, 'ru')
        client.name_en = request.form.get('name_en') or auto_translate(client.name_uz, 'en')
        client.description_uz = request.form.get('description_uz')
        client.description_ru = request.form.get('description_ru') or (auto_translate(client.description_uz, 'ru') if client.description_uz else '')
        client.description_en = request.form.get('description_en') or (auto_translate(client.description_uz, 'en') if client.description_uz else '')
        client.order = int(request.form.get('order', 0))
        client.is_active = request.form.get('is_active') == 'on'
        
        photo_file = request.files.get('photo')
        if photo_file and photo_file.filename:
            filename = secure_filename(photo_file.filename)
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            filepath = os.path.join('clients', filename)
            os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'clients'), exist_ok=True)
            photo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
            client.photo = filepath
        
        db.session.commit()
        flash('Mijoz yangilandi!', 'success')
        return redirect(url_for('admin_clients'))
    
    return render_template('admin/client_form.html', client=client)

@app.route('/admin/client/<int:client_id>/delete', methods=['POST'])
@login_required
def admin_client_delete(client_id):
    client = Client.query.get_or_404(client_id)
    db.session.delete(client)
    db.session.commit()
    flash('Mijoz o\'chirildi!', 'success')
    return redirect(url_for('admin_clients'))

# ==================== Birinchi tashrifchilar ====================
@app.route('/admin/first-visits')
@login_required
def admin_first_visits():
    visits = FirstVisit.query.order_by(FirstVisit.created_at.desc()).all()
    interest_names = {
        'clinic': 'Klinika uchun mebel',
        'restaurant': 'Restoran/kafe uchun mebel',
        'home': 'Uy uchun mebel'
    }
    return render_template('admin/first_visits.html', visits=visits, interest_names=interest_names)

@app.route('/admin/category/add', methods=['GET', 'POST'])
@login_required
def admin_category_add():
    if request.method == 'POST':
        name_uz = request.form.get('name_uz') or request.form.get('name')
        
        # Auto-translate to Russian and English
        name_ru = auto_translate(name_uz, 'ru')
        name_en = auto_translate(name_uz, 'en')
        
        slug = request.form.get('slug') or name_uz.lower().replace(' ', '-')
        # Slug takrorlanmasligini ta'minlash
        base_slug = slug
        counter = 1
        while Category.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        image = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join('categories', filename)
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'categories'), exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
                image = filepath
        
        main_category_id = request.form.get('main_category_id', type=int) or None
        
        try:
            category = Category(name=name_uz, name_uz=name_uz, name_ru=name_ru, name_en=name_en, slug=slug, image=image, main_category_id=main_category_id)
            db.session.add(category)
            db.session.commit()
            flash('Kategoriya qo\'shildi!', 'success')
            return redirect(url_for('admin_categories'))
        except Exception as e:
            db.session.rollback()
            flash(f'Xatolik: {str(e)}', 'error')
            main_categories = MainCategory.query.all()
            return render_template('admin/category_form.html', main_categories=main_categories)
    
    main_categories = MainCategory.query.all()
    return render_template('admin/category_form.html', main_categories=main_categories)

@app.route('/admin/category/<int:category_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_category_edit(category_id):
    category = Category.query.get_or_404(category_id)
    
    if request.method == 'POST':
        category.name_uz = request.form.get('name_uz') or request.form.get('name')
        category.name = category.name_uz
        
        # Auto-translate if fields are empty
        if not request.form.get('name_ru'):
            category.name_ru = auto_translate(category.name_uz, 'ru')
        else:
            category.name_ru = request.form.get('name_ru')
            
        if not request.form.get('name_en'):
            category.name_en = auto_translate(category.name_uz, 'en')
        else:
            category.name_en = request.form.get('name_en')
        
        new_slug = request.form.get('slug') or category.name_uz.lower().replace(' ', '-')
        # Slug takrorlanmasligini ta'minlash (faqat boshqa kategoriyalar bilan)
        if new_slug != category.slug:
            base_slug = new_slug
            counter = 1
            while Category.query.filter(Category.slug == new_slug, Category.id != category.id).first():
                new_slug = f"{base_slug}-{counter}"
                counter += 1
        category.slug = new_slug
        category.main_category_id = request.form.get('main_category_id', type=int) or None
        
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join('categories', filename)
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'categories'), exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
                category.image = filepath
        
        try:
            db.session.commit()
            flash('Kategoriya yangilandi!', 'success')
            return redirect(url_for('admin_categories'))
        except Exception as e:
            db.session.rollback()
            flash(f'Xatolik: {str(e)}', 'error')
    
    main_categories = MainCategory.query.all()
    return render_template('admin/category_form.html', category=category, main_categories=main_categories)

@app.route('/admin/category/<int:category_id>/delete', methods=['POST'])
@login_required
def admin_category_delete(category_id):
    category = Category.query.get_or_404(category_id)
    
    # Check if category has products
    if category.products:
        flash('Bu kategoriyada mahsulotlar bor. Avval mahsulotlarni o\'chiring!', 'error')
        return redirect(url_for('admin_categories'))
    
    db.session.delete(category)
    db.session.commit()
    flash('Kategoriya o\'chirildi!', 'success')
    return redirect(url_for('admin_categories'))

@app.route('/admin/orders')
@login_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/order/<int:order_id>/update-status', methods=['POST'])
@login_required
def admin_order_update_status(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = request.form.get('status')
    db.session.commit()
    flash('Buyurtma holati yangilandi!', 'success')
    return redirect(url_for('admin_orders'))

@app.route('/admin/portfolios')
@login_required
def admin_portfolios():
    portfolios = Portfolio.query.order_by(Portfolio.created_at.desc()).all()
    return render_template('admin/portfolios.html', portfolios=portfolios)

@app.route('/admin/portfolio/add', methods=['GET', 'POST'])
@login_required
def admin_portfolio_add():
    if request.method == 'POST':
        title_uz = request.form.get('title_uz')
        description_uz = request.form.get('description_uz')
        room_type_uz = request.form.get('room_type_uz')
        
        # Auto-translate to Russian and English
        title_ru = auto_translate(title_uz, 'ru')
        title_en = auto_translate(title_uz, 'en')
        description_ru = auto_translate(description_uz, 'ru') if description_uz else None
        description_en = auto_translate(description_uz, 'en') if description_uz else None
        
        before_image = None
        after_image = None
        
        if 'before_image' in request.files:
            file = request.files['before_image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join('portfolio', filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
                before_image = filepath
        
        if 'after_image' in request.files:
            file = request.files['after_image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join('portfolio', filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
                after_image = filepath
        
        portfolio = Portfolio(
            title=title_uz,
            title_uz=title_uz,
            description=description_uz,
            description_uz=description_uz,
            room_type=room_type_uz,
            room_type_uz=room_type_uz,
            before_image=before_image,
            after_image=after_image
        )
        db.session.add(portfolio)
        db.session.commit()
        flash('Portfolio qo\'shildi!', 'success')
        return redirect(url_for('admin_portfolios'))
    
    return render_template('admin/portfolio_form.html')

@app.route('/admin/portfolio/<int:portfolio_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_portfolio_edit(portfolio_id):
    portfolio = Portfolio.query.get_or_404(portfolio_id)
    
    if request.method == 'POST':
        portfolio.title_uz = request.form.get('title_uz')
        portfolio.title = portfolio.title_uz
        portfolio.description_uz = request.form.get('description_uz')
        portfolio.description = portfolio.description_uz
        portfolio.room_type_uz = request.form.get('room_type_uz')
        portfolio.room_type = portfolio.room_type_uz
        
        # Auto-translate to Russian and English
        portfolio.title_ru = auto_translate(portfolio.title_uz, 'ru')
        portfolio.title_en = auto_translate(portfolio.title_uz, 'en')
        portfolio.description_ru = auto_translate(portfolio.description_uz, 'ru') if portfolio.description_uz else None
        portfolio.description_en = auto_translate(portfolio.description_uz, 'en') if portfolio.description_uz else None
        
        if 'before_image' in request.files:
            file = request.files['before_image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join('portfolio', filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
                portfolio.before_image = filepath
        
        if 'after_image' in request.files:
            file = request.files['after_image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join('portfolio', filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
                portfolio.after_image = filepath
        
        db.session.commit()
        flash('Portfolio yangilandi!', 'success')
        return redirect(url_for('admin_portfolios'))
    
    return render_template('admin/portfolio_form.html', portfolio=portfolio)

@app.route('/admin/portfolio/<int:portfolio_id>/delete', methods=['POST'])
@login_required
def admin_portfolio_delete(portfolio_id):
    portfolio = Portfolio.query.get_or_404(portfolio_id)
    if portfolio.after_image:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], portfolio.after_image))
        except:
            pass
    if portfolio.before_image:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], portfolio.before_image))
        except:
            pass
    db.session.delete(portfolio)
    db.session.commit()
    flash('Portfolio o\'chirildi!', 'success')
    return redirect(url_for('admin_portfolios'))


@app.route('/stores')
def stores():
    """Stores page with map"""
    lang = session.get('language', 'uz')
    stores_list = Store.query.all()
    return render_template('stores.html', stores=stores_list, lang=lang)

@app.route('/api/stores')
def api_stores():
    """API endpoint for stores - returns JSON"""
    lang = session.get('language', 'uz')
    stores = Store.query.all()
    
    stores_data = []
    for store in stores:
        stores_data.append({
            'id': store.id,
            'name': store.get_name(lang),
            'address': store.get_address(lang),
            'phone': store.phone,
            'email': store.email,
            'latitude': store.latitude,
            'longitude': store.longitude,
            'working_hours': store.working_hours_uz if lang == 'uz' else (store.working_hours_ru if lang == 'ru' else store.working_hours_en)
        })
    
    return jsonify(stores_data)

@app.route('/api/main-category-products/<slug>')
def api_main_category_products(slug):
    """API endpoint for main category products with search and filters"""
    main_category = MainCategory.query.filter_by(slug=slug).first_or_404()
    lang = get_locale()
    rate = get_exchange_rate()
    
    # Get query parameters
    search = request.args.get('search', '').strip()
    category_id = request.args.get('category', type=int)
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    sort_by = request.args.get('sort', 'default')  # default, price_asc, price_desc, name_asc
    
    # Get categories for this main category
    categories = Category.query.filter_by(main_category_id=main_category.id).all()
    category_ids = [c.id for c in categories]
    
    # Base query
    query = Product.query.filter(Product.category_id.in_(category_ids)) if category_ids else Product.query.filter(False)
    
    # Apply filters
    if category_id:
        query = query.filter(Product.category_id == category_id)
    
    if search:
        # Search in name fields
        search_filter = db.or_(
            Product.name_uz.ilike(f'%{search}%'),
            Product.name_ru.ilike(f'%{search}%'),
            Product.name_en.ilike(f'%{search}%'),
            Product.name.ilike(f'%{search}%')
        )
        query = query.filter(search_filter)
    
    if min_price is not None:
        query = query.filter(Product.price >= min_price / rate)
    if max_price is not None:
        query = query.filter(Product.price <= max_price / rate)
    
    # Apply sorting
    if sort_by == 'price_asc':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'price_desc':
        query = query.order_by(Product.price.desc())
    elif sort_by == 'name_asc':
        query = query.order_by(Product.name_uz.asc())
    else:
        query = query.order_by(Product.created_at.desc())
    
    products = query.all()
    
    # Serialize products
    products_data = []
    for product in products:
        images = json.loads(product.images) if product.images else []
        products_data.append({
            'id': product.id,
            'name': product.get_name(lang),
            'description': product.get_description(lang),
            'price': product.price * rate,
            'price_formatted': f"{product.price * rate:,.0f}",
            'material': product.get_material(lang),
            'size': product.size,
            'images': images,
            'category_id': product.category_id,
            'category_name': product.category.get_name(lang) if product.category else '',
            'is_bestseller': product.is_bestseller,
            'warranty': product.warranty_uz if lang == 'uz' else (product.warranty_ru if lang == 'ru' else product.warranty_en) if product.warranty else None
        })
    
    # Get categories data
    categories_data = []
    for cat in categories:
        categories_data.append({
            'id': cat.id,
            'name': cat.get_name(lang),
            'image': cat.image
        })
    
    return jsonify({
        'products': products_data,
        'categories': categories_data,
        'total': len(products_data)
    })

@app.route('/admin/stores')
@login_required
def admin_stores():
    """Admin panel - Stores list"""
    stores = Store.query.order_by(Store.created_at.desc()).all()
    return render_template('admin/stores.html', stores=stores)

@app.route('/admin/store/add', methods=['GET', 'POST'])
@login_required
def admin_store_add():
    """Admin panel - Add new store"""
    if request.method == 'POST':
        try:
            store = Store(
                name_uz=request.form.get('name_uz', '').strip(),
                name_ru=request.form.get('name_ru', '').strip() or auto_translate(request.form.get('name_uz', '').strip(), 'ru'),
                name_en=request.form.get('name_en', '').strip() or auto_translate(request.form.get('name_uz', '').strip(), 'en'),
                address_uz=request.form.get('address_uz', '').strip(),
                address_ru=request.form.get('address_ru', '').strip() or auto_translate(request.form.get('address_uz', '').strip(), 'ru'),
                address_en=request.form.get('address_en', '').strip() or auto_translate(request.form.get('address_uz', '').strip(), 'en'),
                phone=request.form.get('phone', '').strip(),
                email=request.form.get('email', '').strip(),
                latitude=float(request.form.get('latitude', 0)) if request.form.get('latitude') else None,
                longitude=float(request.form.get('longitude', 0)) if request.form.get('longitude') else None,
                working_hours_uz=request.form.get('working_hours_uz', '').strip(),
                working_hours_ru=request.form.get('working_hours_ru', '').strip() or auto_translate(request.form.get('working_hours_uz', '').strip(), 'ru'),
                working_hours_en=request.form.get('working_hours_en', '').strip() or auto_translate(request.form.get('working_hours_uz', '').strip(), 'en')
            )
            db.session.add(store)
            db.session.commit()
            flash('Filial muvaffaqiyatli qo\'shildi!', 'success')
            return redirect(url_for('admin_stores'))
        except Exception as e:
            db.session.rollback()
            flash(f'Xatolik: {str(e)}', 'error')
    
    return render_template('admin/store_form.html', store=None)

@app.route('/admin/store/<int:store_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_store_edit(store_id):
    """Admin panel - Edit store"""
    store = Store.query.get_or_404(store_id)
    
    if request.method == 'POST':
        try:
            store.name_uz = request.form.get('name_uz', '').strip()
            store.name_ru = request.form.get('name_ru', '').strip() or store.name_ru
            store.name_en = request.form.get('name_en', '').strip() or store.name_en
            store.address_uz = request.form.get('address_uz', '').strip()
            store.address_ru = request.form.get('address_ru', '').strip() or store.address_ru
            store.address_en = request.form.get('address_en', '').strip() or store.address_en
            store.phone = request.form.get('phone', '').strip()
            store.email = request.form.get('email', '').strip()
            store.latitude = float(request.form.get('latitude', 0)) if request.form.get('latitude') else None
            store.longitude = float(request.form.get('longitude', 0)) if request.form.get('longitude') else None
            store.working_hours_uz = request.form.get('working_hours_uz', '').strip()
            store.working_hours_ru = request.form.get('working_hours_ru', '').strip() or store.working_hours_ru
            store.working_hours_en = request.form.get('working_hours_en', '').strip() or store.working_hours_en
            
            db.session.commit()
            flash('Filial muvaffaqiyatli yangilandi!', 'success')
            return redirect(url_for('admin_stores'))
        except Exception as e:
            db.session.rollback()
            flash(f'Xatolik: {str(e)}', 'error')
    
    return render_template('admin/store_form.html', store=store)

@app.route('/admin/store/<int:store_id>/delete', methods=['POST'])
@login_required
def admin_store_delete(store_id):
    """Admin panel - Delete store"""
    store = Store.query.get_or_404(store_id)
    try:
        db.session.delete(store)
        db.session.commit()
        flash('Filial muvaffaqiyatli o\'chirildi!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Xatolik: {str(e)}', 'error')
    return redirect(url_for('admin_stores'))

@app.route('/admin/user-activity')
@login_required
def admin_user_activity():
    """User activity tracking sahifasi - faqat statistika"""
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    # Unique visitors (session_id bo'yicha) - asosiy statistika
    unique_visitors = db.session.query(func.count(func.distinct(UserActivity.session_id))).scalar()
    
    # Sahifaga tashriflar (unique session_id bo'yicha)
    unique_page_visits = db.session.query(
        func.count(func.distinct(UserActivity.session_id))
    ).filter_by(activity_type='page_view').scalar()
    
    # Mahsulot ko'rishlar (unique session_id bo'yicha)
    unique_product_views = db.session.query(
        func.count(func.distinct(UserActivity.session_id))
    ).filter_by(activity_type='product_view').scalar()
    
    # Bugungi statistika
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    
    today_unique_visitors = db.session.query(
        func.count(func.distinct(UserActivity.session_id))
    ).filter(UserActivity.created_at >= today_start).scalar()
    
    today_unique_page_visits = db.session.query(
        func.count(func.distinct(UserActivity.session_id))
    ).filter(
        UserActivity.created_at >= today_start,
        UserActivity.activity_type == 'page_view'
    ).scalar()
    
    today_unique_product_views = db.session.query(
        func.count(func.distinct(UserActivity.session_id))
    ).filter(
        UserActivity.created_at >= today_start,
        UserActivity.activity_type == 'product_view'
    ).scalar()
    
    # Haftalik statistika (7 kun)
    week_ago = datetime.utcnow() - timedelta(days=7)
    week_unique_visitors = db.session.query(
        func.count(func.distinct(UserActivity.session_id))
    ).filter(UserActivity.created_at >= week_ago).scalar()
    
    week_unique_page_visits = db.session.query(
        func.count(func.distinct(UserActivity.session_id))
    ).filter(
        UserActivity.created_at >= week_ago,
        UserActivity.activity_type == 'page_view'
    ).scalar()
    
    week_unique_product_views = db.session.query(
        func.count(func.distinct(UserActivity.session_id))
    ).filter(
        UserActivity.created_at >= week_ago,
        UserActivity.activity_type == 'product_view'
    ).scalar()
    
    # Oylik statistika (30 kun)
    month_ago = datetime.utcnow() - timedelta(days=30)
    month_unique_visitors = db.session.query(
        func.count(func.distinct(UserActivity.session_id))
    ).filter(UserActivity.created_at >= month_ago).scalar()
    
    month_unique_page_visits = db.session.query(
        func.count(func.distinct(UserActivity.session_id))
    ).filter(
        UserActivity.created_at >= month_ago,
        UserActivity.activity_type == 'page_view'
    ).scalar()
    
    month_unique_product_views = db.session.query(
        func.count(func.distinct(UserActivity.session_id))
    ).filter(
        UserActivity.created_at >= month_ago,
        UserActivity.activity_type == 'product_view'
    ).scalar()
    
    # Eng ko'p ko'rilgan sahifalar (unique session_id bo'yicha)
    top_pages = db.session.query(
        UserActivity.page_name,
        func.count(func.distinct(UserActivity.session_id)).label('count')
    ).filter_by(activity_type='page_view').group_by(UserActivity.page_name).order_by(func.count(func.distinct(UserActivity.session_id)).desc()).limit(15).all()
    
    # Eng ko'p ko'rilgan mahsulotlar (unique session_id bo'yicha) - faqat mavjud mahsulotlar
    top_products = db.session.query(
        UserActivity.product_name,
        func.count(func.distinct(UserActivity.session_id)).label('count')
    ).join(Product, UserActivity.product_id == Product.id).filter(
        UserActivity.activity_type == 'product_view',
        UserActivity.product_name.isnot(None),
        UserActivity.product_id.isnot(None)
    ).group_by(
        UserActivity.product_name
    ).order_by(
        func.count(func.distinct(UserActivity.session_id)).desc()
    ).limit(10).all()
    
    # Oxirgi 7 kunlik kunlik statistika (grafiklar uchun - unique session_id)
    daily_stats = []
    for i in range(6, -1, -1):
        date = (datetime.utcnow() - timedelta(days=i)).date()
        date_start = datetime.combine(date, datetime.min.time())
        date_end = datetime.combine(date, datetime.max.time())
        
        day_unique_visitors = db.session.query(
            func.count(func.distinct(UserActivity.session_id))
        ).filter(
            UserActivity.created_at >= date_start,
            UserActivity.created_at <= date_end
        ).scalar()
        
        daily_stats.append({
            'date': date.strftime('%Y-%m-%d'),
            'date_display': date.strftime('%d.%m'),
            'unique_visitors': day_unique_visitors
        })
    
    # Soatlik statistika (bugungi kun uchun - unique session_id)
    hourly_stats = []
    for hour in range(24):
        hour_start = today_start + timedelta(hours=hour)
        hour_end = hour_start + timedelta(hours=1)
        
        hour_unique_visitors = db.session.query(
            func.count(func.distinct(UserActivity.session_id))
        ).filter(
            UserActivity.created_at >= hour_start,
            UserActivity.created_at < hour_end
        ).scalar()
        
        hourly_stats.append({
            'hour': hour,
            'unique_visitors': hour_unique_visitors
        })
    
    stats = {
        'unique_visitors': unique_visitors,
        'unique_page_visits': unique_page_visits,
        'unique_product_views': unique_product_views,
        'today_unique_visitors': today_unique_visitors,
        'today_unique_page_visits': today_unique_page_visits,
        'today_unique_product_views': today_unique_product_views,
        'week_unique_visitors': week_unique_visitors,
        'week_unique_page_visits': week_unique_page_visits,
        'week_unique_product_views': week_unique_product_views,
        'month_unique_visitors': month_unique_visitors,
        'month_unique_page_visits': month_unique_page_visits,
        'month_unique_product_views': month_unique_product_views,
        'top_pages': top_pages,
        'top_products': top_products,
        'daily_stats': daily_stats,
        'hourly_stats': hourly_stats
    }
    
    return render_template('admin/user_activity.html', stats=stats)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context():
        # Ensure upload directories exist
        ensure_upload_dirs()
        # Database migration: Add new columns for translations
        try:
            # Check and add columns to Category table
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            category_columns = [col['name'] for col in inspector.get_columns('category')]
            
            if 'name_ru' not in category_columns:
                db.session.execute(text('ALTER TABLE category ADD COLUMN name_ru VARCHAR(100)'))
                print("Added name_ru column to category table")
            
            if 'name_en' not in category_columns:
                db.session.execute(text('ALTER TABLE category ADD COLUMN name_en VARCHAR(100)'))
                print("Added name_en column to category table")
            
            # Check and add columns to Product table
            product_columns = [col['name'] for col in inspector.get_columns('product')]
            
            if 'name_ru' not in product_columns:
                db.session.execute(text('ALTER TABLE product ADD COLUMN name_ru VARCHAR(200)'))
                print("Added name_ru column to product table")
            
            if 'name_en' not in product_columns:
                db.session.execute(text('ALTER TABLE product ADD COLUMN name_en VARCHAR(200)'))
                print("Added name_en column to product table")
            
            if 'description_ru' not in product_columns:
                db.session.execute(text('ALTER TABLE product ADD COLUMN description_ru TEXT'))
                print("Added description_ru column to product table")
            
            if 'description_en' not in product_columns:
                db.session.execute(text('ALTER TABLE product ADD COLUMN description_en TEXT'))
                print("Added description_en column to product table")
            
            # Check and add colors column to Product table
            if 'colors' not in product_columns:
                db.session.execute(text('ALTER TABLE product ADD COLUMN colors TEXT'))
                db.session.commit()
                print("Added colors column to product table")
            
            # Check and add discount column to Product table
            if 'discount' not in product_columns:
                db.session.execute(text('ALTER TABLE product ADD COLUMN discount INTEGER DEFAULT 0'))
                db.session.commit()
                print("Added discount column to product table")
            
            # Check and create store table
            try:
                store_columns = [col['name'] for col in inspector.get_columns('store')]
                print("store table exists")
            except Exception as e:
                # Create store table
                db.session.execute(text('''
                    CREATE TABLE store (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name_uz VARCHAR(200) NOT NULL,
                        name_ru VARCHAR(200),
                        name_en VARCHAR(200),
                        address_uz TEXT NOT NULL,
                        address_ru TEXT,
                        address_en TEXT,
                        phone VARCHAR(50),
                        email VARCHAR(100),
                        latitude FLOAT,
                        longitude FLOAT,
                        working_hours_uz VARCHAR(200),
                        working_hours_ru VARCHAR(200),
                        working_hours_en VARCHAR(200),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                '''))
                db.session.commit()
                print("Created store table")
            
            # Check and create user_activity table
            try:
                activity_columns = [col['name'] for col in inspector.get_columns('user_activity')]
                print("user_activity table exists")
            except Exception as e:
                # Table doesn't exist, create it
                db.create_all()
                print(f"Created user_activity table")
            
            if 'material_ru' not in product_columns:
                db.session.execute(text('ALTER TABLE product ADD COLUMN material_ru VARCHAR(100)'))
                print("Added material_ru column to product table")
            
            if 'material_en' not in product_columns:
                db.session.execute(text('ALTER TABLE product ADD COLUMN material_en VARCHAR(100)'))
                print("Added material_en column to product table")
            
            # Check and add columns to Portfolio table
            try:
                portfolio_columns = [col['name'] for col in inspector.get_columns('portfolio')]
                
                if 'title_ru' not in portfolio_columns:
                    db.session.execute(text('ALTER TABLE portfolio ADD COLUMN title_ru VARCHAR(200)'))
                    print("Added title_ru column to portfolio table")
                
                if 'title_en' not in portfolio_columns:
                    db.session.execute(text('ALTER TABLE portfolio ADD COLUMN title_en VARCHAR(200)'))
                    print("Added title_en column to portfolio table")
                
                if 'description_ru' not in portfolio_columns:
                    db.session.execute(text('ALTER TABLE portfolio ADD COLUMN description_ru TEXT'))
                    print("Added description_ru column to portfolio table")
                
                if 'description_en' not in portfolio_columns:
                    db.session.execute(text('ALTER TABLE portfolio ADD COLUMN description_en TEXT'))
                    print("Added description_en column to portfolio table")
            except Exception as e:
                print(f"Portfolio migration note: {e}")
            
            # Check and create main_category table
            try:
                main_category_columns = [col['name'] for col in inspector.get_columns('main_category')]
                print("main_category table exists")
            except Exception as e:
                # Table doesn't exist, create it
                db.create_all()
                print("Created main_category table")
                
            # Check and add main_category_id to category table
            try:
                category_columns = [col['name'] for col in inspector.get_columns('category')]
                if 'main_category_id' not in category_columns:
                    db.session.execute(text('ALTER TABLE category ADD COLUMN main_category_id INTEGER'))
                    print("Added main_category_id column to category table")
            except Exception as e:
                print(f"Category migration note: {e}")
            
            # Check and add main_category_id and text translations to review table
            try:
                review_columns = [col['name'] for col in inspector.get_columns('review')]
                if 'main_category_id' not in review_columns:
                    db.session.execute(text('ALTER TABLE review ADD COLUMN main_category_id INTEGER'))
                    print("Added main_category_id column to review table")
                if 'text_ru' not in review_columns:
                    db.session.execute(text('ALTER TABLE review ADD COLUMN text_ru TEXT'))
                    print("Added text_ru column to review table")
                if 'text_en' not in review_columns:
                    db.session.execute(text('ALTER TABLE review ADD COLUMN text_en TEXT'))
                    print("Added text_en column to review table")
            except Exception as e:
                print(f"Review migration note: {e}")
            
            # Commit all migration changes
            try:
                db.session.commit()
            except Exception as e:
                print(f"Migration commit error: {e}")
                try:
                    db.session.rollback()
                except:
                    pass
        except Exception as e:
            print(f"Migration error: {e}")
            try:
                db.session.rollback()
            except:
                pass
        
        # Create all tables including new models (UserActivity, etc.)
        try:
            db.create_all()
        except Exception as e:
            print(f"Create all tables error: {e}")
        
        # Create default admin user if not exists
        if not Admin.query.first():
            admin = Admin(
                username='admin',
                password=generate_password_hash('admin123')
            )
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: username='admin', password='admin123'")

        # Create default exchange rate if not exists
        if not ExchangeRate.query.first():
            rate = ExchangeRate(value=12000.0)
            db.session.add(rate)
            db.session.commit()
            print("Default exchange rate created: 1 USD = 12000 UZS")
        
        # Create default main categories if not exists
        if not MainCategory.query.first():
            main_categories = [
                MainCategory(
                    name_uz='Cafe & Restaurant',
                    name_ru='Кафе и Ресторан',
                    name_en='Cafe & Restaurant',
                    slug='cafe-restaurant',
                    description_uz='Cafe va Restaurantlar uchun maxsus mebellar',
                    description_ru='Специальная мебель для кафе и ресторанов',
                    description_en='Special furniture for cafes and restaurants',
                    order=1
                ),
                MainCategory(
                    name_uz='Xonadon',
                    name_ru='Дом',
                    name_en='Home',
                    slug='home',
                    description_uz='Uy va xonadonlar uchun mebellar',
                    description_ru='Мебель для дома',
                    description_en='Furniture for home',
                    order=2
                ),
                MainCategory(
                    name_uz='Clinika',
                    name_ru='Клиника',
                    name_en='Clinic',
                    slug='clinic',
                    description_uz='Tibbiy muassasalar uchun mebellar',
                    description_ru='Мебель для медицинских учреждений',
                    description_en='Furniture for medical facilities',
                    order=3
                )
            ]
            for mc in main_categories:
                db.session.add(mc)
            db.session.commit()
            print("Created default main categories: Cafe & Restaurant, Xonadon, Clinika")
    
    # Production mode - Render.com will use gunicorn
    if os.environ.get('RENDER') or os.environ.get('PORT'):
        # On Render.com, gunicorn will handle the app
        # Port is automatically set by Render
        pass
    else:
        # Local development
        port = int(os.environ.get('PORT', 5003))
        app.run(host='0.0.0.0', port=port, debug=True)

