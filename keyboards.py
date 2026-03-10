from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

def main_menu_keyboard():
    """Главное меню бота с инлайн кнопками"""
    keyboard = [
        [InlineKeyboardButton("💳 Мой профиль", callback_data="profile"), 
         InlineKeyboardButton("🎁 Мои баллы", callback_data="my_points")],
        [InlineKeyboardButton("📱 QR код", callback_data="generate_qr"), 
         InlineKeyboardButton("📊 Статистика", callback_data="statistics")],
        [InlineKeyboardButton("🎯 Акции", callback_data="promotions"), 
         InlineKeyboardButton("👥 Реферальная программа", callback_data="referral_program")],
        [InlineKeyboardButton("🎉 Розыгрыш", callback_data="giveaway")],
        [InlineKeyboardButton("📞 Поддержка", callback_data="support"), 
         InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Алиас для совместимости
main_keyboard = main_menu_keyboard

def profile_keyboard():
    """Клавиатура для профиля пользователя"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu")]
    ])

def points_keyboard():
    """Клавиатура для работы с баллами"""
    keyboard = [
        [InlineKeyboardButton("📈 История баллов", callback_data="points_history")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def referral_keyboard(share_url=None):
    """Клавиатура реферальной программы - только показ кода и поделиться"""
    keyboard = []
    
    # Если передана ссылка для шеринга, используем switch_inline_query
    if share_url:
        keyboard.append([InlineKeyboardButton("📤 Поделиться ссылкой", switch_inline_query=share_url)])
    else:
        keyboard.append([InlineKeyboardButton("📤 Поделиться ссылкой", callback_data="share_referral")])
    
    keyboard.extend([
        [InlineKeyboardButton("👥 Мои рефералы", callback_data="my_referrals")],
        [InlineKeyboardButton("🏆 Топ рефералов", callback_data="referral_top")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu")]
    ])
    return InlineKeyboardMarkup(keyboard)

def admin_keyboard():
    """Административная клавиатура"""
    keyboard = [
        [InlineKeyboardButton("📊 Статистика пользователей", callback_data="admin_stats")],
        [InlineKeyboardButton("📈 Графики статистики", callback_data="admin_charts_menu")],
        [InlineKeyboardButton("🎯 Создать акцию", callback_data="admin_create_promotion")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🎉 Розыгрыш", callback_data="admin_giveaway_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def giveaway_keyboard(giveaway_id: int, is_participant: bool = False):
    keyboard = []
    if not is_participant:
        keyboard.append([InlineKeyboardButton("✅ Участвую", callback_data=f"giveaway_join_{giveaway_id}")])
    else:
        keyboard.append([InlineKeyboardButton("✅ Вы участвуете", callback_data=f"giveaway_status_{giveaway_id}")])
    keyboard.append([InlineKeyboardButton("🏆 Топ розыгрыша", callback_data=f"giveaway_top_{giveaway_id}")])
    keyboard.append([InlineKeyboardButton("📍 Моя позиция", callback_data=f"giveaway_mypos_{giveaway_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)


def giveaway_admin_keyboard(giveaway_id: int):
    keyboard = [
        [InlineKeyboardButton("📢 Разослать кнопку «Участвую»", callback_data=f"admin_giveaway_broadcast_{giveaway_id}")],
        [InlineKeyboardButton("🏆 Топ розыгрыша", callback_data=f"admin_giveaway_top_{giveaway_id}")],
        [InlineKeyboardButton("⛔ Завершить розыгрыш", callback_data=f"admin_giveaway_stop_{giveaway_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_charts_keyboard():
    """Клавиатура для выбора типа графика"""
    keyboard = [
        [InlineKeyboardButton("📊 Общая статистика по месяцам", callback_data="chart_monthly_stats")],
        [InlineKeyboardButton("🎁 Статистика баллов", callback_data="chart_points")],
        [InlineKeyboardButton("🔙 Назад к админ-панели", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(keyboard)

def cancel_keyboard():
    """Клавиатура отмены"""
    keyboard = [
        [InlineKeyboardButton("❌ Отменить", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def yes_no_keyboard():
    """Клавиатура да/нет"""
    keyboard = [
        [InlineKeyboardButton("✅ Да", callback_data="yes"),
         InlineKeyboardButton("❌ Нет", callback_data="no")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_keyboard():
    """Простая кнопка назад в главное меню"""
    keyboard = [
        [InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_to_admin_keyboard():
    """Кнопка назад в админ-панель"""
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(keyboard)

def share_contact_keyboard():
    """Клавиатура для отправки контакта"""
    keyboard = [
        [KeyboardButton("📞 Поделиться контактом", request_contact=True)],
        [KeyboardButton("❌ Пропустить")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def promotions_keyboard(promotions):
    """Клавиатура с активными акциями"""
    keyboard = []
    for promo in promotions:
        keyboard.append([InlineKeyboardButton(
            f"🎯 {promo.title}", 
            callback_data=f"promo_{promo.id}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard) 

def request_phone_keyboard():
    """Клавиатура для запроса номера телефона при регистрации"""
    keyboard = [
        [KeyboardButton("📱 Поделиться номером телефона", request_contact=True)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def referral_input_keyboard():
    """Клавиатура для ввода реферального кода при регистрации"""
    keyboard = [
        [KeyboardButton("⏭️ Пропустить")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True) 