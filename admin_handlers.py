import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import get_db
from services import UserService, LoyaltyService, PromotionService
from keyboards import admin_keyboard, cancel_keyboard, back_keyboard, back_to_admin_keyboard, admin_charts_keyboard, giveaway_admin_keyboard
import config
from datetime import datetime, timedelta
from charts import generate_monthly_stats_chart, generate_points_chart
from handlers import start

logger = logging.getLogger(__name__)

def save_config_to_file(setting_name, new_value):
    """Сохраняет настройку в config.py"""
    try:
        # Читаем текущий config.py
        with open('config.py', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Находим и обновляем нужную строку
        updated = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f'{setting_name} ='):
                if setting_name in ['ENABLE_NOTIFICATIONS']:
                    # Для boolean значений
                    lines[i] = f"{setting_name} = {new_value}  # Обновлено через админ-панель\n"
                else:
                    # Для числовых значений
                    lines[i] = f"{setting_name} = {new_value}  # Обновлено через админ-панель\n"
                updated = True
                break
        
        if updated:
            # Записываем обновленный файл
            with open('config.py', 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            # Обновляем значение в памяти
            setattr(config, setting_name, new_value)
            
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка при сохранении настройки {setting_name}: {e}")
        return False

# Состояния для административных диалогов
(ADMIN_PROMO_TITLE, ADMIN_PROMO_DESCRIPTION, ADMIN_PROMO_DISCOUNT, ADMIN_PROMO_MEDIA,
 ADMIN_BROADCAST_MESSAGE, ADMIN_BROADCAST_MEDIA, ADMIN_DELETE_PROMO_CONFIRM, ADMIN_NOTIFICATION_DAYS,
 ADMIN_EDIT_INACTIVITY_DAYS, ADMIN_EDIT_WELCOME_BONUS, ADMIN_EDIT_BIRTHDAY_BONUS, 
 ADMIN_EDIT_POINTS_PER_PURCHASE, ADMIN_EDIT_BONUS_THRESHOLD, ADMIN_EDIT_BONUS_AMOUNT,
 ADMIN_EDIT_REFERRAL_BONUS, ADMIN_EDIT_NOTIFICATION_WEEKDAY, ADMIN_EDIT_NOTIFICATION_HOUR,
 ADMIN_EDIT_NOTIFICATION_MINUTE,
 ADMIN_GIVEAWAY_TITLE, ADMIN_GIVEAWAY_DAYS, ADMIN_GIVEAWAY_DESCRIPTION, ADMIN_GIVEAWAY_BROADCAST_TEXT,
 ADMIN_GIFT_AMOUNT, ADMIN_GIFT_DAYS, ADMIN_GIFT_DESCRIPTION, ADMIN_GIFT_GENDER) = range(26)

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    # Проверяем как основного админа, так и список дополнительных
    is_main_admin = user_id == config.ADMIN_USER_ID
    is_in_admin_list = user_id in config.ADMIN_IDS
    
    if config.DEBUG:
        print(f"🔍 Проверка админских прав для пользователя {user_id}:")
        print(f"   Основной админ (ADMIN_USER_ID): {config.ADMIN_USER_ID}")
        print(f"   Список админов (ADMIN_IDS): {config.ADMIN_IDS}")
        print(f"   Является основным админом: {is_main_admin}")
        print(f"   В списке админов: {is_in_admin_list}")
        print(f"   Результат: {is_main_admin or is_in_admin_list}")
    
    return is_main_admin or is_in_admin_list

def admin_notifications_keyboard():
    """Клавиатура для управления уведомлениями"""
    
    keyboard = [
        [InlineKeyboardButton("📤 Отправить уведомления сейчас", callback_data="admin_send_notifications")],
        [InlineKeyboardButton("📊 Статистика неактивных", callback_data="admin_inactive_stats")],
        [InlineKeyboardButton("⚙️ Настройки уведомлений", callback_data="admin_notification_settings")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_media_keyboard():
    """Клавиатура для выбора добавления медиа"""
    
    keyboard = [
        [InlineKeyboardButton("📷 Добавить медиа", callback_data="add_media")],
        [InlineKeyboardButton("✅ Продолжить без медиа", callback_data="skip_media")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_admin")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ панель"""
    user_id = update.effective_user.id
    
    # Добавляем отладочную информацию
    if config.DEBUG:
        print(f"🔍 Попытка доступа к админ-панели:")
        print(f"   user_id: {user_id} (тип: {type(user_id)})")
        print(f"   config.ADMIN_USER_ID: {config.ADMIN_USER_ID} (тип: {type(config.ADMIN_USER_ID)})")
        print(f"   config.ADMIN_IDS: {config.ADMIN_IDS}")
        print(f"   is_admin(user_id): {is_admin(user_id)}")
        print(f"   user_id == config.ADMIN_USER_ID: {user_id == config.ADMIN_USER_ID}")
        print(f"   user_id in config.ADMIN_IDS: {user_id in config.ADMIN_IDS}")
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Недоступно")
        # Вызываем функцию start для не-админов
        return await start(update, context)
    
    admin_text = f"""
🔧 Админ панель
👋 Добро пожаловать, администратор!

✅ Ваши права подтверждены:
• ID: {user_id}
• Статус: {'Основной админ' if user_id == config.ADMIN_USER_ID else 'Дополнительный админ'}

Выберите действие:
    """
    
    # Обновляем клавиатуру
    keyboard = [
        [InlineKeyboardButton("📊 Статистика пользователей", callback_data="admin_stats")],
        [InlineKeyboardButton("📈 Графики статистики", callback_data="admin_charts_menu")],
        [InlineKeyboardButton("🎯 Создать акцию", callback_data="admin_create_promotion")],
        [InlineKeyboardButton("🗑️ Управление акциями", callback_data="admin_manage_promotions")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🎁 Праздничные баллы", callback_data="admin_gift_menu")],
        [InlineKeyboardButton("🔔 Уведомления", callback_data="admin_notifications")],
        [InlineKeyboardButton("🎉 Розыгрыш", callback_data="admin_giveaway_menu")]
    ]
    admin_kb = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        admin_text,
        reply_markup=admin_kb
    )


async def admin_giveaway_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню розыгрыша"""
    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return

    db = get_db()
    try:
        loyalty_service = LoyaltyService(db)
        giveaway = loyalty_service.get_active_giveaway()

        if not giveaway:
            text = "🎉 Розыгрыш\n\nАктивного розыгрыша нет.\n\n💡 Создайте розыгрыш через веб-интерфейс кассира."
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        ends = giveaway.end_date.strftime('%d.%m.%Y %H:%M') if giveaway.end_date else "—"
        text = f"🎉 Активный розыгрыш: {giveaway.title}\n\n"
        if giveaway.description:
            text += f"{giveaway.description}\n\n"
        text += f"⏳ До конца: {ends}\n\n"
        text += "Управление:"
        await query.edit_message_text(text, reply_markup=giveaway_admin_keyboard(giveaway.id))

    except Exception as e:
        logger.error(f"Ошибка в admin_giveaway_menu: {e}", exc_info=True)
        await query.edit_message_text("❌ Ошибка при загрузке меню розыгрыша.", reply_markup=back_to_admin_keyboard())
    finally:
        db.close()


async def admin_giveaway_create_start_DISABLED(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return ConversationHandler.END

    await query.edit_message_text(
        "➕ Создание розыгрыша\n\nВведите название розыгрыша:",
        reply_markup=cancel_keyboard()
    )
    return ADMIN_GIVEAWAY_TITLE


async def admin_giveaway_create_title_DISABLED(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["giveaway_title"] = (update.message.text or "").strip()
    await update.message.reply_text(
        "Введите длительность розыгрыша в днях (1-365):",
        reply_markup=cancel_keyboard()
    )
    return ADMIN_GIVEAWAY_DAYS


async def admin_giveaway_create_days_DISABLED(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text)
        if days < 1 or days > 365:
            raise ValueError()
    except Exception:
        await update.message.reply_text("❌ Введите число от 1 до 365:", reply_markup=cancel_keyboard())
        return ADMIN_GIVEAWAY_DAYS

    context.user_data["giveaway_days"] = days
    await update.message.reply_text(
        "Введите описание/условия (можно коротко). Если не нужно — отправьте '-'",
        reply_markup=cancel_keyboard()
    )
    return ADMIN_GIVEAWAY_DESCRIPTION


async def admin_giveaway_create_description_DISABLED(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = (update.message.text or "").strip()
    if desc == "-":
        desc = ""
    context.user_data["giveaway_description"] = desc
    await update.message.reply_text(
        "Теперь текст рассылки пользователям (к нему будет прикреплена кнопка «Участвую»).\n"
        "Если не хотите рассылку сейчас — отправьте '-'",
        reply_markup=cancel_keyboard()
    )
    return ADMIN_GIVEAWAY_BROADCAST_TEXT


async def admin_giveaway_create_finish_DISABLED(update: Update, context: ContextTypes.DEFAULT_TYPE):
    broadcast_text = (update.message.text or "").strip()
    skip_broadcast = (broadcast_text == "-")

    db = get_db()
    try:
        loyalty_service = LoyaltyService(db)
        giveaway = loyalty_service.create_giveaway(
            title=context.user_data.get("giveaway_title", "Розыгрыш"),
            days=int(context.user_data.get("giveaway_days", 7)),
            description=context.user_data.get("giveaway_description", "")
        )

        await update.message.reply_text(
            f"✅ Розыгрыш создан и запущен!\n\n🎉 {giveaway.title}\n⏳ До: {giveaway.end_date.strftime('%d.%m.%Y %H:%M')}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎉 Управление розыгрышем", callback_data="admin_giveaway_menu")]])
        )

        # Рассылка всем активным зарегистрированным пользователям
        if not skip_broadcast:
            from database import User
            users = db.query(User).filter(User.is_active == True, User.is_registered == True).all()
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Участвую", callback_data=f"giveaway_join_{giveaway.id}")]])

            # Если пользователь не ввел текст, формируем автоматически из данных розыгрыша
            if not broadcast_text:
                broadcast_text = f"🎉 Розыгрыш: {giveaway.title}\n\n"
                if giveaway.description:
                    broadcast_text += f"{giveaway.description}\n\n"
                if giveaway.end_date:
                    broadcast_text += f"⏰ Срок проведения: до {giveaway.end_date.strftime('%d.%m.%Y %H:%M')}\n\n"
                broadcast_text += "🏆 Чтобы принять участие и побороться за приз, нажмите кнопку «✅ Участвую!» ниже.\n"
                broadcast_text += "Победитель будет определен по наибольшему количеству приглашенных друзей за период розыгрыша."

            sent = 0
            for u in users:
                try:
                    await context.bot.send_message(chat_id=u.telegram_id, text=broadcast_text, reply_markup=kb)
                    sent += 1
                except Exception:
                    continue
            await update.message.reply_text(f"📢 Рассылка отправлена: {sent} пользователям.")

    except Exception as e:
        logger.error(f"Ошибка создания розыгрыша: {e}", exc_info=True)
        await update.message.reply_text("❌ Ошибка при создании розыгрыша.")
    finally:
        db.close()
        context.user_data.pop("giveaway_title", None)
        context.user_data.pop("giveaway_days", None)
        context.user_data.pop("giveaway_description", None)

    return ConversationHandler.END


async def admin_giveaway_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return

    giveaway_id = int(query.data.split("_")[-1])

    db = get_db()
    try:
        loyalty_service = LoyaltyService(db)
        giveaway = loyalty_service.get_active_giveaway()
        if not giveaway or giveaway.id != giveaway_id:
            await query.edit_message_text("Розыгрыш не найден/не активен.", reply_markup=back_to_admin_keyboard())
            return

        from database import User
        from database import GiveawayParticipant
        users = db.query(User).filter(User.is_active == True, User.is_registered == True).all()
        participant_ids = {
            int(row[0])
            for row in db.query(GiveawayParticipant.user_id).filter(GiveawayParticipant.giveaway_id == giveaway.id).all()
        }

        # Формируем полное сообщение с названием и описанием
        text = f"🎉 Розыгрыш: {giveaway.title}\n\n"
        if giveaway.description:
            text += f"{giveaway.description}\n\n"
        if giveaway.end_date:
            text += f"⏰ Срок проведения: до {giveaway.end_date.strftime('%d.%m.%Y %H:%M')}\n\n"
        text += "🏆 Чтобы принять участие и побороться за приз, нажмите кнопку «✅ Участвую!» ниже.\n"
        text += "Победитель будет определен по наибольшему количеству приглашенных друзей за период розыгрыша."
        
        sent = 0
        for u in users:
            try:
                if u.id in participant_ids:
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Вы участвуете", callback_data=f"giveaway_status_{giveaway.id}")]])
                else:
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Участвую", callback_data=f"giveaway_join_{giveaway.id}")]])

                await context.bot.send_message(chat_id=u.telegram_id, text=text, reply_markup=kb)
                sent += 1
            except Exception:
                continue

        await query.edit_message_text(f"📢 Готово! Отправлено: {sent}", reply_markup=giveaway_admin_keyboard(giveaway.id))

    except Exception as e:
        logger.error(f"Ошибка рассылки розыгрыша: {e}", exc_info=True)
        await query.edit_message_text("❌ Ошибка при рассылке.", reply_markup=back_to_admin_keyboard())
    finally:
        db.close()


async def admin_giveaway_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return

    giveaway_id = int(query.data.split("_")[-1])
    db = get_db()
    try:
        from database import User, GiveawayParticipant, Giveaway
        loyalty_service = LoyaltyService(db)
        
        # Завершаем розыгрыш
        ok = loyalty_service.stop_giveaway(giveaway_id)
        if not ok:
            await query.edit_message_text(
                "❌ Розыгрыш не найден.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]])
            )
            return
        
        # Получаем информацию о розыгрыше
        giveaway = db.query(Giveaway).filter(Giveaway.id == giveaway_id).first()
        if not giveaway:
            await query.edit_message_text("❌ Розыгрыш не найден.", reply_markup=back_to_admin_keyboard())
            return
        
        # Определяем победителя (первый в топе)
        giveaway_top = loyalty_service.get_giveaway_top(giveaway_id, limit=1)
        winner = None
        winner_info = "Победителей нет"
        
        if giveaway_top and len(giveaway_top) > 0 and giveaway_top[0]["referrals_count"] > 0:
            winner_data = giveaway_top[0]
            winner = db.query(User).filter(User.id == winner_data["user_id"]).first()
            if winner:
                winner_name = f"{winner.first_name or ''} {winner.last_name or ''}".strip() or f"Участник #{winner.id}"
                winner_info = f"🏆 Победитель: {winner_name}\n📊 Приглашено друзей: {winner_data['referrals_count']}"
        
        # Отправляем уведомление всем админам
        from telegram_notifications import send_message_with_inline_button_sync
        
        admin_message = f"""
🎉 Розыгрыш завершён!

📋 Название: {giveaway.title}
{winner_info}

📢 Нажмите кнопку ниже, чтобы разослать сообщение всем участникам о завершении розыгрыша.
        """.strip()
        
        # Отправляем всем админам
        for admin_id in config.ADMIN_IDS:
            try:
                send_message_with_inline_button_sync(
                    telegram_id=admin_id,
                    message=admin_message,
                    button_text="📢 Разослать участникам",
                    callback_data=f"admin_giveaway_notify_participants_{giveaway_id}"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
        
        await query.edit_message_text(
            "✅ Розыгрыш завершён.\n\n📨 Уведомления с информацией о победителе отправлены всем администраторам.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]])
        )
    except Exception as e:
        logger.error(f"Ошибка завершения розыгрыша: {e}", exc_info=True)
        await query.edit_message_text("❌ Ошибка.", reply_markup=back_to_admin_keyboard())
    finally:
        db.close()


async def admin_giveaway_notify_participants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка сообщения всем участникам о завершении розыгрыша"""
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return

    giveaway_id = int(query.data.split("_")[-1])
    db = get_db()
    try:
        from database import User, GiveawayParticipant, Giveaway
        from telegram_notifications import run_notification_sync
        import threading
        
        loyalty_service = LoyaltyService(db)
        giveaway = db.query(Giveaway).filter(Giveaway.id == giveaway_id).first()
        if not giveaway:
            await query.edit_message_text("❌ Розыгрыш не найден.", reply_markup=back_to_admin_keyboard())
            return
        
        # Определяем победителя
        giveaway_top = loyalty_service.get_giveaway_top(giveaway_id, limit=1)
        winner_name = "Победитель будет определен позже"
        
        if giveaway_top and len(giveaway_top) > 0 and giveaway_top[0]["referrals_count"] > 0:
            winner_data = giveaway_top[0]
            winner = db.query(User).filter(User.id == winner_data["user_id"]).first()
            if winner:
                winner_name = f"{winner.first_name or ''} {winner.last_name or ''}".strip() or f"Участник #{winner.id}"
        
        # Получаем всех участников
        participants = db.query(GiveawayParticipant).filter(
            GiveawayParticipant.giveaway_id == giveaway_id
        ).all()
        
        if not participants:
            await query.edit_message_text(
                "❌ Участников не найдено.",
                reply_markup=back_to_admin_keyboard()
            )
            return
        
        # Формируем сообщение для участников
        participant_message = f"""
🎉 Розыгрыш "{giveaway.title}" завершён!

🏆 Победитель: {winner_name}

📞 Мы свяжемся с победителем в ближайшее время для вручения приза.

Спасибо за участие! 🎁
        """.strip()
        
        # Собираем telegram_id всех участников перед закрытием БД
        participant_telegram_ids = []
        for participant in participants:
            user = db.query(User).filter(User.id == participant.user_id).first()
            if user and user.telegram_id:
                participant_telegram_ids.append(user.telegram_id)
        
        # Отправляем сообщение всем участникам в отдельном потоке
        def send_notifications():
            sent = 0
            failed = 0
            for telegram_id in participant_telegram_ids:
                try:
                    run_notification_sync(telegram_id, participant_message)
                    sent += 1
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления участнику {telegram_id}: {e}")
                    failed += 1
            
            logger.info(f"Рассылка завершена: отправлено {sent}, ошибок {failed}")
        
        # Запускаем рассылку в отдельном потоке
        thread = threading.Thread(target=send_notifications, daemon=True)
        thread.start()
        
        await query.edit_message_text(
            f"✅ Рассылка запущена!\n\n📊 Участников: {len(participants)}\n\nСообщения отправляются в фоновом режиме.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]])
        )
        
    except Exception as e:
        logger.error(f"Ошибка рассылки участникам: {e}", exc_info=True)
        await query.edit_message_text("❌ Ошибка при рассылке.", reply_markup=back_to_admin_keyboard())
    finally:
        db.close()


async def admin_giveaway_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return

    giveaway_id = int(query.data.split("_")[-1])
    db = get_db()
    try:
        loyalty_service = LoyaltyService(db)
        top = loyalty_service.get_giveaway_top(giveaway_id, limit=10)

        text = "🏆 Топ розыгрыша (за период)\n\n"
        if not top:
            text += "Пока нет данных."
            await query.edit_message_text(text, reply_markup=giveaway_admin_keyboard(giveaway_id))
            return

        medals = ["🥇", "🥈", "🥉"]
        for idx, item in enumerate(top, 1):
            medal = medals[idx - 1] if idx <= 3 else f"{idx}."
            name = f"{item.get('first_name') or ''} {item.get('last_name') or ''}".strip() or "Пользователь"
            text += f"{medal} {name}\n   👥 {item['referrals_count']} приглашений\n\n"

        await query.edit_message_text(text, reply_markup=giveaway_admin_keyboard(giveaway_id))

    except Exception as e:
        logger.error(f"Ошибка admin_giveaway_top: {e}", exc_info=True)
        await query.edit_message_text("❌ Ошибка.", reply_markup=back_to_admin_keyboard())
    finally:
        db.close()

async def admin_notifications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления уведомлениями"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    weekday_name = weekday_names[config.NOTIFICATION_WEEKDAY]
    
    notifications_text = f"""
🔔 Управление уведомлениями

⚙️ Текущие настройки:
• Порог неактивности: {config.INACTIVITY_DAYS_THRESHOLD} дней
• Бонус за возвращение: {config.WELCOME_BACK_BONUS} баллов
• Уведомления включены: {'✅ Да' if config.ENABLE_NOTIFICATIONS else '❌ Нет'}
• Расписание: {weekday_name}, {config.NOTIFICATION_HOUR:02d}:{config.NOTIFICATION_MINUTE:02d}

Выберите действие:
    """
    
    await query.edit_message_text(
        notifications_text,
        reply_markup=admin_notifications_keyboard()
    )

async def admin_send_notifications_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ручная отправка уведомлений неактивным пользователям"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    await query.edit_message_text("📤 Поиск неактивных пользователей и отправка уведомлений...")
    
    try:
        # Импортируем функцию отправки уведомлений
        from notifications import send_manual_inactivity_check
        
        # Отправляем уведомления
        sent_count = await send_manual_inactivity_check(context.application, config.INACTIVITY_DAYS_THRESHOLD)
        
        result_text = f"""
✅ Уведомления отправлены!

📊 Результат:
• Найдено неактивных пользователей: проверено
• Отправлено уведомлений: {sent_count}
• Период неактивности: {config.INACTIVITY_DAYS_THRESHOLD} дней

⏰ Время отправки: {datetime.now().strftime('%d.%m.%Y %H:%M')}
        """
        
        await query.edit_message_text(
            result_text,
            reply_markup=admin_notifications_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при ручной отправке уведомлений: {e}")
        await query.edit_message_text(
            f"❌ Ошибка при отправке уведомлений: {str(e)}",
            reply_markup=admin_notifications_keyboard()
        )

async def admin_inactive_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика неактивных пользователей"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    db = get_db()
    
    try:
        from database import User, Purchase, PointsHistory
        from sqlalchemy import and_, func
        
        # Вычисляем пороговую дату
        threshold_date = datetime.now() - timedelta(days=config.INACTIVITY_DAYS_THRESHOLD)
        
        # Общее количество пользователей
        total_users = db.query(User).filter(User.is_active == True).count()
        
        # Пользователи зарегистрированные до пороговой даты
        old_users = db.query(User).filter(
            and_(
                User.is_active == True,
                User.registration_date < threshold_date
            )
        ).count()
        
        # Пользователи с покупками за последний период
        users_with_purchases = db.query(User).join(Purchase).filter(
            and_(
                User.is_active == True,
                Purchase.purchase_date > threshold_date
            )
        ).distinct().count()
        
        # Пользователи с тратами баллов за последний период
        users_with_redemptions = db.query(User).join(PointsHistory).filter(
            and_(
                User.is_active == True,
                PointsHistory.transaction_type == 'redemption',
                PointsHistory.created_date > threshold_date
            )
        ).distinct().count()
        
        # Приблизительное количество неактивных
        estimated_inactive = max(0, old_users - users_with_purchases - users_with_redemptions)
        
        stats_text = f"""
📊 Статистика неактивных пользователей

👥 Общая информация:
• Всего активных пользователей: {total_users}
• Зарегистрированы до {threshold_date.strftime('%d.%m.%Y')}: {old_users}

🛒 Активность за последние {config.INACTIVITY_DAYS_THRESHOLD} дней:
• Пользователи с покупками: {users_with_purchases}
• Пользователи с тратами баллов: {users_with_redemptions}

😴 Неактивные пользователи:
• Приблизительно неактивных: {estimated_inactive}
• Процент неактивных: {(estimated_inactive/total_users*100):.1f}% (от общего числа)

ℹ️ Точное количество рассчитывается при отправке уведомлений
        """
        
        await query.edit_message_text(
            stats_text,
            reply_markup=admin_notifications_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики неактивных: {e}")
        await query.edit_message_text(
            f"❌ Ошибка при получении статистики: {str(e)}",
            reply_markup=admin_notifications_keyboard()
        )
    finally:
        db.close()

async def admin_notification_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройки системы"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    weekday_name = weekday_names[config.NOTIFICATION_WEEKDAY]
    
    settings_text = f"""
⚙️ Настройки системы

🔔 Уведомления:
• Включены: {'✅ Да' if config.ENABLE_NOTIFICATIONS else '❌ Нет'}
• Дни неактивности: {config.INACTIVITY_DAYS_THRESHOLD}
• Расписание: {weekday_name}, {config.NOTIFICATION_HOUR:02d}:{config.NOTIFICATION_MINUTE:02d}
• Бонус за возвращение: {config.WELCOME_BACK_BONUS} баллов
• Подарок на ДР: {config.BIRTHDAY_BONUS} баллов

💰 Программа лояльности:
• Баллы за покупку: {config.POINTS_PER_PURCHASE}%
• Порог для бонуса: {config.BONUS_THRESHOLD} баллов
• Размер бонуса: {config.BONUS_AMOUNT} баллов
• Бонус за реферала: {config.REFERRAL_BONUS} баллов

📝 Нажмите на кнопку для редактирования параметра.
    """
    
    keyboard = [
        [InlineKeyboardButton("🔔 Вкл/выкл уведомления", callback_data="toggle_notifications")],
        [InlineKeyboardButton(f"📅 Дни неактивности ({config.INACTIVITY_DAYS_THRESHOLD})", callback_data="edit_inactivity_days")],
        [InlineKeyboardButton(f"📆 День недели ({weekday_name})", callback_data="edit_notification_weekday")],
        [InlineKeyboardButton(f"🕐 Время отправки ({config.NOTIFICATION_HOUR:02d}:{config.NOTIFICATION_MINUTE:02d})", callback_data="edit_notification_time")],
        [InlineKeyboardButton(f"🎁 Бонус возвращения ({config.WELCOME_BACK_BONUS})", callback_data="edit_welcome_bonus")],
        [InlineKeyboardButton(f"🎂 Подарок на ДР ({config.BIRTHDAY_BONUS})", callback_data="edit_birthday_bonus")],
        [InlineKeyboardButton(f"💰 Баллы за покупку ({config.POINTS_PER_PURCHASE}%)", callback_data="edit_points_per_purchase")],
        [InlineKeyboardButton(f"🎯 Порог бонуса ({config.BONUS_THRESHOLD})", callback_data="edit_bonus_threshold")],
        [InlineKeyboardButton(f"💎 Размер бонуса ({config.BONUS_AMOUNT})", callback_data="edit_bonus_amount")],
        [InlineKeyboardButton(f"👥 Бонус реферала ({config.REFERRAL_BONUS})", callback_data="edit_referral_bonus")],
        [InlineKeyboardButton("🔙 Назад к уведомлениям", callback_data="admin_notifications")]
    ]
    
    await query.edit_message_text(
        settings_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключение уведомлений"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    # Переключаем состояние
    new_state = not config.ENABLE_NOTIFICATIONS
    
    if save_config_to_file('ENABLE_NOTIFICATIONS', str(new_state).lower()):
        status = "включены" if new_state else "выключены"
        await query.edit_message_text(
            f"✅ Уведомления {status}!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
        )
    else:
        await query.edit_message_text(
            "❌ Ошибка при сохранении настройки.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
        )

async def edit_inactivity_days_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования дней неактивности"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return ConversationHandler.END
    
    await query.edit_message_text(
        f"📅 Редактирование дней неактивности\n\n"
        f"Текущее значение: {config.INACTIVITY_DAYS_THRESHOLD} дней\n\n"
        f"Введите новое количество дней (1-365):",
        reply_markup=cancel_keyboard()
    )
    
    return ADMIN_EDIT_INACTIVITY_DAYS

async def edit_inactivity_days_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение нового значения дней неактивности"""
    try:
        new_value = int(update.message.text)
        
        if new_value < 1 or new_value > 365:
            await update.message.reply_text(
                "❌ Некорректное значение. Введите число от 1 до 365:",
                reply_markup=cancel_keyboard()
            )
            return ADMIN_EDIT_INACTIVITY_DAYS
        
        if save_config_to_file('INACTIVITY_DAYS_THRESHOLD', new_value):
            await update.message.reply_text(
                f"✅ Дни неактивности обновлены: {new_value} дней",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка при сохранении настройки.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
            )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Некорректное значение. Введите число:",
            reply_markup=cancel_keyboard()
        )
        return ADMIN_EDIT_INACTIVITY_DAYS

# Добавлю остальные функции редактирования настроек
async def edit_welcome_bonus_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования бонуса за возвращение"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"🎁 Редактирование бонуса за возвращение\n\n"
        f"Текущее значение: {config.WELCOME_BACK_BONUS} баллов\n\n"
        f"Введите новое количество баллов (0-1000):",
        reply_markup=cancel_keyboard()
    )
    
    return ADMIN_EDIT_WELCOME_BONUS

async def edit_welcome_bonus_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение нового значения бонуса за возвращение"""
    try:
        new_value = int(update.message.text)
        
        if new_value < 0 or new_value > 1000:
            await update.message.reply_text(
                "❌ Некорректное значение. Введите число от 0 до 1000:",
                reply_markup=cancel_keyboard()
            )
            return ADMIN_EDIT_WELCOME_BONUS
        
        if save_config_to_file('WELCOME_BACK_BONUS', new_value):
            await update.message.reply_text(
                f"✅ Бонус за возвращение обновлен: {new_value} баллов",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка при сохранении настройки.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
            )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Некорректное значение. Введите число:",
            reply_markup=cancel_keyboard()
        )
        return ADMIN_EDIT_WELCOME_BONUS

async def edit_birthday_bonus_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования подарка на день рождения"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"🎂 Редактирование подарка на день рождения\n\n"
        f"Текущее значение: {config.BIRTHDAY_BONUS} баллов\n\n"
        f"Введите новое количество баллов (0-1000):",
        reply_markup=cancel_keyboard()
    )
    
    return ADMIN_EDIT_BIRTHDAY_BONUS

async def edit_birthday_bonus_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение нового значения подарка на день рождения"""
    try:
        new_value = int(update.message.text)
        
        if new_value < 0 or new_value > 1000:
            await update.message.reply_text(
                "❌ Некорректное значение. Введите число от 0 до 1000:",
                reply_markup=cancel_keyboard()
            )
            return ADMIN_EDIT_BIRTHDAY_BONUS
        
        if save_config_to_file('BIRTHDAY_BONUS', new_value):
            await update.message.reply_text(
                f"✅ Подарок на день рождения обновлен: {new_value} баллов",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка при сохранении настройки.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
            )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Некорректное значение. Введите число:",
            reply_markup=cancel_keyboard()
        )
        return ADMIN_EDIT_BIRTHDAY_BONUS

async def edit_points_per_purchase_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования баллов за покупку"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"💰 Редактирование баллов за покупку\n\n"
        f"Текущее значение: {config.POINTS_PER_PURCHASE}%\n\n"
        f"Введите новый процент (1-100):",
        reply_markup=cancel_keyboard()
    )
    
    return ADMIN_EDIT_POINTS_PER_PURCHASE

async def edit_points_per_purchase_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение нового значения баллов за покупку"""
    try:
        new_value = int(update.message.text)
        
        if new_value < 1 or new_value > 100:
            await update.message.reply_text(
                "❌ Некорректное значение. Введите число от 1 до 100:",
                reply_markup=cancel_keyboard()
            )
            return ADMIN_EDIT_POINTS_PER_PURCHASE
        
        if save_config_to_file('POINTS_PER_PURCHASE', new_value):
            await update.message.reply_text(
                f"✅ Баллы за покупку обновлены: {new_value}%",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка при сохранении настройки.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
            )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Некорректное значение. Введите число:",
            reply_markup=cancel_keyboard()
        )
        return ADMIN_EDIT_POINTS_PER_PURCHASE

async def edit_bonus_threshold_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования порога для бонуса"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"🎯 Редактирование порога для бонуса\n\n"
        f"Текущее значение: {config.BONUS_THRESHOLD} баллов\n\n"
        f"Введите новое количество баллов (10-10000):",
        reply_markup=cancel_keyboard()
    )
    
    return ADMIN_EDIT_BONUS_THRESHOLD

async def edit_bonus_threshold_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение нового значения порога для бонуса"""
    try:
        new_value = int(update.message.text)
        
        if new_value < 10 or new_value > 10000:
            await update.message.reply_text(
                "❌ Некорректное значение. Введите число от 10 до 10000:",
                reply_markup=cancel_keyboard()
            )
            return ADMIN_EDIT_BONUS_THRESHOLD
        
        if save_config_to_file('BONUS_THRESHOLD', new_value):
            await update.message.reply_text(
                f"✅ Порог для бонуса обновлен: {new_value} баллов",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка при сохранении настройки.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
            )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Некорректное значение. Введите число:",
            reply_markup=cancel_keyboard()
        )
        return ADMIN_EDIT_BONUS_THRESHOLD

async def edit_bonus_amount_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования размера бонуса"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"💎 Редактирование размера бонуса\n\n"
        f"Текущее значение: {config.BONUS_AMOUNT} баллов\n\n"
        f"Введите новое количество баллов (1-1000):",
        reply_markup=cancel_keyboard()
    )
    
    return ADMIN_EDIT_BONUS_AMOUNT

async def edit_bonus_amount_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение нового значения размера бонуса"""
    try:
        new_value = int(update.message.text)
        
        if new_value < 1 or new_value > 1000:
            await update.message.reply_text(
                "❌ Некорректное значение. Введите число от 1 до 1000:",
                reply_markup=cancel_keyboard()
            )
            return ADMIN_EDIT_BONUS_AMOUNT
        
        if save_config_to_file('BONUS_AMOUNT', new_value):
            await update.message.reply_text(
                f"✅ Размер бонуса обновлен: {new_value} баллов",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка при сохранении настройки.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
            )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Некорректное значение. Введите число:",
            reply_markup=cancel_keyboard()
        )
        return ADMIN_EDIT_BONUS_AMOUNT

async def edit_referral_bonus_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования бонуса за реферала"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"👥 Редактирование бонуса за реферала\n\n"
        f"Текущее значение: {config.REFERRAL_BONUS} баллов\n\n"
        f"Введите новое количество баллов (0-500):",
        reply_markup=cancel_keyboard()
    )
    
    return ADMIN_EDIT_REFERRAL_BONUS

async def edit_referral_bonus_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение нового значения бонуса за реферала"""
    try:
        new_value = int(update.message.text)
        
        if new_value < 0 or new_value > 500:
            await update.message.reply_text(
                "❌ Некорректное значение. Введите число от 0 до 500:",
                reply_markup=cancel_keyboard()
            )
            return ADMIN_EDIT_REFERRAL_BONUS
        
        if save_config_to_file('REFERRAL_BONUS', new_value):
            await update.message.reply_text(
                f"✅ Бонус за реферала обновлен: {new_value} баллов",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка при сохранении настройки.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")]])
            )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Некорректное значение. Введите число:",
            reply_markup=cancel_keyboard()
        )
        return ADMIN_EDIT_REFERRAL_BONUS

async def edit_notification_weekday_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования дня недели для уведомлений"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return ConversationHandler.END
    
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    current_weekday = weekday_names[config.NOTIFICATION_WEEKDAY]
    
    keyboard = []
    for i, day in enumerate(weekday_names):
        check_mark = "✅" if i == config.NOTIFICATION_WEEKDAY else "⬜"
        keyboard.append([InlineKeyboardButton(f"{check_mark} {day}", callback_data=f"weekday_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_notification_settings")])
    
    await query.edit_message_text(
        f"📆 Выберите день недели для отправки уведомлений\n\nТекущий: {current_weekday}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return ADMIN_EDIT_NOTIFICATION_WEEKDAY

async def edit_notification_weekday_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора дня недели"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return ConversationHandler.END
    
    if query.data.startswith("weekday_"):
        new_weekday = int(query.data.split("_")[1])
        
        if save_config_to_file('NOTIFICATION_WEEKDAY', new_weekday):
            weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
            weekday_name = weekday_names[new_weekday]
            
            await query.edit_message_text(
                f"✅ День недели изменен на: {weekday_name}\n\n"
                f"Уведомления будут отправляться по {weekday_name.lower()}м в {config.NOTIFICATION_HOUR:02d}:{config.NOTIFICATION_MINUTE:02d}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")
                ]])
            )
        else:
            await query.edit_message_text(
                "❌ Ошибка при сохранении настройки",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")
                ]])
            )
        
        return ConversationHandler.END
    
    elif query.data == "admin_notification_settings":
        await admin_notification_settings(update, context)
        return ConversationHandler.END
    
    return ConversationHandler.END

async def edit_notification_time_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования времени отправки уведомлений"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return ConversationHandler.END
    
    await query.edit_message_text(
        f"🕐 Введите час для отправки уведомлений (0-23)\n\n"
        f"Текущее время: {config.NOTIFICATION_HOUR:02d}:{config.NOTIFICATION_MINUTE:02d}\n"
        f"Пример: 12 (для 12:00)",
        reply_markup=cancel_keyboard()
    )
    
    return ADMIN_EDIT_NOTIFICATION_HOUR

async def edit_notification_hour_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода часа"""
    try:
        new_hour = int(update.message.text)
        
        if 0 <= new_hour <= 23:
            if save_config_to_file('NOTIFICATION_HOUR', new_hour):
                await update.message.reply_text(
                    f"✅ Час изменен на: {new_hour:02d}\n\n"
                    f"Теперь введите минуты (0-59):",
                    reply_markup=cancel_keyboard()
                )
                return ADMIN_EDIT_NOTIFICATION_MINUTE
            else:
                await update.message.reply_text(
                    "❌ Ошибка при сохранении настройки",
                    reply_markup=cancel_keyboard()
                )
                return ConversationHandler.END
        else:
            await update.message.reply_text(
                "❌ Некорректное значение. Введите число от 0 до 23:",
                reply_markup=cancel_keyboard()
            )
            return ADMIN_EDIT_NOTIFICATION_HOUR
            
    except ValueError:
        await update.message.reply_text(
            "❌ Некорректное значение. Введите число от 0 до 23:",
            reply_markup=cancel_keyboard()
        )
        return ADMIN_EDIT_NOTIFICATION_HOUR

async def edit_notification_minute_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода минут"""
    try:
        new_minute = int(update.message.text)
        
        if 0 <= new_minute <= 59:
            if save_config_to_file('NOTIFICATION_MINUTE', new_minute):
                weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
                weekday_name = weekday_names[config.NOTIFICATION_WEEKDAY]
                
                await update.message.reply_text(
                    f"✅ Время изменено на: {config.NOTIFICATION_HOUR:02d}:{new_minute:02d}\n\n"
                    f"Уведомления будут отправляться по {weekday_name.lower()}м в {config.NOTIFICATION_HOUR:02d}:{new_minute:02d}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад к настройкам", callback_data="admin_notification_settings")
                    ]])
                )
                return ConversationHandler.END
            else:
                await update.message.reply_text(
                    "❌ Ошибка при сохранении настройки",
                    reply_markup=cancel_keyboard()
                )
                return ConversationHandler.END
        else:
            await update.message.reply_text(
                "❌ Некорректное значение. Введите число от 0 до 59:",
                reply_markup=cancel_keyboard()
            )
            return ADMIN_EDIT_NOTIFICATION_MINUTE
            
    except ValueError:
        await update.message.reply_text(
            "❌ Некорректное значение. Введите число от 0 до 59:",
            reply_markup=cancel_keyboard()
        )
        return ADMIN_EDIT_NOTIFICATION_MINUTE

async def back_to_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное админ меню"""
    query = update.callback_query
    await query.answer()
    
    admin_text = """
🔧 Админ панель

Выберите действие:
    """
    
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика пользователей", callback_data="admin_stats")],
        [InlineKeyboardButton("📈 Графики статистики", callback_data="admin_charts_menu")],
        [InlineKeyboardButton("🎯 Создать акцию", callback_data="admin_create_promotion")],
        [InlineKeyboardButton("🗑️ Управление акциями", callback_data="admin_manage_promotions")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🎁 Праздничные подарки", callback_data="admin_gift_menu")],
        [InlineKeyboardButton("🔔 Уведомления", callback_data="admin_notifications")],
        [InlineKeyboardButton("🎉 Розыгрыш", callback_data="admin_giveaway_menu")]
    ]
    admin_kb = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        admin_text,
        reply_markup=admin_kb
    )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика пользователей"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    db = get_db()
    
    try:
        # Получаем статистику
        from sqlalchemy import func
        from database import User, Purchase, PointsHistory
        
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        total_purchases = db.query(Purchase).count()
        
        # Общая сумма всех покупок (включая возвращенные)
        total_spent_all = db.query(func.sum(Purchase.amount)).scalar() or 0
        
        # Сумма возвращенных покупок
        total_returned_amount = db.query(func.sum(Purchase.amount)).filter(
            Purchase.is_returned == True
        ).scalar() or 0
        
        # Итоговая сумма покупок (без возвратов)
        total_spent = total_spent_all - total_returned_amount
        # Общая сумма всех начислений (положительные изменения)
        total_points_earned = db.query(func.sum(PointsHistory.points_change)).filter(
            PointsHistory.points_change > 0
        ).scalar() or 0
        
        # Списанные баллы (redemption)
        total_points_redeemed = db.query(func.sum(PointsHistory.points_change)).filter(
            PointsHistory.transaction_type == 'redemption'
        ).scalar() or 0
        
        # Возвращенные баллы (return) и другие отрицательные операции
        total_points_returned = db.query(func.sum(PointsHistory.points_change)).filter(
            PointsHistory.points_change < 0,
            PointsHistory.transaction_type != 'redemption'
        ).scalar() or 0
        
        # Чистый баланс выданных баллов (выдано - списано - возвращено)
        total_points_net = total_points_earned + total_points_redeemed + total_points_returned
        
        # Текущий баланс всех пользователей
        current_balance = db.query(func.sum(User.points)).scalar() or 0
        
        # Последние регистрации
        recent_users = db.query(User).order_by(User.registration_date.desc()).limit(5).all()
        
        # Считаем количество возвращенных покупок
        returned_purchases_count = db.query(Purchase).filter(Purchase.is_returned == True).count()
        
        stats_text = f"""
📊 Статистика системы

👥 Пользователи:
• Всего зарегистрировано: {total_users}
• Активных: {active_users}

💰 Покупки:
• Всего покупок: {total_purchases}
• Возвращенных покупок: {returned_purchases_count}
• Активных покупок: {total_purchases - returned_purchases_count}
• Общая сумма: {total_spent_all:.2f}₽
• Сумма возвратов: {total_returned_amount:.2f}₽
• Итоговая сумма: {total_spent:.2f}₽

🎁 Баллы:
• Всего начислено: {total_points_earned}
• Списанные баллы: {abs(total_points_redeemed)}
• Возвращенные баллы: {abs(total_points_returned)}
• Итого выдано: {total_points_net}
• Текущий баланс пользователей: {current_balance}
{f'⚠️ Расхождение: {abs(total_points_net - current_balance)} баллов' if abs(total_points_net - current_balance) > 0 else '✅ Баланс корректен'}

📈 Последние регистрации:
        """
        
        for user in recent_users:
            stats_text += f"• {user.first_name} ({user.registration_date.strftime('%d.%m.%Y')})\n"
        
        await query.edit_message_text(
            stats_text,
            reply_markup=back_to_admin_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в admin_stats: {e}")
        await query.edit_message_text(
            "❌ Ошибка при получении статистики.",
            reply_markup=back_to_admin_keyboard()
        )
    finally:
        db.close()

async def admin_create_promotion_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания акции"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return ConversationHandler.END
    
    await query.edit_message_text(
        "🎯 Создание акции\n\nВведите название акции:",
        reply_markup=cancel_keyboard()
    )
    
    return ADMIN_PROMO_TITLE

async def admin_create_promotion_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение названия акции"""
    title = update.message.text
    context.user_data['promo_title'] = title
    
    await update.message.reply_text(
        f"✅ Название: {title}\n\nВведите описание акции:",
        reply_markup=cancel_keyboard()
    )
    
    return ADMIN_PROMO_DESCRIPTION

async def admin_create_promotion_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение описания акции"""
    description = update.message.text
    context.user_data['promo_description'] = description
    
    await update.message.reply_text(
        f"✅ Описание сохранено\n\nХотите добавить медиафайл к акции? (фото, видео, документ)",
        reply_markup=admin_media_keyboard()
    )
    
    return ADMIN_PROMO_MEDIA

async def admin_create_promotion_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка медиафайлов для акции"""
    if update.callback_query:
        # Обработка нажатий кнопок
        query = update.callback_query
        await query.answer()
        
        if query.data == "add_media":
            await query.edit_message_text(
                "📷 Отправьте медиафайл для акции (фото, видео, документ):",
                reply_markup=cancel_keyboard()
            )
            return ADMIN_PROMO_MEDIA
        elif query.data == "skip_media":
            context.user_data['promo_media'] = None
            await query.edit_message_text(
                f"✅ Продолжаем без медиа\n\nВведите процент скидки (или 0, если не нужна скидка):",
                reply_markup=cancel_keyboard()
            )
            return ADMIN_PROMO_DISCOUNT
        elif query.data == "cancel_admin":
            return await cancel_admin_action(update, context)
    else:
        # Обработка медиафайлов
        media_info = None
        
        if update.message.photo:
            # Фото
            photo = update.message.photo[-1]  # Берем самое большое разрешение
            media_info = {
                'type': 'photo',
                'file_id': photo.file_id,
                'caption': update.message.caption
            }
        elif update.message.video:
            # Видео
            video = update.message.video
            media_info = {
                'type': 'video',
                'file_id': video.file_id,
                'caption': update.message.caption
            }
        elif update.message.document:
            # Документ
            document = update.message.document
            media_info = {
                'type': 'document',
                'file_id': document.file_id,
                'caption': update.message.caption
            }
        else:
            await update.message.reply_text(
                "❌ Неподдерживаемый тип файла. Отправьте фото, видео или документ:",
                reply_markup=cancel_keyboard()
            )
            return ADMIN_PROMO_MEDIA
        
        context.user_data['promo_media'] = media_info
        
        await update.message.reply_text(
            f"✅ Медиафайл сохранен ({media_info['type']})\n\nВведите процент скидки (или 0, если не нужна скидка):",
            reply_markup=cancel_keyboard()
        )
        
        return ADMIN_PROMO_DISCOUNT

async def admin_create_promotion_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение скидки и создание акции"""
    try:
        discount = int(update.message.text)
        
        # Создаем акцию
        db = get_db()
        promotion_service = PromotionService(db)
        
        # Устанавливаем даты: начало - сейчас, конец - через месяц
        start_date = datetime.now()
        end_date = start_date + timedelta(days=30)
        
        promotion = promotion_service.create_promotion(
            title=context.user_data['promo_title'],
            description=context.user_data['promo_description'],
            discount_percent=discount if discount > 0 else None,
            start_date=start_date,
            end_date=end_date
        )
        
        # Отправляем уведомление администратору о создании акции
        await update.message.reply_text(
            f"✅ Акция создана!\n\n"
            f"🎯 Название: {promotion.title}\n"
            f"📝 Описание: {promotion.description}\n"
            f"💰 Скидка: {promotion.discount_percent or 0}%\n"
            f"📅 Действует до: {end_date.strftime('%d.%m.%Y')}\n\n"
            f"📤 Отправляю уведомления всем пользователям...",
            reply_markup=back_to_admin_keyboard()
        )
        
        # Отправляем уведомления всем пользователям о новой акции
        try:
            from notifications import send_promotion_notification_with_media
            media_info = context.user_data.get('promo_media')
            
            successful, failed = await send_promotion_notification_with_media(
                bot=context.bot,
                promotion_title=promotion.title,
                promotion_description=promotion.description,
                discount_percent=promotion.discount_percent,
                media_info=media_info
            )
            
            # Сообщаем админу о результатах рассылки
            await update.message.reply_text(
                f"📊 Результаты рассылки уведомлений:\n\n"
                f"✅ Успешно отправлено: {successful}\n"
                f"❌ Ошибок: {failed}\n\n"
                f"🎉 Все пользователи уведомлены о новой акции!"
            )
            
            logger.info(f"Создана акция '{promotion.title}' и отправлены уведомления: {successful} успешно, {failed} ошибок")
            
        except Exception as notification_error:
            logger.error(f"Ошибка при отправке уведомлений о акции: {notification_error}")
            await update.message.reply_text(
                f"⚠️ Акция создана, но произошла ошибка при отправке уведомлений:\n{str(notification_error)}"
            )
        
        db.close()
        
    except ValueError:
        await update.message.reply_text(
            "❌ Некорректное значение. Введите число от 0 до 100:",
            reply_markup=cancel_keyboard()
        )
        return ADMIN_PROMO_DISCOUNT
    except Exception as e:
        logger.error(f"Ошибка при создании акции: {e}")
        await update.message.reply_text(
            "❌ Ошибка при создании акции.",
            reply_markup=back_to_admin_keyboard()
        )
    
    # Очищаем данные
    context.user_data.clear()
    return ConversationHandler.END

async def admin_manage_promotions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление акциями"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    db = get_db()
    promotion_service = PromotionService(db)
    
    try:
        logger.info(f"Администратор {update.effective_user.id} запросил список акций")
        
        # Получаем все активные акции
        promotions = promotion_service.get_active_promotions()
        logger.info(f"Найдено {len(promotions)} активных акций")
        
        if not promotions:
            await query.edit_message_text(
                "📭 Активных акций пока нет.\n\n💡 Создайте акцию через главное меню админ-панели.",
                reply_markup=back_to_admin_keyboard()
            )
            return
        
        # Формируем текст со списком акций
        promo_text = "🗑️ Управление акциями\n\nВыберите акцию для удаления:\n\n"
        
        for i, promo in enumerate(promotions, 1):
            end_date = promo.end_date.strftime('%d.%m.%Y') if promo.end_date else 'Без ограничений'
            discount_text = f" ({promo.discount_percent}% скидка)" if promo.discount_percent else ""
            promo_text += f"{i}. {promo.title}{discount_text}\n   📅 До: {end_date}\n\n"
        
        # Создаем клавиатуру с акциями
        keyboard = []
        for promo in promotions:
            discount_text = f" ({promo.discount_percent}%)" if promo.discount_percent else ""
            button_text = f"🗑️ {promo.title[:25]}{discount_text}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"delete_promo_{promo.id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            promo_text,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка акций: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка при загрузке акций:\n{str(e)}\n\nОбратитесь к администратору.",
            reply_markup=back_to_admin_keyboard()
        )
    finally:
        db.close()

async def admin_delete_promotion_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления акции"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    # Извлекаем ID акции из callback_data
    promo_id = int(query.data.split('_')[2])
    context.user_data['delete_promo_id'] = promo_id
    
    db = get_db()
    promotion_service = PromotionService(db)
    
    try:
        promotion = promotion_service.get_promotion_by_id(promo_id)
        
        if not promotion:
            await query.edit_message_text(
                "❌ Акция не найдена.",
                reply_markup=back_to_admin_keyboard()
            )
            return
        
        end_date = promotion.end_date.strftime('%d.%m.%Y') if promotion.end_date else 'Без ограничений'
        discount_text = f"💰 Скидка: {promotion.discount_percent}%\n" if promotion.discount_percent else ""
        
        confirm_text = f"""
⚠️ Подтверждение удаления акции

🎯 Название: {promotion.title}
📝 Описание: {promotion.description}
{discount_text}📅 Действует до: {end_date}

❗ ВНИМАНИЕ: Это действие нельзя отменить!

Вы уверены, что хотите удалить эту акцию?
        """
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, удалить", callback_data="confirm_delete_promo")],
            [InlineKeyboardButton("❌ Отмена", callback_data="admin_manage_promotions")],
            [InlineKeyboardButton("🔙 Назад к списку", callback_data="admin_manage_promotions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            confirm_text,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке акции для удаления: {e}")
        await query.edit_message_text(
            "❌ Ошибка при загрузке акции.",
            reply_markup=back_to_admin_keyboard()
        )
    finally:
        db.close()

async def admin_confirm_delete_promotion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтвержденное удаление акции"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    promo_id = context.user_data.get('delete_promo_id')
    if not promo_id:
        await query.edit_message_text(
            "❌ Ошибка: ID акции не найден.",
            reply_markup=back_to_admin_keyboard()
        )
        return
    
    db = get_db()
    promotion_service = PromotionService(db)
    
    try:
        promotion = promotion_service.get_promotion_by_id(promo_id)
        
        if not promotion:
            await query.edit_message_text(
                "❌ Акция не найдена.",
                reply_markup=back_to_admin_keyboard()
            )
            return
        
        # Сохраняем информацию для логирования
        promo_title = promotion.title
        
        # Удаляем акцию
        success = promotion_service.delete_promotion(promo_id)
        
        if success:
            await query.edit_message_text(
                f"✅ Акция '{promo_title}' успешно удалена!",
                reply_markup=back_to_admin_keyboard()
            )
            
            logger.info(f"Администратор {update.effective_user.id} удалил акцию '{promo_title}' (ID: {promo_id})")
        else:
            await query.edit_message_text(
                "❌ Не удалось удалить акцию. Попробуйте позже.",
                reply_markup=back_to_admin_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Ошибка при удалении акции: {e}")
        await query.edit_message_text(
            "❌ Произошла ошибка при удалении акции.",
            reply_markup=back_to_admin_keyboard()
        )
    finally:
        # Очищаем данные
        context.user_data.clear()
        db.close()

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало рассылки"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return ConversationHandler.END
    
    await query.edit_message_text(
        "📢 Рассылка сообщения\n\nВведите текст для рассылки всем пользователям:",
        reply_markup=cancel_keyboard()
    )
    
    return ADMIN_BROADCAST_MESSAGE

async def admin_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение текста рассылки"""
    message_text = update.message.text
    context.user_data['broadcast_text'] = message_text
    
    await update.message.reply_text(
        f"✅ Текст сообщения сохранен\n\nХотите добавить медиафайл к рассылке? (фото, видео, документ)",
        reply_markup=admin_media_keyboard()
    )
    
    return ADMIN_BROADCAST_MEDIA

async def admin_broadcast_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка медиафайлов для рассылки"""
    if update.callback_query:
        # Обработка нажатий кнопок
        query = update.callback_query
        await query.answer()
        
        if query.data == "add_media":
            await query.edit_message_text(
                "📷 Отправьте медиафайл для рассылки (фото, видео, документ):",
                reply_markup=cancel_keyboard()
            )
            return ADMIN_BROADCAST_MEDIA
        elif query.data == "skip_media":
            context.user_data['broadcast_media'] = None
            await query.edit_message_text("📤 Начинаю рассылку...")
            return await send_broadcast_messages(update, context)
        elif query.data == "cancel_admin":
            return await cancel_admin_action(update, context)
    else:
        # Обработка медиафайлов
        media_info = None
        
        if update.message.photo:
            # Фото
            photo = update.message.photo[-1]  # Берем самое большое разрешение
            media_info = {
                'type': 'photo',
                'file_id': photo.file_id,
                'caption': update.message.caption
            }
        elif update.message.video:
            # Видео
            video = update.message.video
            media_info = {
                'type': 'video',
                'file_id': video.file_id,
                'caption': update.message.caption
            }
        elif update.message.document:
            # Документ
            document = update.message.document
            media_info = {
                'type': 'document',
                'file_id': document.file_id,
                'caption': update.message.caption
            }
        else:
            await update.message.reply_text(
                "❌ Неподдерживаемый тип файла. Отправьте фото, видео или документ:",
                reply_markup=cancel_keyboard()
            )
            return ADMIN_BROADCAST_MEDIA
        
        context.user_data['broadcast_media'] = media_info
        
        await update.message.reply_text(
            f"✅ Медиафайл сохранен ({media_info['type']})\n\n📤 Начинаю рассылку..."
        )
        
        return await send_broadcast_messages(update, context)

async def send_broadcast_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка рассылки пользователям"""
    message_text = context.user_data.get('broadcast_text')
    media_info = context.user_data.get('broadcast_media')
    
    db = get_db()
    
    try:
        # Получаем всех активных пользователей
        from database import User
        users = db.query(User).filter(User.is_active == True).all()
        
        sent_count = 0
        failed_count = 0
        
        for user in users:
            try:
                if media_info:
                    # Отправляем сообщение с медиафайлом
                    caption = f"📢 {message_text}"
                    
                    if media_info['type'] == 'photo':
                        await context.bot.send_photo(
                            chat_id=user.telegram_id,
                            photo=media_info['file_id'],
                            caption=caption
                        )
                    elif media_info['type'] == 'video':
                        await context.bot.send_video(
                            chat_id=user.telegram_id,
                            video=media_info['file_id'],
                            caption=caption
                        )
                    elif media_info['type'] == 'document':
                        await context.bot.send_document(
                            chat_id=user.telegram_id,
                            document=media_info['file_id'],
                            caption=caption
                        )
                else:
                    # Отправляем обычное текстовое сообщение
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"📢 {message_text}"
                    )
                sent_count += 1
            except Exception as e:
                failed_count += 1
                logger.warning(f"Не удалось отправить сообщение пользователю {user.telegram_id}: {e}")
        
        result_message = f"✅ Рассылка завершена!\n\n📤 Отправлено: {sent_count}\n❌ Не доставлено: {failed_count}"
        
        if update.callback_query:
            await update.callback_query.message.reply_text(
                result_message,
                reply_markup=back_to_admin_keyboard()
            )
        else:
            await update.message.reply_text(
                result_message,
                reply_markup=back_to_admin_keyboard()
            )
        
    except Exception as e:
        logger.error(f"Ошибка при рассылке: {e}")
        error_message = "❌ Ошибка при рассылке."
        
        if update.callback_query:
            await update.callback_query.message.reply_text(error_message, reply_markup=back_to_admin_keyboard())
        else:
            await update.message.reply_text(error_message, reply_markup=back_to_admin_keyboard())
    finally:
        db.close()
    
    # Очищаем данные
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена административного действия"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    
    await query.edit_message_text(
        "❌ Действие отменено.",
        reply_markup=back_to_admin_keyboard()
    )
    
    return ConversationHandler.END 

# Обработчики графиков статистики
async def admin_charts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню выбора графиков"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    charts_text = """
📈 Графики статистики

Выберите тип графика:
    """
    
    await query.edit_message_text(
        charts_text,
        reply_markup=admin_charts_keyboard()
    )

async def admin_chart_monthly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерирует и отправляет график месячной статистики"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    await query.edit_message_text("📊 Генерирую график статистики по месяцам...")
    
    try:
        chart_buffer = generate_monthly_stats_chart()
        
        if chart_buffer:
            # Отправляем график как фото
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=chart_buffer,
                caption="📊 Общая статистика по месяцам"
            )
            
            # Отправляем новое сообщение с кнопками
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="📈 Выберите другой график или вернитесь в админ-панель:",
                reply_markup=admin_charts_keyboard()
            )
            
            # Удаляем сообщение "генерирую..."
            try:
                await query.message.delete()
            except:
                pass
        else:
            await query.edit_message_text(
                "❌ Ошибка при генерации графика",
                reply_markup=admin_charts_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Ошибка генерации графика месячной статистики: {e}")
        try:
            await query.edit_message_text(
                "❌ Ошибка при генерации графика",
                reply_markup=admin_charts_keyboard()
            )
        except:
            # Если редактирование не удалось, отправляем новое сообщение
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ Ошибка при генерации графика",
                reply_markup=admin_charts_keyboard()
            )

# --- ФУНКЦИОНАЛ ПРАЗДНИЧНЫХ БАЛЛОВ ---

async def admin_gift_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню праздничных подарков"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("➕ Запустить новую акцию", callback_data="admin_gift_points_start")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]
    ]
    
    await query.edit_message_text(
        "🎁 Управление праздничными подарками\n\n"
        "Здесь вы можете подарить баллы всем текущим пользователям и установить "
        "период, в течение которого пользователи будут получать этот подарок.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_gift_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление текущими праздничными акциями"""
    query = update.callback_query
    await query.answer()
    
    db = get_db()
    try:
        from database import HolidayGift
        from sqlalchemy import or_
        now = datetime.now()
        active_gifts = db.query(HolidayGift).filter(
            HolidayGift.is_active == True,
            or_(HolidayGift.end_date == None, HolidayGift.end_date >= now)
        ).all()
        
        if not active_gifts:
            await query.edit_message_text(
                "📭 Активных праздничных акций для новых пользователей нет.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_gift_menu")]])
            )
            return
            
        text = "📜 Активные праздничные акции:\n\n"
        keyboard = []
        for gift in active_gifts:
            expiry_date_str = gift.end_date.strftime('%d.%m.%Y') if gift.end_date else 'Бессрочно'
            text += f"🎁 {gift.amount} баллов за '{gift.description}'\n"
            text += f"📅 Активна до: {expiry_date_str}\n"
            text += f"⏳ Сгорают через: {'не сгорают' if gift.days_to_expire == 0 else f'{gift.days_to_expire} дн.'}\n\n"
            
            keyboard.append([InlineKeyboardButton(f"🗑️ Удалить: {gift.description[:20]}...", callback_data=f"delete_holiday_{gift.id}")])
            
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_gift_menu")])
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Ошибка в admin_gift_manage: {e}")
        await query.edit_message_text("❌ Ошибка при загрузке акций.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_gift_menu")]]))
    finally:
        db.close()

