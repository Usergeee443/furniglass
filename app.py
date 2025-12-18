from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from config import Config
from db import db
from models import Admin, Product, Category, Order, Review, Portfolio, FAQ, ExchangeRate
from translations import TRANSLATIONS, get_translation, t
import os
import json
import urllib.request
import urllib.parse

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
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'products'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'categories'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'portfolio'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'designs'), exist_ok=True)

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

# ============ FRONTEND ROUTES ============

@app.route('/')
def index():
    categories = Category.query.limit(4).all()
    bestsellers = Product.query.filter_by(is_bestseller=True).limit(4).all()
    reviews = Review.query.order_by(Review.created_at.desc()).limit(5).all()
    portfolios = Portfolio.query.order_by(Portfolio.created_at.desc()).limit(3).all()
    return render_template('index.html', categories=categories, bestsellers=bestsellers, 
                         reviews=reviews, portfolios=portfolios)

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
                         search_query=search_query)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)

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

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Quick order form
        phone = request.form.get('phone')
        name = request.form.get('name')
        message = request.form.get('message')
        
        order = Order(
            furniture_type='Tezkor buyurtma',
            phone=phone,
            name=name,
            address=message
        )
        db.session.add(order)
        db.session.commit()
        flash('Buyurtmangiz qabul qilindi!', 'success')
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
    
    cart = get_cart()
    
    # Check if product already in cart
    for item in cart:
        if item['product_id'] == product_id:
            item['quantity'] += quantity
            session.modified = True
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'cart_count': get_cart_count(), 'message': 'Mahsulot savatchaga qo\'shildi!'})
            flash('Mahsulot savatchaga qo\'shildi!', 'success')
            return redirect(request.referrer or url_for('products'))
    
    # Add new item
    cart.append({
        'product_id': product_id,
        'quantity': quantity
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
        
        # Get cart products for order
        products_list = []
        total = 0
        rate = get_exchange_rate()
        for item in cart_items:
            product = Product.query.get(item['product_id'])
            if product:
                products_list.append(f"{product.name_uz} x{item['quantity']}")
                total += product.price * rate * item['quantity']
        
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
        size = request.form.get('size')
        category_id = int(request.form.get('category_id'))
        is_bestseller = request.form.get('is_bestseller') == 'on'
        
        images = []
        if 'images' in request.files:
            files = request.files.getlist('images')
            # 5 tagacha rasm cheklash
            files = files[:5]
            
            # Asosiy rasm indexini olish (agar belgilangan bo'lsa)
            main_image_index = int(request.form.get('main_image_index', 0))
            
            for idx, file in enumerate(files):
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join('products', filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
                    images.append(filepath)
            
            # Asosiy rasmni birinchi o'ringa qo'yish
            if images and main_image_index > 0 and main_image_index < len(images):
                main_image = images.pop(main_image_index)
                images.insert(0, main_image)
        
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
            warranty=warranty_uz,
            warranty_uz=warranty_uz,
            images=json.dumps(images)
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
        product.size = request.form.get('size')
        product.category_id = int(request.form.get('category_id'))
        product.is_bestseller = request.form.get('is_bestseller') == 'on'
        
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
                        filepath = os.path.join('products', filename)
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

@app.route('/admin/categories')
@login_required
def admin_categories():
    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/category/add', methods=['GET', 'POST'])
@login_required
def admin_category_add():
    if request.method == 'POST':
        name_uz = request.form.get('name_uz') or request.form.get('name')
        
        # Auto-translate to Russian and English
        name_ru = auto_translate(name_uz, 'ru')
        name_en = auto_translate(name_uz, 'en')
        
        slug = request.form.get('slug') or name_uz.lower().replace(' ', '-')
        
        image = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join('categories', filename)
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'categories'), exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
                image = filepath
        
        category = Category(name=name_uz, name_uz=name_uz, name_ru=name_ru, name_en=name_en, slug=slug, image=image)
        db.session.add(category)
        db.session.commit()
        flash('Kategoriya qo\'shildi!', 'success')
        return redirect(url_for('admin_categories'))
    
    return render_template('admin/category_form.html')

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
        
        category.slug = request.form.get('slug') or category.name_uz.lower().replace(' ', '-')
        
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join('categories', filename)
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'categories'), exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
                category.image = filepath
        
        db.session.commit()
        flash('Kategoriya yangilandi!', 'success')
        return redirect(url_for('admin_categories'))
    
    return render_template('admin/category_form.html', category=category)

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
    db.session.delete(portfolio)
    db.session.commit()
    flash('Portfolio o\'chirildi!', 'success')
    return redirect(url_for('admin_portfolios'))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context():
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
            
            db.session.commit()
        except Exception as e:
            print(f"Migration note: {e}")
            db.session.rollback()
        
        db.create_all()
        
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
    
    app.run(debug=True)

