from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Float, Date, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
import config

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(50))
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))
    birth_date = Column(Date)
    points = Column(Integer, default=0)
    total_spent = Column(Float, default=0.0)
    registration_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    is_registered = Column(Boolean, default=False)
    referral_code = Column(String(10), unique=True)
    referred_by = Column(Integer, ForeignKey('users.id'))
    last_welcome_back_bonus_date = Column(DateTime)
    web_login = Column(String(50), unique=True, nullable=True)  # Логин для веб-входа
    web_password_hash = Column(String(255), nullable=True)  # Хеш пароля для веб-входа
    gender = Column(String(10), nullable=True)  # 'male', 'female' или None
    
    purchases = relationship("Purchase", back_populates="user")
    referrals = relationship("User", remote_side=[id])

class Purchase(Base):
    __tablename__ = 'purchases'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    points_earned = Column(Integer, nullable=False)
    points_used = Column(Integer, default=0)
    purchase_date = Column(DateTime, default=datetime.now)
    description = Column(String(200))
    is_returned = Column(Boolean, default=False)
    return_date = Column(DateTime)
    
    user = relationship("User", back_populates="purchases")

class PointsHistory(Base):
    __tablename__ = 'points_history'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    points_change = Column(Integer, nullable=False)
    transaction_type = Column(String(50))
    description = Column(String(200))
    created_date = Column(DateTime, default=datetime.now)
    expiry_date = Column(DateTime, nullable=True)  # Дата сгорания баллов
    is_expired_processed = Column(Boolean, default=False)  # Флаг, что сгорание уже обработано

class Giveaway(Base):
    __tablename__ = 'giveaways'

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(String(1000))
    created_date = Column(DateTime, default=datetime.now)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=False)

    participants = relationship("GiveawayParticipant", back_populates="giveaway")


class GiveawayParticipant(Base):
    __tablename__ = 'giveaway_participants'
    __table_args__ = (
        UniqueConstraint('giveaway_id', 'user_id', name='uq_giveaway_participant'),
    )

    id = Column(Integer, primary_key=True)
    giveaway_id = Column(Integer, ForeignKey('giveaways.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    joined_date = Column(DateTime, default=datetime.now)

    giveaway = relationship("Giveaway", back_populates="participants")
    user = relationship("User")

class Promotion(Base):
    __tablename__ = 'promotions'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    description = Column(String(500))
    discount_percent = Column(Integer)
    points_required = Column(Integer)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)

class HolidayGift(Base):
    __tablename__ = 'holiday_gifts'
    
    id = Column(Integer, primary_key=True)
    amount = Column(Integer, nullable=False)
    description = Column(String(200))
    days_to_expire = Column(Integer, default=0)  # Срок жизни самих баллов
    start_date = Column(DateTime, default=datetime.now)
    end_date = Column(DateTime, nullable=True)  # До какого времени акция действует для новых пользователей (None = бессрочно)
    is_active = Column(Boolean, default=True)

def _resolve_database_url(original_url: str) -> str:
    """Возвращает абсолютный URL для SQLite, если указан относительный путь.
    Оставляет прочие URL без изменений.
    """
    if original_url.startswith('sqlite:///'):
        relative_path = original_url.replace('sqlite:///', '', 1)
        if not os.path.isabs(relative_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            abs_path = os.path.join(base_dir, relative_path)
            # Приводим к прямым слешам для корректного URL
            abs_path = abs_path.replace('\\', '/')
            return f"sqlite:///{abs_path}"
    return original_url

_DB_URL = _resolve_database_url(config.DATABASE_URL)

# Для SQLite в многопоточной среде (Waitress) нужен флаг check_same_thread=False
_connect_args = {"check_same_thread": False} if _DB_URL.startswith('sqlite:///') else {}

engine = create_engine(_DB_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)

def safe_migrate():
    """Безопасно добавляет недостающие колонки в существующие таблицы.
    Можно вызывать при каждом запуске — не ломает уже существующие данные.
    """
    import sqlite3
    
    # Получаем путь к файлу БД из URL
    db_path = _DB_URL.replace('sqlite:///', '')
    
    # Список нужных миграций: (таблица, колонка, тип SQL)
    migrations = [
        ('users', 'gender',                 'TEXT'),
        ('users', 'web_login',              'TEXT UNIQUE'),
        ('users', 'web_password_hash',      'TEXT'),
        ('users', 'last_welcome_back_bonus_date', 'DATETIME'),
        ('holiday_gifts', 'end_date',       'DATETIME'),
        ('holiday_gifts', 'is_active',      'INTEGER DEFAULT 1'),
        ('holiday_gifts', 'days_to_expire', 'INTEGER DEFAULT 0'),
        ('holiday_gifts', 'start_date',     'DATETIME'),
        ('points_history', 'expiry_date',   'DATETIME'),
        ('points_history', 'is_expired_processed', 'BOOLEAN DEFAULT 0'),
    ]
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        for table, column, col_type in migrations:
            # Проверяем, существует ли таблица
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if not cursor.fetchone():
                continue  # Таблица ещё не создана — create_all() займётся этим
            
            # Проверяем, существует ли колонка
            cursor.execute(f"PRAGMA table_info({table})")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            if column not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                    print(f"[DB MIGRATE] Добавлена колонка {table}.{column}")
                except Exception as e:
                    print(f"[DB MIGRATE] Ошибка добавления {table}.{column}: {e}")
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB MIGRATE] Ошибка миграции: {e}")

def init_db():
    """Инициализация базы данных - создание всех таблиц"""
    print("🔧 Инициализация базы данных...")
    Base.metadata.create_all(bind=engine)
    print("✅ База данных инициализирована!")

def get_db():
    return SessionLocal() 

def get_database_url() -> str:
    """Текущий URL подключения к БД (для диагностики)."""
    return _DB_URL

# Диагностика при импорте
try:
    print(f"[DB] Используется база данных: {_DB_URL}")
except Exception:
    pass