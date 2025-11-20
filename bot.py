import os
import logging
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, 
                         ConversationHandler, CallbackContext)
from database import Session, Expense, Income, get_session, init_database
from config import BOT_TOKEN, EXPENSE_CATEGORIES, INCOME_CATEGORIES
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Определяем состояния для ConversationHandler
(
    WAITING_AMOUNT,
    WAITING_CATEGORY, 
    WAITING_DESCRIPTION,
    CONFIRM_RESET,
    SELECT_OPERATION,
    EDIT_MENU,
    EDITING_AMOUNT,
    EDITING_DESCRIPTION
) = range(8)

# Flask сервер для Railway
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Finance Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def get_main_keyboard():
    """Клавиатура основного меню"""
    keyboard = [
        [KeyboardButton("💸 Добавить расход"), KeyboardButton("💰 Добавить доход")],
        [KeyboardButton("📊 Баланс"), KeyboardButton("📈 Диаграмма")],
        [KeyboardButton("📋 Последние операции"), KeyboardButton("✏️ Редактировать")],
        [KeyboardButton("🔄 Сброс данных"), KeyboardButton("🆘 Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_categories_keyboard(transaction_type):
    """Клавиатура с категориями"""
    categories = (
        EXPENSE_CATEGORIES if transaction_type == "expense" else INCOME_CATEGORIES
    )
    keyboard = [[KeyboardButton(cat)] for cat in categories]
    keyboard.append([KeyboardButton("↩️ Назад")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def show_balance(update: Update, context: CallbackContext):
    """Показывает баланс пользователя"""
    user_id = update.effective_user.id
    try:
        session = get_session()
        
        # Рассчитываем баланс из базы
        expenses = session.query(Expense).filter(Expense.user_id == user_id).all()
        incomes = session.query(Income).filter(Income.user_id == user_id).all()
        
        total_income = sum(inc.amount for inc in incomes)
        total_expenses = sum(exp.amount for exp in expenses)
        balance = total_income - total_expenses
        
        session.close()
        
        update.message.reply_text(
            f"📊 *Ваш баланс:* {balance:.2f} руб.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(),
        )
    except Exception as e:
        logger.error(f"Ошибка получения баланса: {e}")
        update.message.reply_text("❌ Ошибка получения баланса")

def show_chart(update: Update, context: CallbackContext):
    """Показывает текстовую диаграмму баланса"""
    user_id = update.effective_user.id
    try:
        session = get_session()
        
        # Получаем доходы и расходы
        incomes = session.query(Income).filter(Income.user_id == user_id).all()
        expenses = session.query(Expense).filter(Expense.user_id == user_id).all()
        session.close()

        total_income = sum(inc.amount for inc in incomes)
        total_expenses = sum(exp.amount for exp in expenses)
        balance = total_income - total_expenses

        if total_income + total_expenses > 0:
            income_percent = int((total_income / (total_income + total_expenses)) * 100)
            expense_percent = 100 - income_percent
        else:
            income_percent = expense_percent = 0

        income_bar = "█" * (income_percent // 5)
        expense_bar = "█" * (expense_percent // 5)

        chart_text = f"""
📊 *Визуализация финансов:*

💰 Доходы: {total_income:,.2f} руб.
{income_bar} {income_percent}%

💸 Расходы: {total_expenses:,.2f} руб.
{expense_bar} {expense_percent}%

⚖️ *Баланс: {balance:,.2f} руб.*
        """

        update.message.reply_text(chart_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка построения диаграммы: {e}")
        update.message.reply_text("❌ Ошибка построения диаграммы")

def reset_data(update: Update, context: CallbackContext):
    """Сброс всех данных пользователя"""
    keyboard = [
        [KeyboardButton("✅ Да, сбросить все")],
        [KeyboardButton("❌ Нет, отмена")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    update.message.reply_text(
        "⚠️ *ВНИМАНИЕ!* Вы собираетесь удалить ВСЕ ваши финансовые данные.\n\n"
        "❌ Удалятся все доходы и расходы\n"
        "❌ Сбросится баланс к нулю\n"
        "❌ Это действие нельзя отменить!\n\n"
        "Вы уверены что хотите сбросить все данные?",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

    return CONFIRM_RESET

def handle_reset_confirmation(update: Update, context: CallbackContext):
    """Обработка подтверждения сброса данных"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "✅ Да, сбросить все":
        try:
            session = get_session()
            # Удаляем все записи пользователя
            session.query(Expense).filter(Expense.user_id == user_id).delete()
            session.query(Income).filter(Income.user_id == user_id).delete()
            session.commit()
            session.close()
            
            update.message.reply_text(
                "✅ Все данные сброшены! Баланс обнулен. 🎯",
                reply_markup=get_main_keyboard(),
            )
        except Exception as e:
            logger.error(f"Ошибка сброса данных: {e}")
            update.message.reply_text(
                f"❌ Ошибка при сбросе данных", reply_markup=get_main_keyboard()
            )
    
    elif text == "❌ Нет, отмена":
        update.message.reply_text(
            "✅ Сброс данных отменен", reply_markup=get_main_keyboard()
        )
    
    return ConversationHandler.END

def edit_operation_select(update: Update, context: CallbackContext):
    """Позволяет выбрать операцию для редактирования"""
    user_id = update.effective_user.id
    try:
        session = get_session()
        # Получаем последние операции (доходы и расходы)
        expenses = session.query(Expense).filter(Expense.user_id == user_id).order_by(Expense.date.desc()).limit(3).all()
        incomes = session.query(Income).filter(Income.user_id == user_id).order_by(Income.date.desc()).limit(3).all()
        session.close()
        
        transactions = []
        for exp in expenses:
            transactions.append({'id': exp.id, 'type': 'expense', 'amount': exp.amount, 
                               'category': exp.category, 'description': exp.description, 'date': exp.date})
        for inc in incomes:
            transactions.append({'id': inc.id, 'type': 'income', 'amount': inc.amount,
                               'category': inc.category, 'description': inc.description, 'date': inc.date})
        
        # Сортируем по дате
        transactions.sort(key=lambda x: x['date'], reverse=True)
        transactions = transactions[:5]
        
        if not transactions:
            update.message.reply_text("📝 У вас еще нет операций для редактирования")
            return ConversationHandler.END
        
        # Создаем клавиатуру с операциями
        keyboard = []
        for t in transactions:
            emoji = "💸" if t['type'] == 'expense' else "💰"
            sign = "-" if t['type'] == 'expense' else "+"
            button_text = f"{t['id']}: {sign}{abs(t['amount']):.2f} - {t['category']}"
            keyboard.append([KeyboardButton(button_text)])
        
        keyboard.append([KeyboardButton("↩️ Назад")])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        text = "📝 *Выберите операцию для редактирования:*\n\n"
        for t in transactions:
            emoji = "💸" if t['type'] == 'expense' else "💰"
            sign = "-" if t['type'] == 'expense' else "+"
            text += f"{emoji} *{t['id']}*: {sign}{abs(t['amount']):.2f} руб. - {t['category']}\n"
        
        update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        context.user_data['transactions'] = transactions
        return SELECT_OPERATION
        
    except Exception as e:
        logger.error(f"Ошибка получения операций: {e}")
        update.message.reply_text("❌ Ошибка загрузки операций")
        return ConversationHandler.END

def show_edit_menu(update: Update, context: CallbackContext, transaction_id):
    """Показывает меню редактирования операции"""
    transactions = context.user_data.get('transactions', [])
    transaction = next((t for t in transactions if t['id'] == transaction_id), None)
    
    if not transaction:
        update.message.reply_text("❌ Операция не найдена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    emoji = "💸" if transaction['type'] == 'expense' else "💰"
    sign = "-" if transaction['type'] == 'expense' else "+"
    
    keyboard = [
        [KeyboardButton("💵 Изменить сумму")],
        [KeyboardButton("📝 Изменить описание")],
        [KeyboardButton("🗑️ Удалить операцию")],
        [KeyboardButton("↩️ Назад к списку")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    text = f"✏️ *Редактирование операции:*\n\n"
    text += f"{emoji} *ID {transaction['id']}*: {sign}{abs(transaction['amount']):.2f} руб.\n"
    text += f"📁 Категория: {transaction['category']}\n"
    text += f"📝 Описание: {transaction['description'] if transaction['description'] else 'нет'}\n"
    text += f"⏰ Дата: {transaction['date'].strftime('%d.%m.%Y %H:%M')}\n\n"
    text += "Выберите действие:"
    
    update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    context.user_data['transaction_id'] = transaction_id
    context.user_data['transaction_type'] = transaction['type']
    return EDIT_MENU

def handle_operation_selection(update: Update, context: CallbackContext):
    """Обработка выбора операции для редактирования"""
    text = update.message.text
    
    if text == "↩️ Назад":
        update.message.reply_text("↩️ Возврат в главное меню", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        transaction_id = int(text.split(':')[0].strip())
        return show_edit_menu(update, context, transaction_id)
    except (ValueError, IndexError):
        update.message.reply_text("❌ Неверный формат операции", reply_markup=get_main_keyboard())
        return SELECT_OPERATION

def handle_edit_menu(update: Update, context: CallbackContext):
    """Обработка меню редактирования"""
    text = update.message.text
    transaction_id = context.user_data.get('transaction_id')
    transaction_type = context.user_data.get('transaction_type')
    
    if not transaction_id:
        update.message.reply_text("❌ Ошибка: операция не найдена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if text == "↩️ Назад к списку":
        return edit_operation_select(update, context)
    
    elif text == "💵 Изменить сумму":
        update.message.reply_text(
            "💵 Введите новую сумму:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("↩️ Назад")]], resize_keyboard=True)
        )
        return EDITING_AMOUNT
    
    elif text == "📝 Изменить описание":
        update.message.reply_text(
            "📝 Введите новое описание (или 'Удалить' чтобы очистить):",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Удалить"), KeyboardButton("↩️ Назад")]], resize_keyboard=True)
        )
        return EDITING_DESCRIPTION
    
    elif text == "🗑️ Удалить операцию":
        user_id = update.effective_user.id
        try:
            session = get_session()
            if transaction_type == 'expense':
                transaction = session.query(Expense).filter(Expense.id == transaction_id, Expense.user_id == user_id).first()
            else:
                transaction = session.query(Income).filter(Income.id == transaction_id, Income.user_id == user_id).first()
            
            if transaction:
                session.delete(transaction)
                session.commit()
                update.message.reply_text("✅ Операция удалена!", reply_markup=get_main_keyboard())
            else:
                update.message.reply_text("❌ Операция не найдена", reply_markup=get_main_keyboard())
            session.close()
        except Exception as e:
            logger.error(f"Ошибка удаления: {e}")
            update.message.reply_text("❌ Ошибка при удалении", reply_markup=get_main_keyboard())
        
        context.user_data.clear()
        return ConversationHandler.END

def handle_editing_amount(update: Update, context: CallbackContext):
    """Обработка изменения суммы"""
    text = update.message.text
    transaction_id = context.user_data.get('transaction_id')
    transaction_type = context.user_data.get('transaction_type')
    user_id = update.effective_user.id
    
    if text == "↩️ Назад":
        return show_edit_menu(update, context, transaction_id)
    
    try:
        new_amount = float(text.replace(',', '.'))
        
        # Обновляем сумму в базе
        try:
            session = get_session()
            if transaction_type == 'expense':
                transaction = session.query(Expense).filter(Expense.id == transaction_id, Expense.user_id == user_id).first()
            else:
                transaction = session.query(Income).filter(Income.id == transaction_id, Income.user_id == user_id).first()
            
            if transaction:
                transaction.amount = new_amount
                session.commit()
                update.message.reply_text("✅ Сумма обновлена!", reply_markup=get_main_keyboard())
            else:
                update.message.reply_text("❌ Операция не найдена", reply_markup=get_main_keyboard())
            session.close()
        except Exception as e:
            logger.error(f"Ошибка обновления суммы: {e}")
            update.message.reply_text("❌ Ошибка обновления суммы", reply_markup=get_main_keyboard())
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        update.message.reply_text("❌ Введите корректную сумму (например: 1500 или 99.90)")
        return EDITING_AMOUNT

def handle_editing_description(update: Update, context: CallbackContext):
    """Обработка изменения описания"""
    text = update.message.text
    transaction_id = context.user_data.get('transaction_id')
    transaction_type = context.user_data.get('transaction_type')
    user_id = update.effective_user.id
    
    if text == "↩️ Назад":
        return show_edit_menu(update, context, transaction_id)
    
    new_description = "" if text == "Удалить" else text
    
    # Обновляем описание в базе
    try:
        session = get_session()
        if transaction_type == 'expense':
            transaction = session.query(Expense).filter(Expense.id == transaction_id, Expense.user_id == user_id).first()
        else:
            transaction = session.query(Income).filter(Income.id == transaction_id, Income.user_id == user_id).first()
        
        if transaction:
            transaction.description = new_description
            session.commit()
            action = "удалено" if text == "Удалить" else "обновлено"
            update.message.reply_text(f"✅ Описание {action}!", reply_markup=get_main_keyboard())
        else:
            update.message.reply_text("❌ Операция не найдена", reply_markup=get_main_keyboard())
        session.close()
    except Exception as e:
        logger.error(f"Ошибка обновления описания: {e}")
        update.message.reply_text("❌ Ошибка обновления описания", reply_markup=get_main_keyboard())
    
    context.user_data.clear()
    return ConversationHandler.END

def start(update: Update, context: CallbackContext):
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я бот для учета финансов. Вот что я умею:

💸 *Добавить расход* - записать трату
💰 *Добавить доход* - записать доход  
📊 *Баланс* - показать текущий баланс
📋 *Последние операции* - история операций

Просто нажми на кнопку внизу! 🚀
    """
    update.message.reply_text(
        welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown"
    )
    return ConversationHandler.END

def add_expense(update: Update, context: CallbackContext):
    """Начало добавления расхода"""
    context.user_data['transaction_type'] = 'expense'
    update.message.reply_text(
        "💸 Введите сумму расхода:",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("↩️ Назад")]], resize_keyboard=True
        ),
    )
    return WAITING_AMOUNT

def add_income(update: Update, context: CallbackContext):
    """Начало добавления дохода"""
    context.user_data['transaction_type'] = 'income'
    update.message.reply_text(
        "💰 Введите сумму дохода:",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("↩️ Назад")]], resize_keyboard=True
        ),
    )
    return WAITING_AMOUNT

def handle_amount(update: Update, context: CallbackContext):
    """Обработка ввода суммы"""
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
    """Обработка выбора категории"""
    text = update.message.text
    
    if text == "↩️ Назад":
        update.message.reply_text(
            "↩️ Возврат в главное меню", reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    
    transaction_type = context.user_data.get('transaction_type', 'expense')
    categories = EXPENSE_CATEGORIES if transaction_type == "expense" else INCOME_CATEGORIES
    
    if text in categories:
        context.user_data['category'] = text
        update.message.reply_text(
            "📝 Введите описание (или нажмите 'Пропустить'):",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Пропустить")], [KeyboardButton("↩️ Назад")]],
                resize_keyboard=True,
            ),
        )
        return WAITING_DESCRIPTION
    else:
        update.message.reply_text("❌ Выберите категорию из списка")
        return WAITING_CATEGORY

def handle_description(update: Update, context: CallbackContext):
    """Обработка ввода описания"""
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

    # Сохраняем транзакцию
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
        update.message.reply_text(
            "❌ Ошибка при сохранении транзакции", reply_markup=get_main_keyboard()
        )

    # Очищаем временные данные
    context.user_data.clear()
    return ConversationHandler.END

def show_recent_transactions(update: Update, context: CallbackContext):
    """Показывает последние операции"""
    user_id = update.effective_user.id
    try:
        session = get_session()
        # Получаем последние операции
        expenses = session.query(Expense).filter(Expense.user_id == user_id).order_by(Expense.date.desc()).limit(3).all()
        incomes = session.query(Income).filter(Income.user_id == user_id).order_by(Income.date.desc()).limit(3).all()
        session.close()
        
        transactions = []
        for exp in expenses:
            transactions.append({'type': 'expense', 'amount': exp.amount, 'category': exp.category, 
                               'description': exp.description, 'date': exp.date})
        for inc in incomes:
            transactions.append({'type': 'income', 'amount': inc.amount, 'category': inc.category,
                               'description': inc.description, 'date': inc.date})
        
        # Сортируем по дате
        transactions.sort(key=lambda x: x['date'], reverse=True)
        transactions = transactions[:5]
        
        if not transactions:
            update.message.reply_text("📝 У вас еще нет операций")
            return

        text = "📋 *Последние операции:*\n\n"
        for t in transactions:
            emoji = "💸" if t['type'] == 'expense' else "💰"
            sign = "-" if t['type'] == 'expense' else "+"
            text += f"{emoji} {sign}{abs(t['amount']):.2f} руб. - {t['category']}\n"
            if t['description']:
                text += f"   📝 {t['description']}\n"
            text += f"   ⏰ {t['date'].strftime('%d.%m %H:%M')}\n\n"

        update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка получения операций: {e}")
        update.message.reply_text("❌ Ошибка загрузки операций")

def show_help(update: Update, context: CallbackContext):
    """Показывает справку"""
    update.message.reply_text(
        "🆘 *Помощь по боту:*\n\n"
        "• Используйте кнопки для навигации\n"
        "• Для добавления операции выберите тип и следуйте инструкциям\n"
        "• Баланс рассчитывается автоматически\n"
        "• Все данные хранятся только для вас\n\n"
        "Начните с кнопки 'Добавить расход' или 'Добавить доход'!",
        parse_mode="Markdown",
    )

def cancel(update: Update, context: CallbackContext):
    """Отмена текущей операции"""
    context.user_data.clear()
    update.message.reply_text(
        "↩️ Возврат в главное меню", reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

def error_handler(update: Update, context: CallbackContext):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")
    if update and update.effective_message:
        update.effective_message.reply_text(
            "❌ Произошла ошибка. Попробуйте еще раз.", reply_markup=get_main_keyboard()
        )

def main():
    """Основная функция"""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден!")
        return

    # Инициализируем базу данных
    init_database()

    # Создаем updater
    updater = Updater(BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Создаем ConversationHandler для добавления транзакций
    transaction_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex("^💸 Добавить расход$"), add_expense),
            MessageHandler(Filters.regex("^💰 Добавить доход$"), add_income),
        ],
        states={
            WAITING_AMOUNT: [
                MessageHandler(Filters.text & ~Filters.command, handle_amount)
            ],
            WAITING_CATEGORY: [
                MessageHandler(Filters.text & ~Filters.command, handle_category)
            ],
            WAITING_DESCRIPTION: [
                MessageHandler(Filters.text & ~Filters.command, handle_description)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(Filters.regex("^↩️ Назад$"), cancel),
        ],
        allow_reentry=True
    )

    # ConversationHandler для редактирования операций
    edit_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex("^✏️ Редактировать$"), edit_operation_select),
        ],
        states={
            SELECT_OPERATION: [
                MessageHandler(Filters.text & ~Filters.command, handle_operation_selection)
            ],
            EDIT_MENU: [
                MessageHandler(Filters.text & ~Filters.command, handle_edit_menu)
            ],
            EDITING_AMOUNT: [
                MessageHandler(Filters.text & ~Filters.command, handle_editing_amount)
            ],
            EDITING_DESCRIPTION: [
                MessageHandler(Filters.text & ~Filters.command, handle_editing_description)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(Filters.regex("^↩️ Назад$"), cancel),
        ],
        allow_reentry=True
    )

    # ConversationHandler для сброса данных
    reset_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex("^🔄 Сброс данных$"), reset_data),
        ],
        states={
            CONFIRM_RESET: [
                MessageHandler(Filters.text & ~Filters.command, handle_reset_confirmation)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
        allow_reentry=True
    )

    # Добавляем обработчики
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(transaction_conv_handler)
    dispatcher.add_handler(edit_conv_handler)
    dispatcher.add_handler(reset_conv_handler)
    
    # Обработчики для простых команд
    dispatcher.add_handler(MessageHandler(Filters.regex("^📊 Баланс$"), show_balance))
    dispatcher.add_handler(MessageHandler(Filters.regex("^📈 Диаграмма$"), show_chart))
    dispatcher.add_handler(MessageHandler(Filters.regex("^📋 Последние операции$"), show_recent_transactions))
    dispatcher.add_handler(MessageHandler(Filters.regex("^🆘 Помощь$"), show_help))
    dispatcher.add_handler(MessageHandler(Filters.regex("^↩️ Назад$"), cancel))
    
    dispatcher.add_error_handler(error_handler)

    logger.info("🤖 Бот запущен...")
    
    # Запускаем веб-сервер в отдельном потоке для Railway
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    logger.info("🌐 Веб-сервер запущен для Railway")
    
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()