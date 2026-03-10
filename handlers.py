import logging
import asyncio
from telegram import Update, InputFile, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from io import BytesIO
from database import get_db
from services import UserService, LoyaltyService, QRService, PromotionService
from keyboards import *
import config
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler регистрации
WAITING_FIRST_NAME, WAITING_LAST_NAME, WAITING_BIRTH_DATE, WAITING_PHONE, WAITING_REFERRAL_CODE = range(5)
WAITING_GENDER = 5
# Состояния для админки
ADMIN_WAITING_USER_ID, ADMIN_WAITING_AMOUNT, ADMIN_WAITING_DESCRIPTION = range(10, 13)
ADMIN_WAITING_POINTS, ADMIN_WAITING_POINTS_DESCRIPTION = range(13, 15)

async def delete_message_safely(message):
    """Безопасно удаляет сообщение"""
    try:
        await message.delete()
        logger.info("QR код автоматически удален через 5 минут")
    except Exception as e:
        logger.warning(f"Не удалось удалить QR код: {e}")

async def delete_qr_job(context):
    """Job функция для удаления QR кода"""
    message = context.job.data
    await delete_message_safely(message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Проверяем реферальный код в аргументах
    referral_code = None
    if context.args:
        referral_code = context.args[0]
        context.user_data['pending_referral_code'] = referral_code
    
    db = get_db()
    user_service = UserService(db)
    
    try:
        # Проверяем, существует ли пользователь
        existing_user = user_service.get_user_by_telegram_id(user.id)
        
        if existing_user and existing_user.is_registered:
            # Пользователь уже зарегистрирован
            loyalty_service = LoyaltyService(db)
            is_returning_user = await _check_if_returning_user(existing_user, db)
        
            # Отправляем бонус возвращающемуся пользователю
            if is_returning_user and config.ENABLE_NOTIFICATIONS:
                success = loyalty_service.add_bonus_points(
                    existing_user.id,
                    config.WELCOME_BACK_BONUS,
                    "Бонус за возвращение в магазин"
                )
                if success:
                    # ЗАЩИТА ОТ НАКРУТКИ: Обновляем дату последнего бонуса за возвращение
                    existing_user.last_welcome_back_bonus_date = datetime.now()
                    db.commit()
                    # Обновляем объект пользователя чтобы получить актуальный баланс
                    db.refresh(existing_user)
                    
                    await update.message.reply_text(
                        f"🎉 Добро пожаловать обратно, {existing_user.first_name}!\n\n"
                        f"🎁 Мы соскучились и начислили тебе {config.WELCOME_BACK_BONUS} бонусных баллов!\n"
                        f"💳 Твой текущий баланс: {existing_user.points} баллов"
                    )
            
            # Обновляем объект пользователя перед отправкой главного меню
            db.refresh(existing_user)
            await _send_main_menu(update, existing_user)
        else:
            # Пользователь новый - начинаем регистрацию без создания записи в БД
            return await _start_registration(update, context)
            
    except Exception as e:
        logger.error(f"Ошибка в start handler: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")
    finally:
        db.close()

async def _start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс регистрации"""
    await update.message.reply_text(
        "🎉 Добро пожаловать в программу лояльности!\n\n"
        "Для использования всех возможностей программы нужно пройти быструю регистрацию.\n\n"
        "Как вас зовут? Напишите ваше имя:"
    )
    return WAITING_FIRST_NAME

async def handle_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода имени"""
    first_name = update.message.text.strip()
    
    if len(first_name) < 2 or len(first_name) > 50:
        await update.message.reply_text("Имя должно содержать от 2 до 50 символов. Попробуйте еще раз:")
        return WAITING_FIRST_NAME
    
    context.user_data['first_name'] = first_name
    await update.message.reply_text(f"Приятно познакомиться, {first_name}! 😊\n\nТеперь напишите вашу фамилию:")
    return WAITING_LAST_NAME

async def handle_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода фамилии"""
    last_name = update.message.text.strip()
    
    if len(last_name) < 2 or len(last_name) > 50:
        await update.message.reply_text("Фамилия должна содержать от 2 до 50 символов. Попробуйте еще раз:")
        return WAITING_LAST_NAME
    
    context.user_data['last_name'] = last_name
    await update.message.reply_text(
        "Отлично! 👍\n\n"
        "Теперь укажите вашу дату рождения в формате ДД.ММ.ГГГГ\n"
        "Например: 25.12.1990"
    )
    return WAITING_BIRTH_DATE

async def handle_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода даты рождения"""
    birth_date_str = update.message.text.strip()
    
    try:
        birth_date = datetime.strptime(birth_date_str, "%d.%m.%Y").date()
        
        # Проверяем, что возраст разумный (от 10 до 120 лет)
        today = datetime.now().date()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        if age < 10 or age > 120:
            await update.message.reply_text(
                "Пожалуйста, укажите корректную дату рождения в формате ДД.ММ.ГГГГ\n"
                "Например: 25.12.1990"
            )
            return WAITING_BIRTH_DATE
            
        context.user_data['birth_date'] = birth_date
        
        from telegram import ReplyKeyboardMarkup
        gender_keyboard = ReplyKeyboardMarkup(
            [["👩 Женский", "👨 Мужской", "⏭️ Пропустить"]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await update.message.reply_text(
            "Спасибо! 📅\n\n"
            "Укажите ваш пол (используется для праздничных акций):",
            reply_markup=gender_keyboard
        )
        return WAITING_GENDER
        
    except ValueError:
        await update.message.reply_text(
            "Неверный формат даты. Пожалуйста, используйте формат ДД.ММ.ГГГГ\n"
            "Например: 25.12.1990"
        )
        return WAITING_BIRTH_DATE

async def handle_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора пола"""
    text = update.message.text.strip()
    
    if "Женский" in text:
        context.user_data['gender'] = 'female'
    elif "Мужской" in text:
        context.user_data['gender'] = 'male'
    else:
        context.user_data['gender'] = None  # Пропустить
    
    await update.message.reply_text(
        "Последний шаг - поделитесь номером телефона.\n"
        "⚠️ Для продолжения необходимо нажать кнопку ниже и отправить контакт:",
        reply_markup=request_phone_keyboard()
    )
    return WAITING_PHONE

async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода номера телефона - только через кнопку отправки контакта"""
    phone = None
    phone_normalized = None
    
    # Принимаем только контакт через кнопку, текстовый ввод не принимается
    if not update.message.contact:
        await update.message.reply_text(
            "❌ Пожалуйста, используйте кнопку ниже для отправки номера телефона.\n\n"
            "📱 Нажмите на кнопку '📱 Поделиться номером телефона' и подтвердите отправку контакта.\n\n"
            "⚠️ Ввод номера текстом недоступен - необходимо отправить контакт через кнопку:",
            reply_markup=request_phone_keyboard()
        )
        return WAITING_PHONE
    
    # Если пользователь отправил контакт через кнопку
    phone = update.message.contact.phone_number
    if not phone:
        await update.message.reply_text(
            "❌ Не удалось получить номер телефона из контакта.\n\n"
            "Пожалуйста, попробуйте еще раз, нажав кнопку ниже:",
            reply_markup=request_phone_keyboard()
        )
        return WAITING_PHONE
    
    # Нормализуем номер (убираем все нецифровые символы кроме +)
    phone_normalized = ''.join(filter(lambda x: x.isdigit() or x == '+', phone))
    if not phone_normalized.startswith('+'):
        # Если номер без +, добавляем +7 для российских номеров
        if phone_normalized.startswith('7'):
            phone_normalized = '+' + phone_normalized
        elif phone_normalized.startswith('8'):
            phone_normalized = '+7' + phone_normalized[1:]
        else:
            phone_normalized = '+7' + phone_normalized
    
    # Строгая валидация: номер должен быть в формате +7 и содержать 11 цифр (7 + 10)
    phone_digits = ''.join(filter(str.isdigit, phone_normalized))
    if not phone_normalized.startswith('+7') or len(phone_digits) != 11:
        await update.message.reply_text(
            "❌ Некорректный номер телефона!\n\n"
            "📱 Полученный номер не соответствует формату российского номера.\n"
            "Пожалуйста, убедитесь, что вы отправляете корректный контакт с номером телефона.\n\n"
            "Попробуйте еще раз:",
            reply_markup=request_phone_keyboard()
        )
        return WAITING_PHONE
    
    # Сохраняем нормализованный номер (только цифры с +7)
    context.user_data['phone'] = phone_normalized
    
    # Проверяем, есть ли уже реферальный код из ссылки
    if 'pending_referral_code' in context.user_data:
        await update.message.reply_text("Отлично! 📱\n\nЗавершаем регистрацию...")
        
        # Автоматически используем реферальный код из ссылки
        referral_code = context.user_data['pending_referral_code']
        return await _complete_registration_with_referral(update, context, referral_code)
    else:
        # Спрашиваем про реферальный код только если его нет
        await update.message.reply_text(
            "Отлично! 📱\n\n"
            "Есть ли у вас реферальный код от друга?\n\n"
            "Введите код или нажмите 'Пропустить':",
            reply_markup=referral_input_keyboard()
        )
        return WAITING_REFERRAL_CODE

async def handle_referral_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода реферального кода"""
    referral_code = None
    
    if update.message.text and update.message.text.strip() != "⏭️ Пропустить":
        referral_code = update.message.text.strip().upper()
    
    return await _complete_registration_with_referral(update, context, referral_code)

async def _complete_registration_with_referral(update: Update, context: ContextTypes.DEFAULT_TYPE, referral_code=None):
    """Завершает регистрацию пользователя с применением реферального кода"""
    # Проверяем, что все обязательные данные заполнены
    if 'phone' not in context.user_data or not context.user_data['phone']:
        await update.message.reply_text(
            "❌ Ошибка: номер телефона не указан. Пожалуйста, начните регистрацию заново командой /start",
            reply_markup=main_menu_keyboard()
        )
        context.user_data.clear()
        from telegram.ext import ConversationHandler
        return ConversationHandler.END
    
    # Сохраняем данные пользователя
    db = get_db()
    user_service = UserService(db)
    loyalty_service = LoyaltyService(db)
    
    try:
        user_id = update.effective_user.id
        
        # Создаем пользователя с полными данными (пользователь создается только при завершении регистрации)
        user_telegram = update.effective_user
        success = user_service.complete_registration(
            telegram_id=user_id,
            first_name=context.user_data['first_name'],
            last_name=context.user_data['last_name'],
            birth_date=context.user_data['birth_date'],
            phone=context.user_data['phone'],
            username=user_telegram.username,
            gender=context.user_data.get('gender')
        )
        
        if not success:
            logger.error(f"Не удалось создать пользователя с telegram_id: {user_id}")
            await update.message.reply_text(
                "❌ Произошла ошибка при регистрации. Пожалуйста, попробуйте позже или обратитесь в поддержку."
            )
            context.user_data.clear()
            from telegram.ext import ConversationHandler
            return ConversationHandler.END
        
        # Получаем созданного пользователя
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            logger.error(f"Пользователь не найден после создания, telegram_id: {user_id}")
            await update.message.reply_text(
                "❌ Произошла ошибка при регистрации. Пожалуйста, попробуйте позже или обратитесь в поддержку."
            )
            context.user_data.clear()
            from telegram.ext import ConversationHandler
            return ConversationHandler.END
        
        referral_applied = False
        
        # Начисляем 10 баллов за регистрацию всем новым пользователям
        try:
            registration_bonus = 10
            success_bonus = loyalty_service.add_bonus_points(db_user.id, registration_bonus, 'Бонус за регистрацию')
            if success_bonus:
                logger.info(f"Бонус за регистрацию начислен пользователю {db_user.id} (telegram_id: {user_id}): {registration_bonus} баллов")
            else:
                logger.warning(f"Не удалось начислить бонус за регистрацию пользователю {db_user.id}")
        except Exception as e:
            logger.error(f"Ошибка при начислении бонуса за регистрацию: {e}", exc_info=True)
        
        # Обновляем объект пользователя чтобы получить актуальный баланс
        db.refresh(db_user)
        
        # Применяем реферальный код если есть
        if referral_code and not db_user.referred_by:
            if loyalty_service.apply_referral(db_user.id, referral_code):
                referral_applied = True
                # Обновляем объект пользователя чтобы получить актуальный баланс
                db.refresh(db_user)
                await update.message.reply_text(
                    f"🎉 Поздравляем! Вы получили {config.REFERRAL_BONUS} баллов за регистрацию по реферальной ссылке!"
                )
        
        # Обновляем объект пользователя чтобы получить актуальный баланс после всех начислений
        db.refresh(db_user)
        
        final_message = (
            f"🎉 Регистрация завершена успешно!\n\n"
            f"Добро пожаловать в программу лояльности, {context.user_data['first_name']}!\n\n"
            f"🎁 Ваш текущий баланс: {db_user.points} баллов\n"
            f"📱 Ваш реферальный код: {db_user.referral_code}\n\n"
        )
        
        if referral_applied:
            final_message += f"✨ В том числе:\n"
            final_message += f"   • 10 баллов за регистрацию\n"
            final_message += f"   • {config.REFERRAL_BONUS} баллов за реферальную программу\n\n"
        else:
            final_message += f"✨ Вы получили 10 баллов за регистрацию!\n\n"
        
        final_message += "Зарабатывайте баллы за покупки и приглашайте друзей!"
        
        # Удаляем клавиатуру регистрации и показываем главное меню
        await update.message.reply_text(
            final_message,
            reply_markup=ReplyKeyboardRemove()
        )
        # Отправляем главное меню отдельным сообщением
        await update.message.reply_text(
            "Выберите действие из меню ниже:",
            reply_markup=main_menu_keyboard()
        )
            
        # Очищаем временные данные
        context.user_data.clear()
            
    except Exception as e:
        logger.error(f"Ошибка при завершении регистрации: {e}")
        await update.message.reply_text("Произошла ошибка при регистрации. Попробуйте позже.")
    finally:
        db.close()
    
    from telegram.ext import ConversationHandler
    return ConversationHandler.END

async def _send_main_menu(update: Update, user):
    """Отправляет главное меню пользователю"""
    welcome_text = f"""
🎉 Добро пожаловать в программу лояльности, {user.first_name}!

🎁 Ваш текущий баланс: {user.points} баллов
📱 Ваш реферальный код: {user.referral_code}

Зарабатывайте баллы за покупки и приглашайте друзей!
За каждые 100₽ покупки = {config.POINTS_PER_PURCHASE} баллов

Выберите действие из меню ниже:
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=main_menu_keyboard()
    )

async def _check_if_returning_user(user, db) -> bool:
    """Проверяет, является ли пользователь возвращающимся после длительного отсутствия"""
    try:
        from database import Purchase, PointsHistory
        
        # ВАЖНО: Не даем бонус за возвращение только что зарегистрированным пользователям
        # Если пользователь зарегистрировался менее чем 7 дней назад, он не считается возвращающимся
        if user.registration_date:
            days_since_registration = (datetime.now() - user.registration_date).days
            if days_since_registration < 7:
                logger.info(f"Пользователь {user.telegram_id} зарегистрирован {days_since_registration} дней назад - не считается возвращающимся")
                return False
        
        # Пороговая дата для определения "возвращающегося" пользователя
        threshold_date = datetime.now() - timedelta(days=config.INACTIVITY_DAYS_THRESHOLD)
        
        # ЗАЩИТА ОТ НАКРУТКИ: Проверяем, когда в последний раз давали бонус за возвращение
        if user.last_welcome_back_bonus_date:
            # Если бонус уже давался недавно (меньше порогового периода), не даем повторно
            time_since_last_bonus = datetime.now() - user.last_welcome_back_bonus_date
            if time_since_last_bonus.days < config.INACTIVITY_DAYS_THRESHOLD:
                logger.info(f"Пользователь {user.telegram_id} уже получал бонус за возвращение {time_since_last_bonus.days} дней назад")
                return False
        
        # Проверяем последнюю активность (покупки или траты баллов)
        last_purchase = db.query(Purchase).filter(
            Purchase.user_id == user.id,
            Purchase.purchase_date > threshold_date
        ).first()
        
        last_redemption = db.query(PointsHistory).filter(
            PointsHistory.user_id == user.id,
            PointsHistory.transaction_type == 'redemption',
            PointsHistory.created_date > threshold_date
        ).first()
        
        # Если нет активности за пороговый период, считаем возвращающимся
        return not last_purchase and not last_redemption
        
    except Exception as e:
        logger.error(f"Ошибка при проверке возвращающегося пользователя: {e}")
        return False

async def _check_user_registration(user_id: int, update: Update) -> bool:
    """Проверяет, завершил ли пользователь регистрацию"""
    db = get_db()
    user_service = UserService(db)
    
    try:
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user or not db_user.is_registered:
            await update.message.reply_text(
                "❗ Для использования этой функции необходимо завершить регистрацию.\n"
                "Нажмите /start чтобы пройти регистрацию."
            )
            return False
        return True
    except Exception as e:
        logger.error(f"Ошибка при проверке регистрации: {e}")
        return False
    finally:
        db.close()

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать профиль пользователя"""
    user_id = update.effective_user.id
    
    # Проверяем регистрацию
    if not await _check_user_registration(user_id, update):
        return
    
    db = get_db()
    user_service = UserService(db)
    
    try:
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            error_text = "Пользователь не найден. Нажмите /start"
            if update.callback_query:
                await update.callback_query.edit_message_text(error_text)
            else:
                await update.message.reply_text(error_text)
            return
        
        profile_text = f"""
👤 Ваш профиль:

🆔 ID: {db_user.id}
👤 Имя: {db_user.first_name or 'Не указано'} {db_user.last_name or ''}
📱 Телефон: {db_user.phone or 'Не указан'}
📅 Дата рождения: {db_user.birth_date.strftime('%d.%m.%Y') if db_user.birth_date else 'Не указана'}
📅 Дата регистрации: {db_user.registration_date.strftime('%d.%m.%Y')}
🎁 Баллы: {db_user.points}
💰 Потрачено всего: {(db_user.total_spent or 0):.2f}₽
        """
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                profile_text,
                reply_markup=profile_keyboard()
            )
        else:
            await update.message.reply_text(
                profile_text,
                reply_markup=profile_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Ошибка в profile handler: {e}")
        error_text = "Произошла ошибка."
        if update.callback_query:
            await update.callback_query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)
    finally:
        db.close()

async def my_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о баллах"""
    user_id = update.effective_user.id
    
    # Проверяем регистрацию
    if not await _check_user_registration(user_id, update):
        return
    
    db = get_db()
    user_service = UserService(db)
    loyalty_service = LoyaltyService(db)
    
    try:
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            await update.message.reply_text("Пользователь не найден.")
            return
        
        stats = loyalty_service.get_user_statistics(db_user.id)
        
        points_text = f"""
🎁 Мои баллы: {stats['points']}

📊 Статистика:
• Покупок совершено: {stats['purchases_count']}
• Потрачено всего: {stats['total_spent']:.2f}₽
• Приглашено друзей: {stats['referrals_count']}

💡 Как заработать баллы:
• За покупки: {config.POINTS_PER_PURCHASE} баллов за 100₽
• За приглашение друга: {config.REFERRAL_BONUS} баллов
• Бонус при накоплении {config.BONUS_THRESHOLD} баллов: +{config.BONUS_AMOUNT} баллов
        """
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                points_text,
                reply_markup=points_keyboard()
            )
        else:
            await update.message.reply_text(
                points_text,
                reply_markup=points_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Ошибка в my_points handler: {e}")
        error_text = "Произошла ошибка."
        if update.callback_query:
            await update.callback_query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)
    finally:
        db.close()

async def generate_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерировать QR код пользователя"""
    user_id = update.effective_user.id
    
    # Проверяем регистрацию
    if not await _check_user_registration(user_id, update):
        return
    
    db = get_db()
    user_service = UserService(db)
    
    try:
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            error_text = "Пользователь не найден."
            if update.callback_query:
                await update.callback_query.edit_message_text(error_text)
            else:
                await update.message.reply_text(error_text)
            return
        
        # Показываем сообщение о генерации (для callback)
        loading_message = None
        if update.callback_query:
            loading_message = await update.callback_query.edit_message_text(
                "📱 Генерирую ваш QR код..."
            )
        
        # Логируем процесс генерации
        logger.info(f"Генерация QR-кода для пользователя {db_user.id} (telegram_id: {user_id})")
        
        # Генерируем QR код с дополнительной обработкой ошибок
        try:
            qr_image_bytes = QRService.generate_user_qr(db_user.id, user_id)
            
            if not qr_image_bytes:
                raise ValueError("QR-сервис вернул пустые данные")
            
            if len(qr_image_bytes) < 100:
                raise ValueError(f"QR-код слишком мал: {len(qr_image_bytes)} байт")
                
            logger.info(f"QR-код сгенерирован успешно: {len(qr_image_bytes)} байт")
            
        except Exception as qr_error:
            logger.error(f"Ошибка генерации QR-кода: {qr_error}")
            error_text = "❌ Ошибка при генерации QR-кода. Попробуйте позже."
            if update.callback_query and loading_message:
                try:
                    await loading_message.edit_text(
                        error_text,
                        reply_markup=main_menu_keyboard()
                    )
                except:
                    await update.callback_query.message.reply_text(
                        error_text,
                        reply_markup=main_menu_keyboard()
                    )
            elif update.callback_query:
                await update.callback_query.message.reply_text(
                    error_text,
                    reply_markup=main_menu_keyboard()
                )
            else:
                await update.message.reply_text(error_text)
            return
        
        # Подготавливаем подпись
        caption = (
            f"📱 Ваш QR код для программы лояльности\n\n"
            f"🎁 Баллы: {db_user.points}\n"
            f"📱 ID: {db_user.id}"
        )
        
        # Отправляем QR-код
        success = False
        qr_message = None
        
        # Способ 1: InputFile
        if not success:
            try:
                photo_file = InputFile(qr_image_bytes, filename="qr_code.png")
                if update.callback_query:
                    qr_message = await update.callback_query.message.reply_photo(
                        photo=photo_file,
                        caption=caption
                    )
                else:
                    qr_message = await update.message.reply_photo(
                        photo=photo_file,
                        caption=caption
                    )
                success = True
                logger.info("QR-код отправлен через InputFile")
            except Exception as e:
                logger.warning(f"InputFile не сработал: {e}")
        
        # Способ 2: BytesIO
        if not success:
            try:
                bio = BytesIO(qr_image_bytes)
                bio.name = "qr_code.png"
                if update.callback_query:
                    qr_message = await update.callback_query.message.reply_photo(
                        photo=bio,
                        caption=caption
                    )
                else:
                    qr_message = await update.message.reply_photo(
                        photo=bio,
                        caption=caption
                    )
                success = True
                logger.info("QR-код отправлен через BytesIO")
            except Exception as e:
                logger.warning(f"BytesIO не сработал: {e}")
        
        if success:
            # Отправляем главное меню
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    "🏠 Главное меню\nВыберите действие:",
                    reply_markup=main_menu_keyboard()
                )
            else:
                await update.message.reply_text(
                    "🏠 Главное меню\nВыберите действие:",
                    reply_markup=main_menu_keyboard()
                )
            
            # Удаляем сообщение "Генерирую QR код..."
            if loading_message:
                try:
                    await loading_message.delete()
                except:
                    pass
            
            # Планируем удаление QR кода через 5 минут
            if context.job_queue and qr_message:
                context.job_queue.run_once(
                    delete_qr_job,
                    when=300,
                    data=qr_message
                )
        else:
            # Если ничего не сработало
            logger.error("Все способы отправки QR-кода провалились")
            error_text = (
                "❌ Не удалось отправить QR-код. Проблема с Telegram API.\n\n"
                f"📋 Ваши данные:\n"
                f"🆔 ID: {db_user.id}\n"
                f"🎁 Баллы: {db_user.points}\n\n"
                "Обратитесь в поддержку для получения QR-кода."
            )
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    error_text,
                    reply_markup=main_menu_keyboard()
                )
            else:
                await update.message.reply_text(error_text)
        
    except Exception as e:
        logger.error(f"Ошибка в generate_qr handler: {e}", exc_info=True)
        error_text = "Ошибка при генерации QR кода."
        if update.callback_query:
            await update.callback_query.message.reply_text(
                error_text,
                reply_markup=main_menu_keyboard()
            )
        else:
            await update.message.reply_text(error_text)
    finally:
        db.close()

async def referral_program(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мой реферальный код"""
    user_id = update.effective_user.id
    
    # Проверяем регистрацию
    if not await _check_user_registration(user_id, update):
        return
    
    db = get_db()
    user_service = UserService(db)
    loyalty_service = LoyaltyService(db)
    
    try:
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            await update.message.reply_text("Пользователь не найден.")
            return
        
        stats = loyalty_service.get_user_statistics(db_user.id)
        
        # Формируем текст для кнопки "Поделиться"
        share_text = f"🎁 Приглашаю тебя в программу лояльности! Получи {config.REFERRAL_BONUS} баллов при регистрации по моей реферальной ссылке: https://t.me/{context.bot.username}?start={stats['referral_code']}"
        
        referral_text = f"""🎁 Ваш реферальный код: {stats['referral_code']}

📊 Статистика рефералов:
👥 Приглашено друзей: {stats['referrals_count']}
💰 Заработано на рефералах: {stats['referrals_count'] * config.REFERRAL_BONUS} баллов

💡 Как это работает:
• Поделитесь своим кодом с друзьями
• Когда друг введет ваш код при регистрации:
  - Вы получаете {config.REFERRAL_BONUS} баллов
  - Ваш друг также получает {config.REFERRAL_BONUS} баллов

🔗 Ваша реферальная ссылка:
https://t.me/{context.bot.username}?start={stats['referral_code']}"""
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                referral_text,
                reply_markup=referral_keyboard(share_url=share_text)
            )
        else:
            await update.message.reply_text(
                referral_text,
                reply_markup=referral_keyboard(share_url=share_text)
            )
            
    except Exception as e:
        logger.error(f"Ошибка в referral_program handler: {e}")
        await update.message.reply_text("Произошла ошибка.")
    finally:
        db.close()