async def admin_gift_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление праздничной акции (деактивация)"""
    query = update.callback_query
    await query.answer()
    
    gift_id = int(query.data.split('_')[2])
    db = get_db()
    try:
        from database import HolidayGift
        gift = db.query(HolidayGift).filter(HolidayGift.id == gift_id).first()
        if gift:
            gift.is_active = False
            db.commit()
            await query.edit_message_text(f"✅ Акция '{gift.description}' деактивирована.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_gift_manage")]]))
        else:
            await query.edit_message_text("❌ Акция не найдена.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_gift_manage")]]))
    except Exception as e:
        logger.error(f"Ошибка при удалении акции: {e}")
        await query.edit_message_text("❌ Ошибка при удалении.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_gift_manage")]]))
    finally:
        db.close()

async def admin_gift_points_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса дарения баллов на праздник"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return ConversationHandler.END
    
    await query.edit_message_text(
        "🎁 Подарочные баллы (Праздничная акция)\n\n"
        "1. Эти баллы будут начислены ВСЕМ зарегистрированным пользователям сейчас.\n"
        "2. Эти баллы будут автоматически выдаваться КАЖДОМУ новому пользователю при регистрации.\n\n"
        "Введите количество баллов, которое хотите подарить:",
        reply_markup=cancel_keyboard()
    )
    
    return ADMIN_GIFT_AMOUNT

async def admin_gift_points_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение суммы баллов"""
    try:
        amount = int(update.message.text)
        if amount <= 0:
            raise ValueError()
        
        context.user_data['gift_amount'] = amount
        
        await update.message.reply_text(
            f"✅ Сумма: {amount} баллов\n\n"
            "Через сколько дней эти баллы должны сгореть?\n"
            "(Введите количество дней, например: 7, 14, 30. Или 0, если не должны сгорать)",
            reply_markup=cancel_keyboard()
        )
        return ADMIN_GIFT_DAYS
    except ValueError:
        await update.message.reply_text("❌ Введите положительное целое число:", reply_markup=cancel_keyboard())
        return ADMIN_GIFT_AMOUNT

