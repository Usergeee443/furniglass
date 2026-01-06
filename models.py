from db import db
from flask_login import UserMixin
from datetime import datetime


class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class MainCategory(db.Model):
    """Asosiy kategoriyalar: Cafe&Restaurant, Xonadon, Clinika"""
    id = db.Column(db.Integer, primary_key=True)
    name_uz = db.Column(db.String(200), nullable=False)
    name_ru = db.Column(db.String(200))
    name_en = db.Column(db.String(200))
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description_uz = db.Column(db.Text)
    description_ru = db.Column(db.Text)
    description_en = db.Column(db.Text)
    image = db.Column(db.String(200))
    icon = db.Column(db.String(100))  # Icon nomi yoki path
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    categories = db.relationship('Category', backref='main_category', lazy=True)
    reviews = db.relationship('Review', backref='main_category', lazy=True)
    
    def get_name(self, lang='uz'):
        """Get main category name in specified language"""
        if lang == 'ru' and self.name_ru:
            return self.name_ru
        elif lang == 'en' and self.name_en:
            return self.name_en
        return self.name_uz
    
    def get_description(self, lang='uz'):
        """Get main category description in specified language"""
        if lang == 'ru' and self.description_ru:
            return self.description_ru
        elif lang == 'en' and self.description_en:
            return self.description_en
        return self.description_uz or ''

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_uz = db.Column(db.String(100), nullable=False)
    name_ru = db.Column(db.String(100))  # Avtomatik tarjima
    name_en = db.Column(db.String(100))  # Avtomatik tarjima
    slug = db.Column(db.String(100), unique=True, nullable=False)
    image = db.Column(db.String(200))
    main_category_id = db.Column(db.Integer, db.ForeignKey('main_category.id'), nullable=True)
    products = db.relationship('Product', backref='category', lazy=True)
    
    def get_name(self, lang='uz'):
        """Get category name in specified language"""
        if lang == 'ru' and self.name_ru:
            return self.name_ru
        elif lang == 'en' and self.name_en:
            return self.name_en
        return self.name_uz or self.name

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_uz = db.Column(db.String(200), nullable=False)
    name_ru = db.Column(db.String(200))  # Avtomatik tarjima
    name_en = db.Column(db.String(200))  # Avtomatik tarjima
    description = db.Column(db.Text)
    description_uz = db.Column(db.Text)
    description_ru = db.Column(db.Text)  # Avtomatik tarjima
    description_en = db.Column(db.Text)  # Avtomatik tarjima
    price = db.Column(db.Float, nullable=False)
    size = db.Column(db.String(100))
    material = db.Column(db.String(100))
    material_uz = db.Column(db.String(100))
    material_ru = db.Column(db.String(100))  # Avtomatik tarjima
    material_en = db.Column(db.String(100))  # Avtomatik tarjima
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    is_bestseller = db.Column(db.Boolean, default=False)
    warranty = db.Column(db.String(50))
    warranty_uz = db.Column(db.String(50))
    images = db.Column(db.Text)  # JSON string of image paths
    colors = db.Column(db.Text)  # JSON string of color options: [{"name": "Qora", "hex": "#1a1a2e"}, ...]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_name(self, lang='uz'):
        """Get product name in specified language"""
        if lang == 'ru' and self.name_ru:
            return self.name_ru
        elif lang == 'en' and self.name_en:
            return self.name_en
        return self.name_uz or self.name
    
    def get_description(self, lang='uz'):
        """Get product description in specified language"""
        if lang == 'ru' and self.description_ru:
            return self.description_ru
        elif lang == 'en' and self.description_en:
            return self.description_en
        return self.description_uz or self.description or ''
    
    def get_material(self, lang='uz'):
        """Get product material in specified language"""
        if lang == 'ru' and self.material_ru:
            return self.material_ru
        elif lang == 'en' and self.material_en:
            return self.material_en
        return self.material_uz or self.material or ''

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    furniture_type = db.Column(db.String(200), nullable=False)
    size = db.Column(db.String(100))
    color = db.Column(db.String(50))
    material = db.Column(db.String(100))
    design_image = db.Column(db.String(200))
    phone = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100))
    address = db.Column(db.Text)
    status = db.Column(db.String(50), default='Yangi')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    text = db.Column(db.Text, nullable=False)
    text_uz = db.Column(db.Text, nullable=False)
    text_ru = db.Column(db.Text)
    text_en = db.Column(db.Text)
    rating = db.Column(db.Integer, default=5)
    main_category_id = db.Column(db.Integer, db.ForeignKey('main_category.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_text(self, lang='uz'):
        """Get review text in specified language"""
        if lang == 'ru' and self.text_ru:
            return self.text_ru
        elif lang == 'en' and self.text_en:
            return self.text_en
        return self.text_uz or self.text

class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    title_uz = db.Column(db.String(200), nullable=False)
    title_ru = db.Column(db.String(200))  # Avtomatik tarjima
    title_en = db.Column(db.String(200))  # Avtomatik tarjima
    description = db.Column(db.Text)
    description_uz = db.Column(db.Text)
    description_ru = db.Column(db.Text)  # Avtomatik tarjima
    description_en = db.Column(db.Text)  # Avtomatik tarjima
    room_type = db.Column(db.String(50))  # Yotoqxona / Zal / Oshxona
    room_type_uz = db.Column(db.String(50))
    before_image = db.Column(db.String(200))
    after_image = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_title(self, lang='uz'):
        """Get portfolio title in specified language"""
        if lang == 'ru' and self.title_ru:
            return self.title_ru
        elif lang == 'en' and self.title_en:
            return self.title_en
        return self.title_uz or self.title
    
    def get_description(self, lang='uz'):
        """Get portfolio description in specified language"""
        if lang == 'ru' and self.description_ru:
            return self.description_ru
        elif lang == 'en' and self.description_en:
            return self.description_en
        return self.description_uz or self.description or ''

class FAQ(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(300), nullable=False)
    question_uz = db.Column(db.String(300), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    answer_uz = db.Column(db.Text, nullable=False)
    order = db.Column(db.Integer, default=0)


class ExchangeRate(db.Model):
    """
    Saqlanadigan yagona yozuv:
    1 USD ning so'mdagi qiymati.
    """
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Float, nullable=False, default=12000.0)  # 1 USD = 12 000 so'm (default)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Collection(db.Model):
    """Collections - Sofa collections, Table collections, etc."""
    id = db.Column(db.Integer, primary_key=True)
    name_uz = db.Column(db.String(200), nullable=False)
    name_ru = db.Column(db.String(200))
    name_en = db.Column(db.String(200))
    description_uz = db.Column(db.Text)
    description_ru = db.Column(db.Text)
    description_en = db.Column(db.Text)
    image = db.Column(db.String(200))
    slug = db.Column(db.String(100), unique=True, nullable=False)
    category_type = db.Column(db.String(50))  # sofa, table, chair, bed, storage
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_name(self, lang='uz'):
        if lang == 'ru' and self.name_ru:
            return self.name_ru
        elif lang == 'en' and self.name_en:
            return self.name_en
        return self.name_uz
    
    def get_description(self, lang='uz'):
        if lang == 'ru' and self.description_ru:
            return self.description_ru
        elif lang == 'en' and self.description_en:
            return self.description_en
        return self.description_uz or ''


class Store(db.Model):
    """Store locations"""
    id = db.Column(db.Integer, primary_key=True)
    name_uz = db.Column(db.String(200), nullable=False)
    name_ru = db.Column(db.String(200))
    name_en = db.Column(db.String(200))
    address_uz = db.Column(db.Text, nullable=False)
    address_ru = db.Column(db.Text)
    address_en = db.Column(db.Text)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    working_hours_uz = db.Column(db.String(200))
    working_hours_ru = db.Column(db.String(200))
    working_hours_en = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_name(self, lang='uz'):
        if lang == 'ru' and self.name_ru:
            return self.name_ru
        elif lang == 'en' and self.name_en:
            return self.name_en
        return self.name_uz
    
    def get_address(self, lang='uz'):
        if lang == 'ru' and self.address_ru:
            return self.address_ru
        elif lang == 'en' and self.address_en:
            return self.address_en
        return self.address_uz


class SampleRequest(db.Model):
    """Free sample requests"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    message = db.Column(db.Text)
    status = db.Column(db.String(50), default='Yangi')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Article(db.Model):
    """Inspiration articles"""
    id = db.Column(db.Integer, primary_key=True)
    title_uz = db.Column(db.String(300), nullable=False)
    title_ru = db.Column(db.String(300))
    title_en = db.Column(db.String(300))
    content_uz = db.Column(db.Text)
    content_ru = db.Column(db.Text)
    content_en = db.Column(db.Text)
    image = db.Column(db.String(200))
    slug = db.Column(db.String(200), unique=True, nullable=False)
    category = db.Column(db.String(50))  # trends, tips, inspiration
    featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_title(self, lang='uz'):
        if lang == 'ru' and self.title_ru:
            return self.title_ru
        elif lang == 'en' and self.title_en:
            return self.title_en
        return self.title_uz
    
    def get_content(self, lang='uz'):
        if lang == 'ru' and self.content_ru:
            return self.content_ru
        elif lang == 'en' and self.content_en:
            return self.content_en
        return self.content_uz or ''


class DesignConsultation(db.Model):
    """Interior Design Service consultations"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100))
    room_type = db.Column(db.String(50))  # living, dining, bedroom, etc.
    budget = db.Column(db.String(50))
    message = db.Column(db.Text)
    status = db.Column(db.String(50), default='Yangi')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserActivity(db.Model):
    """User activity tracking - sahifalar va mahsulotlar ko'rish"""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100))  # Session ID
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    activity_type = db.Column(db.String(50))  # 'page_view', 'product_view'
    page_url = db.Column(db.String(500))  # Sahifa URL
    page_name = db.Column(db.String(200))  # Sahifa nomi (masalan: "Mahsulotlar", "Portfolio")
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)  # Agar mahsulot ko'rilgan bo'lsa
    product_name = db.Column(db.String(200))  # Mahsulot nomi
    referrer = db.Column(db.String(500))  # Qayerdan kelgan
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    product = db.relationship('Product', backref='views', lazy=True)


