import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from database import Session, Expense, Income, get_session
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


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        
        await update.message.reply_text(
            f"📊 *Ваш баланс:* {balance:.2f} руб.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(),
        )
    except Exception as e:
        logger.error(f"Ошибка получения баланса: {e}")
        await update.message.reply_text("❌ Ошибка получения баланса")


async def show_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

        await update.message.reply_text(chart_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка построения диаграммы: {e}")
        await update.message.reply_text("❌ Ошибка построения диаграммы")


async def reset_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс всех данных пользователя"""
    keyboard = [
        [KeyboardButton("✅ Да, сбросить все")],
        [KeyboardButton("❌ Нет, отмена")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "⚠️ *ВНИМАНИЕ!* Вы собираетесь удалить ВСЕ ваши финансовые данные.\n\n"
        "❌ Удалятся все доходы и расходы\n"
        "❌ Сбросится баланс к нулю\n"
        "❌ Это действие нельзя отменить!\n\n"
        "Вы уверены что хотите сбросить все данные?",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

    return CONFIRM_RESET


async def handle_reset_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            
            await update.message.reply_text(
                "✅ Все данные сброшены! Баланс обнулен. 🎯",
                reply_markup=get_main_keyboard(),
            )
        except Exception as e:
            logger.error(f"Ошибка сброса данных: {e}")
            await update.message.reply_text(
                f"❌ Ошибка при сбросе данных", reply_markup=get_main_keyboard()
            )
    
    elif text == "❌ Нет, отмена":
        await update.message.reply_text(
            "✅ Сброс данных отменен", reply_markup=get_main_keyboard()
        )
    
    return ConversationHandler.END


async def edit_operation_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            await update.message.reply_text("📝 У вас еще нет операций для редактирования")
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
        
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        context.user_data['transactions'] = transactions
        return SELECT_OPERATION
        
    except Exception as e:
        logger.error(f"Ошибка получения операций: {e}")
        await update.message.reply_text("❌ Ошибка загрузки операций")
        return ConversationHandler.END


async def show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, transaction_id):
    """Показывает меню редактирования операции"""
    transactions = context.user_data.get('transactions', [])
    transaction = next((t for t in transactions if t['id'] == transaction_id), None)
    
    if not transaction:
        await update.message.reply_text("❌ Операция не найдена", reply_markup=get_main_keyboard())
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
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    context.user_data['transaction_id'] = transaction_id
    context.user_data['transaction_type'] = transaction['type']
    return EDIT_MENU


async def handle_operation_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора операции для редактирования"""
    text = update.message.text
    
    if text == "↩️ Назад":
        await update.message.reply_text("↩️ Возврат в главное меню", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        transaction_id = int(text.split(':')[0].strip())
        return await show_edit_menu(update, context, transaction_id)
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Неверный формат операции", reply_markup=get_main_keyboard())
        return SELECT_OPERATION


async def handle_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка меню редактирования"""
    text = update.message.text
    transaction_id = context.user_data.get('transaction_id')
    transaction_type = context.user_data.get('transaction_type')
    
    if not transaction_id:
        await update.message.reply_text("❌ Ошибка: операция не найдена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if text == "↩️ Назад к списку":
        return await edit_operation_select(update, context)
    
    elif text == "💵 Изменить сумму":
        await update.message.reply_text(
            "💵 Введите новую сумму:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("↩️ Назад")]], resize_keyboard=True)
        )
        return EDITING_AMOUNT
    
    elif text == "📝 Изменить описание":
        await update.message.reply_text(
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
                await update.message.reply_text("✅ Операция удалена!", reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text("❌ Операция не найдена", reply_markup=get_main_keyboard())
            session.close()
        except Exception as e:
            logger.error(f"Ошибка удаления: {e}")
            await update.message.reply_text("❌ Ошибка при удалении", reply_markup=get_main_keyboard())
        
        context.user_data.clear()
        return ConversationHandler.END


async def handle_editing_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка изменения суммы"""
    text = update.message.text
    transaction_id = context.user_data.get('transaction_id')
    transaction_type = context.user_data.get('transaction_type')
    user_id = update.effective_user.id
    
    if text == "↩️ Назад":
        return await show_edit_menu(update, context, transaction_id)
    
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
                await update.message.reply_text("✅ Сумма обновлена!", reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text("❌ Операция не найдена", reply_markup=get_main_keyboard())
            session.close()
        except Exception as e:
            logger.error(f"Ошибка обновления суммы: {e}")
            await update.message.reply_text("❌ Ошибка обновления суммы", reply_markup=get_main_keyboard())
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Введите корректную сумму (например: 1500 или 99.90)")
        return EDITING_AMOUNT


async def handle_editing_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка изменения описания"""
    text = update.message.text
    transaction_id = context.user_data.get('transaction_id')
    transaction_type = context.user_data.get('transaction_type')
    user_id = update.effective_user.id
    
    if text == "↩️ Назад":
        return await show_edit_menu(update, context, transaction_id)
    
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
            await update.message.reply_text(f"✅ Описание {action}!", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text("❌ Операция не найдена", reply_markup=get_main_keyboard())
        session.close()
    except Exception as e:
        logger.error(f"Ошибка обновления описания: {e}")
        await update.message.reply_text("❌ Ошибка обновления описания", reply_markup=get_main_keyboard())
    
    context.user_data.clear()
    return ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await update.message.reply_text(
        welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown"
    )
    return ConversationHandler.END


async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления расхода"""
    context.user_data['transaction_type'] = 'expense'
    await update.message.reply_text(
        "💸 Введите сумму расхода:",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("↩️ Назад")]], resize_keyboard=True
        ),
    )
    return WAITING_AMOUNT