async def admin_gift_points_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение срока сгорания баллов"""
    try:
        days = int(update.message.text)
        if days < 0:
            raise ValueError()
            
        context.user_data['gift_days'] = days
        
        await update.message.reply_text(
            f"✅ Срок сгорания баллов: {'не сгорают' if days == 0 else f'{days} дней'}\n\n"
            "Введите описание повода (например: 'С 8 Марта!' или 'С Новым Годом!'):",
            reply_markup=cancel_keyboard()
        )
        return ADMIN_GIFT_DESCRIPTION
    except ValueError:
        await update.message.reply_text("❌ Введите число дней (0 или больше):", reply_markup=cancel_keyboard())
        return ADMIN_GIFT_DAYS

async def admin_gift_points_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем описание и спрашиваем пол целевой аудитории"""
    description = update.message.text.strip()
    context.user_data['gift_description'] = description
    
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    gender_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👩 Только женщинам", callback_data="gift_gender_female")],
        [InlineKeyboardButton("👨 Только мужчинам", callback_data="gift_gender_male")],
        [InlineKeyboardButton("👥 Всем", callback_data="gift_gender_all")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ])
    await update.message.reply_text(
        f"✅ Повод: {description}\n\n"
        "Кому начислить баллы?",
        reply_markup=gender_kb
    )
    return ADMIN_GIFT_GENDER