async def show_promotions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные акции"""
    db = get_db()
    promotion_service = PromotionService(db)
    
    try:
        promotions = promotion_service.get_active_promotions()
        
        if not promotions:
            promo_text = "🎯 Активных акций пока нет.\nСледите за обновлениями!"
            keyboard = back_keyboard()
        else:
            promo_text = "🎯 Активные акции:\n\n"
            for promo in promotions:
                promo_text += f"• {promo.title}\n{promo.description}\n\n"
            keyboard = promotions_keyboard(promotions)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                promo_text,
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                promo_text,
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Ошибка в show_promotions handler: {e}")
        await update.message.reply_text("Произошла ошибка.")
    finally:
        db.close()

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику пользователя"""
    user_id = update.effective_user.id
    db = get_db()
    user_service = UserService(db)
    loyalty_service = LoyaltyService(db)
    
    try:
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            await update.message.reply_text("Пользователь не найден.")
            return
        
        stats = loyalty_service.get_user_statistics(db_user.id)
        history = loyalty_service.get_points_history(db_user.id, 5)
        
        stats_text = f"""
📊 Ваша статистика:

🎁 Текущие баллы: {stats['points']}
💰 Потрачено всего: {stats['total_spent']:.2f}₽
🛒 Покупок совершено: {stats['purchases_count']}
👥 Приглашено друзей: {stats['referrals_count']}
📅 Дата регистрации: {stats['registration_date'].strftime('%d.%m.%Y')}

📈 Последние операции:
        """
        
        for transaction in history:
            emoji = "➕" if transaction.points_change > 0 else "➖"
            stats_text += f"{emoji} {abs(transaction.points_change)} баллов - {transaction.description}\n"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                stats_text,
                reply_markup=back_keyboard()
            )
        else:
            await update.message.reply_text(
                stats_text,
                reply_markup=back_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Ошибка в show_statistics handler: {e}")
        await update.message.reply_text("Произошла ошибка.")
    finally:
        db.close()

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поддержка"""
    support_text = """
📞 Служба поддержки

По всем вопросам обращайтесь:
📍 Адрес: г. Феодосия, ул. Земская 8
⏰ Время работы: 9:00-20:00
    """
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            support_text,
            reply_markup=back_keyboard()
        )
    else:
        await update.message.reply_text(
            support_text,
            reply_markup=back_keyboard()
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    help_text = """
ℹ️ Справка по боту

🎁 Программа лояльности позволяет:
• Накапливать баллы за покупки
• Получать бонусы за приглашение друзей
• Участвовать в акциях и получать скидки
• Отслеживать свою статистику

💳 Основные команды:
• Мой профиль - информация о вас
• Мои баллы - текущий баланс и история
• QR код - ваш персональный QR код
• Статистика - подробная статистика
• Акции - текущие предложения
• Реферальная программа - приглашайте друзей

📱 Как пользоваться:
1. Показывайте QR код при покупке
2. Баллы начисляются автоматически
3. Приглашайте друзей по реферальной ссылке
4. Участвуйте в акциях для получения бонусов

Нужна помощь? Обращайтесь в поддержку!
    """
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            help_text,
            reply_markup=back_keyboard()
        )
    else:
        await update.message.reply_text(
            help_text,
            reply_markup=back_keyboard()
        )

# Обработчики callback запросов
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "back_to_menu":
        try:
            # Пытаемся редактировать сообщение (работает для текстовых)
            await query.edit_message_text(
                "🏠 Главное меню\nВыберите действие:",
                reply_markup=main_menu_keyboard()
            )
        except Exception as e:
            # Если не получается редактировать (например, сообщение с фото),
            # отправляем новое сообщение
            await query.message.reply_text(
                "🏠 Главное меню\nВыберите действие:",
                reply_markup=main_menu_keyboard()
            )
    # Обработчики кнопок главного меню
    elif data == "profile":
        await profile_callback(update, context)
    elif data == "my_points":
        await my_points_callback(update, context)
    elif data == "generate_qr":
        await generate_qr_callback(update, context)
    elif data == "statistics":
        await show_statistics_callback(update, context)
    elif data == "promotions":
        await show_promotions_callback(update, context)
    elif data == "referral_program":
        await referral_program_callback(update, context)
    elif data == "support":
        await support_callback(update, context)
    elif data == "help":
        await help_callback(update, context)
    # Существующие обработчики
    elif data == "points_history":
        await show_points_history(update, context)
    elif data == "share_referral":
        await share_referral_link(update, context)
    elif data == "my_referrals":
        await show_my_referrals(update, context)
    elif data == "referral_top":
        await show_referral_top(update, context)
    elif data == "giveaway":
        await show_giveaway(update, context)
    elif data.startswith("giveaway_join_"):
        giveaway_id = int(data.split("_")[-1])
        await join_giveaway(update, context, giveaway_id=giveaway_id)
    elif data.startswith("giveaway_top_"):
        giveaway_id = int(data.split("_")[-1])
        await show_giveaway_top(update, context, giveaway_id=giveaway_id)
    elif data.startswith("giveaway_mypos_"):
        giveaway_id = int(data.split("_")[-1])
        await show_giveaway_my_position(update, context, giveaway_id=giveaway_id)
    elif data.startswith("giveaway_status_"):
        await show_giveaway(update, context)


async def show_points_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать историю баллов"""
    user_id = update.effective_user.id
    db = get_db()
    user_service = UserService(db)
    loyalty_service = LoyaltyService(db)
    
    try:
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            await query.message.reply_text("Пользователь не найден.")
            return
        
        history = loyalty_service.get_points_history(db_user.id, 10)
        
        history_text = "📈 История операций с баллами:\n\n"
        
        if not history:
            history_text += "Операций пока не было."
        else:
            for transaction in history:
                emoji = "➕" if transaction.points_change > 0 else "➖"
                date_str = transaction.created_date.strftime('%d.%m.%Y %H:%M')
                history_text += f"{emoji} {abs(transaction.points_change)} баллов\n"
                history_text += f"   {transaction.description}\n"
                history_text += f"   {date_str}\n\n"
        
        await update.callback_query.edit_message_text(
            history_text,
            reply_markup=back_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в show_points_history: {e}")
        await update.callback_query.edit_message_text("Произошла ошибка.")
    finally:
        db.close()

async def share_referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поделиться реферальной ссылкой"""
    user_id = update.effective_user.id
    db = get_db()
    user_service = UserService(db)
    
    try:
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            await query.message.reply_text("Пользователь не найден.")
            return
        
        share_text = f"""
🎁 Приглашайте друзей и получайте бонусы!

Поделитесь этой ссылкой с друзьями:
https://t.me/{context.bot.username}?start={db_user.referral_code}

За каждого приглашенного друга вы получите {config.REFERRAL_BONUS} баллов!
        """
        
        await update.callback_query.edit_message_text(
            share_text,
            reply_markup=back_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в share_referral_link: {e}")
        await update.callback_query.edit_message_text("Произошла ошибка.")
    finally:
        db.close()

async def show_my_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать моих рефералов"""
    user_id = update.effective_user.id
    db = get_db()
    user_service = UserService(db)
    loyalty_service = LoyaltyService(db)
    
    try:
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            await update.callback_query.message.reply_text("Пользователь не найден.")
            return
        
        referrals = user_service.get_user_referrals(db_user.id)
        
        if not referrals:
            referrals_text = "👥 У вас пока нет приглашенных друзей.\n\nПоделитесь своим реферальным кодом!"
        else:
            referrals_text = f"👥 Ваши приглашенные друзья ({len(referrals)}):\n\n"
            for i, referral in enumerate(referrals, 1):
                reg_date = referral.registration_date.strftime('%d.%m.%Y')
                referrals_text += f"{i}. {referral.first_name} {referral.last_name}\n"
                referrals_text += f"   Регистрация: {reg_date}\n\n"
        
        await update.callback_query.edit_message_text(
            referrals_text,
            reply_markup=back_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в show_my_referrals: {e}")
        await update.callback_query.message.reply_text("Произошла ошибка.")
    finally:
        db.close()

async def show_referral_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать топ рефералов"""
    user_id = update.effective_user.id
    
    # Проверяем регистрацию
    if not await _check_user_registration(user_id, update):
        return
    
    db = get_db()
    user_service = UserService(db)
    loyalty_service = LoyaltyService(db)
    
    try:
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            await update.callback_query.message.reply_text("Пользователь не найден.")
            return
        
        # Получаем топ 10 рефералов
        top_referrals = loyalty_service.get_referral_top(limit=10)
        
        # Получаем позицию текущего пользователя
        user_position = loyalty_service.get_user_referral_position(db_user.id)
        
        if not top_referrals:
            top_text = "🏆 Топ рефералов\n\n"
            top_text += "Пока нет пользователей с приглашенными друзьями.\n"
            top_text += "Станьте первым!"
            
            await update.callback_query.edit_message_text(
                top_text,
                reply_markup=referral_keyboard()
            )
            return
        
        # Формируем текст с топом
        top_text = "🏆 Топ рефералов\n\n"
        
        # Добавляем позицию пользователя
        if user_position:
            top_text += f"📍 Ваша позиция: {user_position['position']}\n"
            top_text += f"👥 Приглашено друзей: {user_position['referrals_count']}\n\n"
        
        top_text += "🥇 Лучшие рефералы:\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        for idx, item in enumerate(top_referrals, 1):
            medal = medals[idx - 1] if idx <= 3 else f"{idx}."
            
            # Определяем имя пользователя
            name = f"{item['first_name'] or ''} {item['last_name'] or ''}".strip()
            if not name:
                name = "Пользователь"
            
            # Выделяем текущего пользователя
            is_current = item['user_id'] == db_user.id
            current_mark = " 👈 Вы" if is_current else ""
            
            friends_text = 'друг' if item['referrals_count'] == 1 else ('друга' if item['referrals_count'] < 5 else 'друзей')
            
            top_text += f"{medal} {name}{current_mark}\n"
            top_text += f"   👥 {item['referrals_count']} {friends_text}\n"
            top_text += f"   ⭐ {item['points']} баллов\n\n"
        
        await update.callback_query.edit_message_text(
            top_text,
            reply_markup=referral_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в show_referral_top: {e}", exc_info=True)
        await update.callback_query.message.reply_text("Произошла ошибка при загрузке топа рефералов.")
    finally:
        db.close()


async def show_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать текущий розыгрыш"""
    tg_id = update.effective_user.id
    if not await _check_user_registration(tg_id, update):
        return

    db = get_db()
    user_service = UserService(db)
    loyalty_service = LoyaltyService(db)

    try:
        db_user = user_service.get_user_by_telegram_id(tg_id)
        if not db_user:
            await update.callback_query.message.reply_text("Пользователь не найден.")
            return

        giveaway = loyalty_service.get_active_giveaway()
        if not giveaway:
            await update.callback_query.edit_message_text(
                "🎉 Розыгрыш\n\nСейчас нет активного розыгрыша.",
                reply_markup=back_keyboard()
            )
            return

        from database import GiveawayParticipant
        is_participant = db.query(GiveawayParticipant).filter(
            GiveawayParticipant.giveaway_id == giveaway.id,
            GiveawayParticipant.user_id == db_user.id
        ).first() is not None

        ends = giveaway.end_date.strftime('%d.%m.%Y %H:%M') if giveaway.end_date else "—"
        text = f"🎉 Розыгрыш: {giveaway.title}\n\n"
        if giveaway.description:
            text += f"{giveaway.description}\n\n"
        text += f"⏳ До конца: {ends}\n\n"
        text += "🏆 Побеждает участник, который пригласит больше всего друзей по реферальной ссылке в период розыгрыша."

        await update.callback_query.edit_message_text(
            text,
            reply_markup=giveaway_keyboard(giveaway.id, is_participant=is_participant)
        )

    except Exception as e:
        logger.error(f"Ошибка в show_giveaway: {e}", exc_info=True)
        await update.callback_query.edit_message_text("Произошла ошибка.", reply_markup=back_keyboard())
    finally:
        db.close()


async def join_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE, giveaway_id: int):
    """Вступить в розыгрыш"""
    tg_id = update.effective_user.id
    if not await _check_user_registration(tg_id, update):
        return

    db = get_db()
    user_service = UserService(db)
    loyalty_service = LoyaltyService(db)

    try:
        db_user = user_service.get_user_by_telegram_id(tg_id)
        if not db_user:
            await update.callback_query.message.reply_text("Пользователь не найден.")
            return

        giveaway = loyalty_service.get_active_giveaway()
        if not giveaway or giveaway.id != giveaway_id:
            await update.callback_query.edit_message_text(
                "Розыгрыш не найден или уже завершён.",
                reply_markup=back_keyboard()
            )
            return

        _, msg = loyalty_service.join_active_giveaway(db_user.id)
        await update.callback_query.edit_message_text(
            msg,
            reply_markup=giveaway_keyboard(giveaway.id, is_participant=True)
        )

    except Exception as e:
        logger.error(f"Ошибка в join_giveaway: {e}", exc_info=True)
        await update.callback_query.edit_message_text("Произошла ошибка.", reply_markup=back_keyboard())
    finally:
        db.close()


async def show_giveaway_top(update: Update, context: ContextTypes.DEFAULT_TYPE, giveaway_id: int):
    """Топ розыгрыша (рефералы за период розыгрыша)"""
    tg_id = update.effective_user.id
    if not await _check_user_registration(tg_id, update):
        return

    db = get_db()
    user_service = UserService(db)
    loyalty_service = LoyaltyService(db)

    try:
        db_user = user_service.get_user_by_telegram_id(tg_id)
        if not db_user:
            await update.callback_query.message.reply_text("Пользователь не найден.")
            return

        top = loyalty_service.get_giveaway_top(giveaway_id, limit=10)
        pos = loyalty_service.get_giveaway_user_position(giveaway_id, db_user.id)

        text = "🏆 Топ розыгрыша\n\n"
        if pos:
            text += f"📍 Ваша позиция: {pos['position']}\n"
            text += f"👥 Приглашено друзей: {pos['referrals_count']}\n\n"

        if not top:
            text += "Пока нет участников/приглашений.\nНажмите «✅ Участвую» и пригласите друзей!"
            await update.callback_query.edit_message_text(text, reply_markup=giveaway_keyboard(giveaway_id, is_participant=bool(pos)))
            return

        medals = ["🥇", "🥈", "🥉"]
        for idx, item in enumerate(top, 1):
            medal = medals[idx - 1] if idx <= 3 else f"{idx}."
            name = f"{item.get('first_name') or ''} {item.get('last_name') or ''}".strip() or "Пользователь"
            current_mark = " 👈 Вы" if item["user_id"] == db_user.id else ""
            text += f"{medal} {name}{current_mark}\n"
            text += f"   👥 {item['referrals_count']} приглашений\n\n"

        await update.callback_query.edit_message_text(text, reply_markup=giveaway_keyboard(giveaway_id, is_participant=bool(pos)))

    except Exception as e:
        logger.error(f"Ошибка в show_giveaway_top: {e}", exc_info=True)
        await update.callback_query.edit_message_text("Произошла ошибка.", reply_markup=back_keyboard())
    finally:
        db.close()


async def show_giveaway_my_position(update: Update, context: ContextTypes.DEFAULT_TYPE, giveaway_id: int):
    tg_id = update.effective_user.id
    if not await _check_user_registration(tg_id, update):
        return

    db = get_db()
    user_service = UserService(db)
    loyalty_service = LoyaltyService(db)

    try:
        db_user = user_service.get_user_by_telegram_id(tg_id)
        if not db_user:
            await update.callback_query.message.reply_text("Пользователь не найден.")
            return

        pos = loyalty_service.get_giveaway_user_position(giveaway_id, db_user.id)
        if not pos:
            await update.callback_query.edit_message_text(
                "Вы пока не участвуете в розыгрыше. Нажмите «✅ Участвую».",
                reply_markup=giveaway_keyboard(giveaway_id, is_participant=False)
            )
            return

        text = "📍 Моя позиция в розыгрыше\n\n"
        text += f"Место: {pos['position']}\n"
        text += f"Приглашено друзей (за период): {pos['referrals_count']}\n"
        await update.callback_query.edit_message_text(text, reply_markup=giveaway_keyboard(giveaway_id, is_participant=True))

    except Exception as e:
        logger.error(f"Ошибка в show_giveaway_my_position: {e}", exc_info=True)
        await update.callback_query.edit_message_text("Произошла ошибка.", reply_markup=back_keyboard())
    finally:
        db.close()

# Callback обработчики для главного меню
async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для профиля"""
    query = update.callback_query
    # Вызываем существующую функцию profile, адаптируя её для callback
    context.user_data['is_callback'] = True
    await profile(update, context)

async def my_points_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для моих баллов"""
    query = update.callback_query
    context.user_data['is_callback'] = True
    await my_points(update, context)

async def generate_qr_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для QR кода"""
    query = update.callback_query
    context.user_data['is_callback'] = True
    await generate_qr(update, context)

async def show_statistics_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для статистики"""
    query = update.callback_query
    context.user_data['is_callback'] = True
    await show_statistics(update, context)

async def show_promotions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для акций"""
    query = update.callback_query
    context.user_data['is_callback'] = True
    await show_promotions(update, context)

async def referral_program_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для реферальной программы"""
    query = update.callback_query
    context.user_data['is_callback'] = True
    await referral_program(update, context)

async def support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для поддержки"""
    query = update.callback_query
    context.user_data['is_callback'] = True
    await support(update, context)

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для помощи"""
    query = update.callback_query
    context.user_data['is_callback'] = True
    await help_command(update, context)

# Обработчик текстовых сообщений
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    
    # Поскольку теперь используются только инлайн кнопки, 
    # предлагаем пользователю использовать команду /start для получения меню
    await update.message.reply_text(
        "Для использования бота используйте команду /start для получения меню с кнопками.",
        reply_markup=main_menu_keyboard()
    ) 