async def add_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления дохода"""
    context.user_data['transaction_type'] = 'income'
    await update.message.reply_text(
        "💰 Введите сумму дохода:",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("↩️ Назад")]], resize_keyboard=True
        ),
    )
    return WAITING_AMOUNT


async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода суммы"""
    text = update.message.text
    
    if text == "↩️ Назад":
        await update.message.reply_text("↩️ Возврат в главное меню", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        amount = float(text.replace(",", "."))
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть больше 0")
            return WAITING_AMOUNT

        context.user_data['amount'] = amount
        transaction_type = context.user_data['transaction_type']
        
        await update.message.reply_text(
            "📁 Выберите категорию:",
            reply_markup=get_categories_keyboard(transaction_type),
        )
        return WAITING_CATEGORY
    except ValueError:
        await update.message.reply_text("❌ Введите корректную сумму (например: 1500 или 99.90)")
        return WAITING_AMOUNT


async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора категории"""
    text = update.message.text
    
    if text == "↩️ Назад":
        await update.message.reply_text(
            "↩️ Возврат в главное меню", reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    
    transaction_type = context.user_data.get('transaction_type', 'expense')
    categories = EXPENSE_CATEGORIES if transaction_type == "expense" else INCOME_CATEGORIES
    
    if text in categories:
        context.user_data['category'] = text
        await update.message.reply_text(
            "📝 Введите описание (или нажмите 'Пропустить'):",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Пропустить")], [KeyboardButton("↩️ Назад")]],
                resize_keyboard=True,
            ),
        )
        return WAITING_DESCRIPTION
    else:
        await update.message.reply_text("❌ Выберите категорию из списка")
        return WAITING_CATEGORY


async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода описания"""
    text = update.message.text
    
    if text == "↩️ Назад":
        transaction_type = context.user_data.get('transaction_type', 'expense')
        await update.message.reply_text(
            "📁 Выберите категорию:",
            reply_markup=get_categories_keyboard(transaction_type),
        )
        return WAITING_CATEGORY
    
    description = text if text != "Пропустить" else ""
    user_id = update.effective_user.id
    amount = context.user_data['amount']
    category = context.user_data['category']
    transaction_type = context.user_data['transaction_type']

    # Сохраняем транзакцию (ИСПРАВЛЕННАЯ ВЕРСИЯ)
    try:
        session = get_session()
        if transaction_type == "expense":
            transaction = Expense(
                amount=amount,
                category=category,
                description=description,
                date=datetime.now()
            )
            transaction.user_id = user_id  # устанавливаем user_id отдельно
        else:
            transaction = Income(
                amount=amount,
                category=category,
                description=description,
                date=datetime.now()
            )
            transaction.user_id = user_id  # устанавливаем user_id отдельно
        
        session.add(transaction)
        session.commit()
        session.close()

        emoji = "💸" if transaction_type == "expense" else "💰"
        sign = "-" if transaction_type == "expense" else "+"
        await update.message.reply_text(
            f"✅ {emoji} Транзакция добавлена!\n"
            f"Сумма: {sign}{amount:.2f} руб.\n"
            f"Категория: {category}\n"
            f"Описание: {description if description else 'нет'}",
            reply_markup=get_main_keyboard(),
        )

    except Exception as e:
        logger.error(f"Ошибка сохранения транзакции: {e}")
        await update.message.reply_text(
            "❌ Ошибка при сохранении транзакции", reply_markup=get_main_keyboard()
        )

    # Очищаем временные данные
    context.user_data.clear()
    return ConversationHandler.END


async def show_recent_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            await update.message.reply_text("📝 У вас еще нет операций")
            return

        text = "📋 *Последние операции:*\n\n"
        for t in transactions:
            emoji = "💸" if t['type'] == 'expense' else "💰"
            sign = "-" if t['type'] == 'expense' else "+"
            text += f"{emoji} {sign}{abs(t['amount']):.2f} руб. - {t['category']}\n"
            if t['description']:
                text += f"   📝 {t['description']}\n"
            text += f"   ⏰ {t['date'].strftime('%d.%m %H:%M')}\n\n"

        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка получения операций: {e}")
        await update.message.reply_text("❌ Ошибка загрузки операций")


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает справку"""
    await update.message.reply_text(
        "🆘 *Помощь по боту:*\n\n"
        "• Используйте кнопки для навигации\n"
        "• Для добавления операции выберите тип и следуйте инструкциям\n"
        "• Баланс рассчитывается автоматически\n"
        "• Все данные хранятся только для вас\n\n"
        "Начните с кнопки 'Добавить расход' или 'Добавить доход'!",
        parse_mode="Markdown",
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущей операции"""
    context.user_data.clear()
    await update.message.reply_text(
        "↩️ Возврат в главное меню", reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка. Попробуйте еще раз.", reply_markup=get_main_keyboard()
        )


def main():
    """Основная функция"""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден!")
        return

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Создаем ConversationHandler для добавления транзакций
    transaction_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💸 Добавить расход$"), add_expense),
            MessageHandler(filters.Regex("^💰 Добавить доход$"), add_income),
        ],
        states={
            WAITING_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)
            ],
            WAITING_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category)
            ],
            WAITING_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^↩️ Назад$"), cancel),
        ],
        allow_reentry=True
    )

    # ConversationHandler для редактирования операций
    edit_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^✏️ Редактировать$"), edit_operation_select),
        ],
        states={
            SELECT_OPERATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_operation_selection)
            ],
            EDIT_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_menu)
            ],
            EDITING_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_editing_amount)
            ],
            EDITING_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_editing_description)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^↩️ Назад$"), cancel),
        ],
        allow_reentry=True
    )

    # ConversationHandler для сброса данных
    reset_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔄 Сброс данных$"), reset_data),
        ],
        states={
            CONFIRM_RESET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reset_confirmation)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
        allow_reentry=True
    )

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(transaction_conv_handler)
    application.add_handler(edit_conv_handler)
    application.add_handler(reset_conv_handler)
    
    # Обработчики для простых команд
    application.add_handler(MessageHandler(filters.Regex("^📊 Баланс$"), show_balance))
    application.add_handler(MessageHandler(filters.Regex("^📈 Диаграмма$"), show_chart))
    application.add_handler(MessageHandler(filters.Regex("^📋 Последние операции$"), show_recent_transactions))
    application.add_handler(MessageHandler(filters.Regex("^🆘 Помощь$"), show_help))
    application.add_handler(MessageHandler(filters.Regex("^↩️ Назад$"), cancel))
    
    application.add_error_handler(error_handler)

    # Запускаем бота
    logger.info("🤖 Бот запущен...")
    application.run_polling()


if __name__ == "__main__":
    main()