async def admin_gift_points_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем целевую аудиторию и запускаем начисление"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data == "gift_gender_female":
        context.user_data['gift_gender'] = 'female'
        audience_label = "женщинам"
    elif data == "gift_gender_male":
        context.user_data['gift_gender'] = 'male'
        audience_label = "мужчинам"
    else:
        context.user_data['gift_gender'] = None  # Всем
        audience_label = "всем"
    
    await query.edit_message_text(f"⏳ Готовлю начисление баллов {audience_label}...")
    
    # Передаем управление в финальную функцию
    return await admin_gift_points_finish(update, context)

async def admin_gift_points_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение и начисление баллов"""
    description = context.user_data.get('gift_description')
    amount = context.user_data.get('gift_amount')
    days = context.user_data.get('gift_days')
    gift_gender = context.user_data.get('gift_gender')  # None = всем, 'female', 'male'
    
    db = get_db()
    try:
        from database import User, HolidayGift
        from services import LoyaltyService
        import asyncio
        loyalty_service = LoyaltyService(db)
        
        # Вычисляем дату сгорания самих баллов
        expiry_date = None
        expiry_text = ""
        if days > 0:
            expiry_date = datetime.now() + timedelta(days=days)
            expiry_text = f"\n⏰ Баллы действительны до {expiry_date.strftime('%d.%m.%Y %H:%M')}"
        
        # Сохраняем акцию в базу данных, чтобы новые пользователи тоже получали бонус
        holiday_gift = HolidayGift(
            amount=amount,
            description=description,
            days_to_expire=days,
            start_date=datetime.now(),
            end_date=None, # Бессрочно до ручного выключения
            is_active=True
        )
        db.add(holiday_gift)
        db.commit()
        
        # Фильтруем пользователей по полу
        query = db.query(User).filter(User.is_active == True, User.is_registered == True)
        if gift_gender == 'female':
            query = query.filter(User.gender == 'female')
        elif gift_gender == 'male':
            query = query.filter(User.gender == 'male')
        users = query.all()
        
        audience_label = {None: 'все', 'female': 'женщины', 'male': 'мужчины'}[gift_gender]
        
        reply_func = update.callback_query.edit_message_text if update.callback_query else update.message.reply_text
        await reply_func(f"🚀 Начинаю начисление баллов для {audience_label} ({len(users)} чел.)...")
        
        success_count = 0
        for user in users:
            try:
                # Начисляем баллы
                loyalty_service.add_bonus_points(
                    user_id=user.id,
                    points=amount,
                    description=description,
                    expiry_date=expiry_date
                )
                
                # Отправляем уведомление
                msg = f"""
