import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)
    transaction_type = Column(String(10), nullable=False)  # 'income' или 'expense'
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<Transaction(user_id={self.user_id}, amount={self.amount}, type={self.transaction_type})>"

class Database:
    def __init__(self, db_url=None):
        # Используем DATABASE_URL от Heroku или локальную SQLite
        if db_url is None:
            db_url = os.getenv('DATABASE_URL', 'sqlite:///finance.db')
        
        # Конвертируем postgres:// в postgresql:// для SQLAlchemy
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
            
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        logger.info(f"✅ База данных инициализирована: {db_url}")
    
    def add_transaction(self, user_id, amount, category, transaction_type, description=""):
        try:
            # Для расходов сохраняем отрицательную сумму, для доходов - положительную
            final_amount = -abs(amount) if transaction_type == 'expense' else abs(amount)
            
            transaction = Transaction(
                user_id=user_id,
                amount=final_amount,
                category=category,
                transaction_type=transaction_type,
                description=description
            )
            self.session.add(transaction)
            self.session.commit()
            logger.info(f"✅ Добавлена транзакция для user_id={user_id}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"❌ Ошибка добавления транзакции: {e}")
            return False
    
    def get_transaction_by_id(self, transaction_id, user_id):
        """Находит транзакцию по ID и user_id"""
        try:
            return self.session.query(Transaction).filter_by(id=transaction_id, user_id=user_id).first()
        except Exception as e:
            logger.error(f"❌ Ошибка поиска транзакции: {e}")
            return None

    def update_transaction(self, transaction_id, user_id, amount=None, category=None, description=None):
        """Обновляет транзакцию"""
        try:
            transaction = self.get_transaction_by_id(transaction_id, user_id)
            if not transaction:
                return False
            
            if amount is not None:
                # Сохраняем знак в зависимости от типа транзакции
                if transaction.transaction_type == 'expense':
                    transaction.amount = -abs(amount)
                else:
                    transaction.amount = abs(amount)
            if category is not None:
                transaction.category = category
            if description is not None:
                transaction.description = description
                
            self.session.commit()
            logger.info(f"✅ Обновлена транзакция {transaction_id} для user_id={user_id}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"❌ Ошибка обновления транзакции: {e}")
            return False

    def get_user_balance(self, user_id):
        try:
            transactions = self.session.query(Transaction).filter_by(user_id=user_id).all()
            balance = sum(t.amount for t in transactions)
            return balance
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса: {e}")
            return 0
    
    def get_user_transactions(self, user_id, limit=10):
        try:
            return self.session.query(Transaction).filter_by(user_id=user_id).order_by(Transaction.created_at.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"❌ Ошибка получения транзакций: {e}")
            return []
        
    def delete_user_transactions(self, user_id):
        """Удаляет все транзакции пользователя"""
        try:
            # Находим все транзакции пользователя
            transactions = self.session.query(Transaction).filter_by(user_id=user_id).all()
            
            # Удаляем каждую транзакцию
            for transaction in transactions:
                self.session.delete(transaction)
            
            # Сохраняем изменения
            self.session.commit()
            logger.info(f"✅ Сброшены данные для user_id={user_id}")
            return True
        except Exception as e:
            # Если ошибка - откатываем изменения
            self.session.rollback()
            logger.error(f"❌ Ошибка сброса данных: {e}")
            return False

# Создаем глобальный экземпляр базы данных
db = Database()