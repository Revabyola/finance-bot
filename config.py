import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ Не найден BOT_TOKEN в .env файле!")

# Категории по умолчанию
EXPENSE_CATEGORIES = [
    '🍔 еда', '🚗 транспорт', '🎮 развлечения', 
    '🏠 коммуналка', '👕 одежда', '💊 здоровье',
    '📱 связь', '🎁 подарки', '✈️ путешествия',
    '📚 образование', '💼 бизнес', '❔ другое'
]

INCOME_CATEGORIES = [
    '💰 зарплата', '💼 freelance', '📈 инвестиции',
    '🎁 подарок', '🔄 возврат', '💸 прочее'
]