🎁 Вам подарок!

{description}
💰 Вам начислено {amount} бонусных баллов!
🏆 Ваш новый баланс: {user.points} баллов
{expiry_text}

Спасибо, что вы с нами! 🎉
                """
                try:
                    await context.bot.send_message(chat_id=user.telegram_id, text=msg.strip())
                except:
                    pass
                success_count += 1
                await asyncio.sleep(0.05) # Небольшая пауза
            except Exception as e:
                logger.error(f"Ошибка при подарке пользователю {user.id}: {e}")
        
        msg = (
            f"✅ Готово!\n\n"
            f"📊 Результат:\n"
            f"• Успешно начислено: {success_count}\n"
            f"• Повод: {description}\n"
            f"• Аудитория: {audience_label}\n"
            f"• Акция активна для новых регистраций до выключения."
        )
        if update.callback_query:
            try:
                await update.callback_query.delete_message()
            except:
                pass
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=msg,
                reply_markup=back_to_admin_keyboard()
            )
        else:
            await update.message.reply_text(msg, reply_markup=back_to_admin_keyboard())
        
    except Exception as e:
        logger.error(f"Ошибка в процессе дарения баллов: {e}")
        db.rollback()
        
        reply_func = update.callback_query.edit_message_text if update.callback_query else update.message.reply_text
        await reply_func("❌ Произошла ошибка при начислении.", reply_markup=back_to_admin_keyboard())
    finally:
        db.close()
        context.user_data.clear()
        
    return ConversationHandler.END

async def admin_chart_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерирует и отправляет график статистики баллов"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    await query.edit_message_text("🎁 Генерирую график статистики баллов...")
    
    try:
        chart_buffer = generate_points_chart()
        
        if chart_buffer:
            # Отправляем график как фото
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=chart_buffer,
                caption="🎁 Статистика баллов"
            )
            
            # Отправляем новое сообщение с кнопками
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="📈 Выберите другой график или вернитесь в админ-панель:",
                reply_markup=admin_charts_keyboard()
            )
            
            # Удаляем сообщение "генерирую..."
            try:
                await query.message.delete()
            except:
                pass
        else:
            await query.edit_message_text(
                "❌ Ошибка при генерации графика",
                reply_markup=admin_charts_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Ошибка генерации графика баллов: {e}")
        try:
            await query.edit_message_text(
                "❌ Ошибка при генерации графика",
                reply_markup=admin_charts_keyboard()
            )
        except:
            # Если редактирование не удалось, отправляем новое сообщение
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ Ошибка при генерации графика",
                reply_markup=admin_charts_keyboard()
            ) 