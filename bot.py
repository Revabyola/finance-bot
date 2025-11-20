import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
from database import Session, Expense, Income, get_session, init_database
from config import BOT_TOKEN, EXPENSE_CATEGORIES, INCOME_CATEGORIES
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WAITING_AMOUNT, WAITING_CATEGORY, WAITING_DESCRIPTION = range(3)

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("💸 Добавить расход"), KeyboardButton("💰 Добавить доход")],
        [KeyboardButton("📊 Баланс"), KeyboardButton("📋 Последние операции")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_categories_keyboard(transaction_type):
    categories = EXPENSE_CATEGORIES if transaction_type == "expense" else INCOME_CATEGORIES
    keyboard = [[KeyboardButton(cat)] for cat in categories]
    keyboard.append([KeyboardButton("↩️ Назад")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я бот для учета финансов. Вот что я умею:

💸 Добавить расход - записать трату
💰 Добавить доход - записать доход  
📊 Баланс - показать текущий баланс
📋 Последние операции - история операций

Просто нажми на кнопку внизу! 🚀
    """
    update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())
    return ConversationHandler.END

def show_balance(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        session = get_session()
        expenses = session.query(Expense).filter(Expense.user_id == user_id).all()
        incomes = session.query(Income).filter(Income.user_id == user_id).all()
        total_income = sum(inc.amount for inc in incomes)
        total_expenses = sum(exp.amount for exp in expenses)
        balance = total_income - total_expenses
        session.close()
        
        update.message.reply_text(
            f"📊 Ваш баланс: {balance:.2f} руб.",
            reply_markup=get_main_keyboard(),
        )
    except Exception as e:
        logger.error(f"Ошибка получения баланса: {e}")
        update.message.reply_text("❌ Ошибка получения баланса")

def show_recent_transactions(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        session = get_session()
        expenses = session.query(Expense).filter(Expense.user_id == user_id).order_by(Expense.date.desc()).limit(5).all()
        incomes = session.query(Income).filter(Income.user_id == user_id).order_by(Income.date.desc()).limit(5).all()
        session.close()
        
        transactions = []
        for exp in expenses:
            transactions.append({'type': 'expense', 'amount': exp.amount, 'category': exp.category, 'description': exp.description, 'date': exp.date})
        for inc in incomes:
            transactions.append({'type': 'income', 'amount': inc.amount, 'category': inc.category, 'description': inc.description, 'date': inc.date})
        
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        if not transactions:
            update.message.reply_text("📝 У вас еще нет операций")
            return

        text = "📋 Последние операции:\n\n"
        for t in transactions:
            emoji = "💸" if t['type'] == 'expense' else "💰"
            sign = "-" if t['type'] == 'expense' else "+"
            text += f"{emoji} {sign}{abs(t['amount']):.2f} руб. - {t['category']}\n"
            if t['description']:
                text += f"   📝 {t['description']}\n"
            text += f"   ⏰ {t['date'].strftime('%d.%m %H:%M')}\n\n"

        update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Ошибка получения операций: {e}")
        update.message.reply_text("❌ Ошибка загрузки операций")

def add_expense(update: Update, context: CallbackContext):
    context.user_data['transaction_type'] = 'expense'
    update.message.reply_text(
        "💸 Введите сумму расхода:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("↩️ Назад")]], resize_keyboard=True),
    )
    return WAITING_AMOUNT

def add_income(update: Update, context: CallbackContext):
    context.user_data['transaction_type'] = 'income'
    update.message.reply_text(
        "💰 Введите сумму дохода:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("↩️ Назад")]], resize_keyboard=True),
    )
    return WAITING_AMOUNT

def handle_amount(update: Update, context: CallbackContext):
    text = update.message.text
    
    if text == "↩️ Назад":
        update.message.reply_text("↩️ Возврат в главное меню", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        amount = float(text.replace(",", "."))
        if amount <= 0:
            update.message.reply_text("❌ Сумма должна быть больше 0")
            return WAITING_AMOUNT

        context.user_data['amount'] = amount
        transaction_type = context.user_data['transaction_type']
        
        update.message.reply_text(
            "📁 Выберите категорию:",
            reply_markup=get_categories_keyboard(transaction_type),
        )
        return WAITING_CATEGORY
    except ValueError:
        update.message.reply_text("❌ Введите корректную сумму (например: 1500 или 99.90)")
        return WAITING_AMOUNT

def handle_category(update: Update, context: CallbackContext):
    text = update.message.text
    
    if text == "↩️ Назад":
        update.message.reply_text("↩️ Возврат в главное меню", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    transaction_type = context.user_data.get('transaction_type', 'expense')
    categories = EXPENSE_CATEGORIES if transaction_type == "expense" else INCOME_CATEGORIES
    
    if text in categories:
        context.user_data['category'] = text
        update.message.reply_text(
            "📝 Введите описание (или нажмите 'Пропустить'):",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Пропустить")], [KeyboardButton("↩️ Назад")]], resize_keyboard=True,
            ),
        )
        return WAITING_DESCRIPTION
    else:
        update.message.reply_text("❌ Выберите категорию из списка")
        return WAITING_CATEGORY

def handle_description(update: Update, context: CallbackContext):
    text = update.message.text
    
    if text == "↩️ Назад":
        transaction_type = context.user_data.get('transaction_type', 'expense')
        update.message.reply_text(
            "📁 Выберите категорию:",
            reply_markup=get_categories_keyboard(transaction_type),
        )
        return WAITING_CATEGORY
    
    description = text if text != "Пропустить" else ""
    user_id = update.effective_user.id
    amount = context.user_data['amount']
    category = context.user_data['category']
    transaction_type = context.user_data['transaction_type']

    try:
        session = get_session()
        if transaction_type == "expense":
            transaction = Expense(
                user_id=user_id,
                amount=amount,
                category=category,
                description=description,
                date=datetime.now()
            )
        else:
            transaction = Income(
                user_id=user_id,
                amount=amount,
                category=category,
                description=description,
                date=datetime.now()
            )
        
        session.add(transaction)
        session.commit()
        session.close()

        emoji = "💸" if transaction_type == "expense" else "💰"
        sign = "-" if transaction_type == "expense" else "+"
        update.message.reply_text(
            f"✅ {emoji} Транзакция добавлена!\n"
            f"Сумма: {sign}{amount:.2f} руб.\n"
            f"Категория: {category}\n"
            f"Описание: {description if description else 'нет'}",
            reply_markup=get_main_keyboard(),
        )

    except Exception as e:
        logger.error(f"Ошибка сохранения транзакции: {e}")
        update.message.reply_text("❌ Ошибка при сохранении транзакции", reply_markup=get_main_keyboard())

    context.user_data.clear()
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    context.user_data.clear()
    update.message.reply_text("↩️ Возврат в главное меню", reply_markup=get_main_keyboard())
    return ConversationHandler.END

def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден!")
        return

    init_database()

    updater = Updater(BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex("^💸 Добавить расход$"), add_expense),
            MessageHandler(Filters.regex("^💰 Добавить доход$"), add_income),
        ],
        states={
            WAITING_AMOUNT: [MessageHandler(Filters.text & ~Filters.command, handle_amount)],
            WAITING_CATEGORY: [MessageHandler(Filters.text & ~Filters.command, handle_category)],
            WAITING_DESCRIPTION: [MessageHandler(Filters.text & ~Filters.command, handle_description)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(Filters.regex("^↩️ Назад$"), cancel)],
    )

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(MessageHandler(Filters.regex("^📊 Баланс$"), show_balance))
    dispatcher.add_handler(MessageHandler(Filters.regex("^📋 Последние операции$"), show_recent_transactions))
    dispatcher.add_handler(MessageHandler(Filters.regex("^↩️ Назад$"), cancel))

    logger.info("🤖 Бот запущен...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()