import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле")

# Категории расходов и доходов
EXPENSE_CATEGORIES = ["Еда", "Транспорт", "Развлечения", "Жилье", "Здоровье", "Другое"]
INCOME_CATEGORIES = ["Зарплата", "Премия", "Инвестиции", "Подарок", "Другое"]