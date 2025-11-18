import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_url():
    """
    Получаем URL базы данных.
    На Render используем PostgreSQL, локально - SQLite
    """
    # Для Render (PostgreSQL)
    if 'DATABASE_URL' in os.environ:
        db_url = os.environ['DATABASE_URL']
        # Конвертируем postgres:// в postgresql:// для SQLAlchemy
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        logger.info("🔗 Используем PostgreSQL (Render)")
        return db_url
    # Для локальной разработки (SQLite)
    else:
        logger.info("🔗 Используем SQLite (локально)")
        return 'sqlite:///finance_bot.db'

# Создаем движок базы данных
try:
    engine = create_engine(get_database_url())
    logger.info("✅ Подключение к базе данных успешно")
except Exception as e:
    logger.error(f"❌ Ошибка подключения к базе: {e}")
    engine = create_engine('sqlite:///finance_bot.db')  # fallback

Base = declarative_base()

class Expense(Base):
    __tablename__ = 'expenses'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(String(500))
    date = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<Expense(user_id={self.user_id}, amount={self.amount}, category='{self.category}')>"

class Income(Base):
    __tablename__ = 'incomes'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(String(500))
    date = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<Income(user_id={self.user_id}, amount={self.amount}, category='{self.category}')>"

# Создаем таблицы
def init_database():
    try:
        Base.metadata.create_all(engine)
        logger.info("✅ Таблицы базы данных созданы/проверены")
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц: {e}")

# Инициализируем базу при импорте
init_database()

Session = sessionmaker(bind=engine)

def get_session():
    """Возвращает новую сессию базы данных"""
    return Session()