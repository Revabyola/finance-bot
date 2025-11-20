import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_url():
    if 'DATABASE_URL' in os.environ:
        db_url = os.environ['DATABASE_URL']
        # Явно указываем asyncpg драйвер
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql+asyncpg://', 1)
        return db_url
    else:
        return 'sqlite:///finance_bot.db'



engine = create_engine(get_database_url())
Base = declarative_base()

class Expense(Base):
    __tablename__ = 'expenses'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(String(500))
    date = Column(DateTime, default=datetime.now)

class Income(Base):
    __tablename__ = 'incomes'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(String(500))
    date = Column(DateTime, default=datetime.now)

def init_database():
    try:
        # ПЕРЕСОЗДАЕМ таблицы с user_id
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        logger.info("✅ Таблицы ПЕРЕСОЗДАНЫ с полем user_id")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")



Session = sessionmaker(bind=engine)

def get_session():
    return Session()