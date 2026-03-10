import logging
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from database import get_db, User, Purchase, PointsHistory
from services import UserService, LoyaltyService
import config

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, bot_application):
        self.bot = bot_application.bot
        
    async def send_inactivity_notifications(self, days_threshold=20, send_to_all=False):
        db = get_db()
        try:
            threshold_date = datetime.now() - timedelta(days=days_threshold)
            
            if send_to_all:
                logger.info("Запуск рассылки для ВСЕХ активных пользователей")
                target_users = db.query(User).filter(User.is_active == True).all()
            else:
                logger.info(f"Поиск неактивных пользователей с {threshold_date.strftime('%d.%m.%Y')}")
                # Первичный фильтр: активные пользователи, зарегистрированные более days_threshold назад
                potential_inactive = db.query(User).filter(
                    and_(
                        User.is_active == True,
                        User.registration_date < threshold_date
                    )
                ).all()
                
                target_users = []
                for user in potential_inactive:
                    if await self._is_user_inactive(db, user, threshold_date):
                        target_users.append(user)
            
            notifications_sent = 0
            logger.info(f"Начинаю отправку для {len(target_users)} пользователей")
            
            for user in target_users:
                if await self._send_reminder_notification(user):
                    notifications_sent += 1
                    await asyncio.sleep(0.5)  # Небольшая задержка, чтобы не спамить
            
            logger.info(f"Рассылка завершена. Отправлено уведомлений: {notifications_sent}")
            return notifications_sent
            
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомлений: {e}")
            return 0
        finally:
            db.close()
    
    async def _is_user_inactive(self, db, user: User, threshold_date: datetime) -> bool:
        try:
            recent_purchases = db.query(Purchase).filter(
                and_(
                    Purchase.user_id == user.id,
                    Purchase.purchase_date > threshold_date
                )
            ).first()
            
            recent_redemptions = db.query(PointsHistory).filter(
                and_(
                    PointsHistory.user_id == user.id,
                    PointsHistory.transaction_type == 'redemption',
                    PointsHistory.created_date > threshold_date
                )
            ).first()
            
            return not recent_purchases and not recent_redemptions
            
        except Exception as e:
            logger.error(f"Ошибка проверки активности пользователя {user.id}: {e}")
            return False
    
    async def _send_reminder_notification(self, user: User) -> bool:
        try:
            message = f"""
🛍️ Мы скучаем по тебе, {user.first_name or 'дорогой покупатель'}!

💔 Мы заметили, что ты давно не заходил в наш магазин.
🎁 У тебя есть {user.points} баллов, которые можно потратить!

🔥 Не упусти выгодные предложения:
• Используй накопленные баллы для скидок
• Получай новые баллы за каждую покупку
• Приглашай друзей и получай бонусы

💡 Твой реферальный код: {user.referral_code}

⭐ Возвращайся скорее - тебя ждут приятные сюрпризы!
            """
            
            await self.bot.send_message(
                chat_id=user.telegram_id,
                text=message.strip()
            )
            
            logger.info(f"Напоминание отправлено пользователю {user.id} ({user.telegram_id})")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания пользователю {user.id}: {e}")
            return False

async def setup_notifications(application):
    try:
        notification_service = NotificationService(application)
        
        async def send_weekly_notifications():
            logger.info("🔔 Фоновая задача уведомлений Пятница 12:00 запущена")
            notification_triggered = False
            
            while True:
                try:
                    current_time = datetime.now()
                    
                    # Проверяем расписание (Пятница 12:00 по умолчанию)
                    if (current_time.weekday() == config.NOTIFICATION_WEEKDAY and 
                        current_time.hour == config.NOTIFICATION_HOUR and 
                        current_time.minute == config.NOTIFICATION_MINUTE and
                        not notification_triggered):
                        
                        logger.info(f"🔔 ЗАПУСК ПЛАНОВОЙ РАССЫЛКИ (день {current_time.weekday()}, время {current_time.hour:02d}:{current_time.minute:02d})")
                        
                        # "всем пользователям" как просил USER. 
                        # Если нужно только неактивным, убрать send_to_all=True
                        await notification_service.send_inactivity_notifications(config.INACTIVITY_DAYS_THRESHOLD, send_to_all=True)
                        
                        notification_triggered = True
                        logger.info("✅ Плановая рассылка завершена")
                    
                    # Сброс флага
                    if current_time.minute != config.NOTIFICATION_MINUTE:
                        notification_triggered = False
                    
                    await asyncio.sleep(30) # Проверяем чаще для надежности
                    
                except Exception as e:
                    logger.error(f"Ошибка в цикле уведомлений: {e}")
                    await asyncio.sleep(60)
        
        async def check_expired_points():
            logger.info("📅 Фоновая задача проверки сгорания баллов запущена")
            while True:
                try:
                    db = get_db()
                    loyalty_service = LoyaltyService(db)
                    processed = loyalty_service.process_expired_points()
                    if processed > 0:
                        logger.info(f"🔥 Автоматически списано просроченных начислений: {processed}")
                    db.close()
                    # Проверяем каждый час
                    await asyncio.sleep(3600)
                except Exception as e:
                    logger.error(f"Ошибка в задаче сгорания баллов: {e}")
                    await asyncio.sleep(600)

        asyncio.create_task(send_weekly_notifications())
        asyncio.create_task(check_expired_points())
        
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        weekday_name = weekday_names[config.NOTIFICATION_WEEKDAY]
        logger.info(f"Служба еженедельных уведомлений готова: {weekday_name} в {config.NOTIFICATION_HOUR:02d}:{config.NOTIFICATION_MINUTE:02d}")
        
    except Exception as e:
        logger.error(f"Ошибка настройки уведомлений: {e}")

async def send_manual_inactivity_check(application, days_threshold=20):
    try:
        notification_service = NotificationService(application)
        # При ручном запуске из админки оставляем логику только для неактивных пользователей
        return await notification_service.send_inactivity_notifications(days_threshold, send_to_all=False)
    except Exception as e:
        logger.error(f"Ошибка ручной проверки неактивности: {e}")
        return 0

async def get_inactive_users_count(days_threshold=20):
    try:
        db = get_db()
        threshold_date = datetime.now() - timedelta(days=days_threshold)
        
        inactive_users = db.query(User).filter(
            and_(
                User.is_active == True,
                User.registration_date < threshold_date
            )
        ).all()
        
        inactive_count = 0
        for user in inactive_users:
            recent_purchases = db.query(Purchase).filter(
                and_(
                    Purchase.user_id == user.id,
                    Purchase.purchase_date > threshold_date
                )
            ).first()
            
            recent_redemptions = db.query(PointsHistory).filter(
                and_(
                    PointsHistory.user_id == user.id,
                    PointsHistory.transaction_type == 'redemption',
                    PointsHistory.created_date > threshold_date
                )
            ).first()
            
            if not recent_purchases and not recent_redemptions:
                inactive_count += 1
        
        db.close()
        return inactive_count
        
    except Exception as e:
        logger.error(f"Ошибка подсчета неактивных пользователей: {e}")
        return 0

class BroadcastService:
    def __init__(self, bot):
        self.bot = bot
    
    async def send_broadcast_message(self, message: str, target_users=None):
        try:
            db = get_db()
            
            if target_users is None:
                users = db.query(User).filter(User.is_active == True).all()
            else:
                users = target_users
            
            successful = 0
            failed = 0
            
            for user in users:
                try:
                    await self.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message
                    )
                    successful += 1
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Ошибка отправки сообщения пользователю {user.id}: {e}")
                    failed += 1
            
            db.close()
            
            logger.info(f"Рассылка завершена: {successful} успешно, {failed} ошибок")
            return successful, failed
            
        except Exception as e:
            logger.error(f"Ошибка рассылки: {e}")
            return 0, 0

async def send_promotion_notification(bot, promotion_title: str, promotion_description: str, discount_percent: int = None):
    """Отправка уведомления о новой акции всем пользователям"""
    try:
        db = get_db()
        
        # Получаем всех активных пользователей
        users = db.query(User).filter(User.is_active == True).all()
        
        # Формируем сообщение о новой акции
        discount_text = f"💰 Скидка: {discount_percent}%" if discount_percent and discount_percent > 0 else ""
        
        message = f"""
🎉 Новая акция в нашем магазине!

🎯 {promotion_title}

📝 {promotion_description}

{discount_text}

🛍️ Не упустите возможность сэкономить!
⏰ Торопитесь - количество товаров ограничено!

💎 Используйте свои накопленные баллы для дополнительной скидки!
        """
        
        successful = 0
        failed = 0
        
        logger.info(f"Начинаю отправку уведомлений о новой акции '{promotion_title}' для {len(users)} пользователей")
        
        for user in users:
            try:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=message.strip()
                )
                successful += 1
                # Небольшая задержка между отправками, чтобы избежать ограничений Telegram
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления о акции пользователю {user.id}: {e}")
                failed += 1
        
        db.close()
        
        logger.info(f"Уведомления о акции отправлены: {successful} успешно, {failed} ошибок")
        return successful, failed
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомлений о акции: {e}")
        return 0, 0

async def send_welcome_back_bonus(user_id: int, bot):
    try:
        db = get_db()
        loyalty_service = LoyaltyService(db)
        user_service = UserService(db)
        
        user = user_service.get_user_by_telegram_id(user_id)
        if not user:
            return False
        
        success = loyalty_service.add_bonus_points(
            user.id,
            config.WELCOME_BACK_BONUS,
            "Бонус за возвращение"
        )
        
        if success:
            message = f"""
🎉 Добро пожаловать обратно!

💝 Мы соскучились и начислили тебе {config.WELCOME_BACK_BONUS} бонусных баллов!
🏆 Твой баланс: {user.points + config.WELCOME_BACK_BONUS} баллов

Продолжай делать покупки и копить баллы! 
            """
            
            await bot.send_message(
                chat_id=user.telegram_id,
                text=message.strip()
            )
            
            logger.info(f"Бонус за возвращение отправлен пользователю {user.id}")
            return True
        
        db.close()
        return False
        
    except Exception as e:
        logger.error(f"Ошибка отправки бонуса за возвращение: {e}")
        return False

async def send_promotion_notification_with_media(bot, promotion_title: str, promotion_description: str, discount_percent: int = None, media_info: dict = None):
    """Отправка уведомления о новой акции с поддержкой медиафайлов"""
    try:
        db = get_db()
        users = db.query(User).filter(User.is_active == True).all()
        
        successful = 0
        failed = 0
        
        # Формируем текст уведомления
        discount_text = f"💰 Скидка: {discount_percent}%" if discount_percent and discount_percent > 0 else ""
        
        notification_text = f"""
🎉 Новая акция в нашем магазине!

🎯 {promotion_title}

📝 {promotion_description}

{discount_text}

🛍️ Не упустите возможность сэкономить!
⏰ Торопитесь - количество товаров ограничено!

💎 Используйте свои накопленные баллы для дополнительной скидки!
        """.strip()
        
        logger.info(f"Начинаю отправку уведомлений о новой акции '{promotion_title}' для {len(users)} пользователей")
        
        for user in users:
            try:
                if media_info:
                    # Отправляем сообщение с медиафайлом
                    if media_info['type'] == 'photo':
                        await bot.send_photo(
                            chat_id=user.telegram_id,
                            photo=media_info['file_id'],
                            caption=notification_text
                        )
                    elif media_info['type'] == 'video':
                        await bot.send_video(
                            chat_id=user.telegram_id,
                            video=media_info['file_id'],
                            caption=notification_text
                        )
                    elif media_info['type'] == 'document':
                        await bot.send_document(
                            chat_id=user.telegram_id,
                            document=media_info['file_id'],
                            caption=notification_text
                        )
                else:
                    # Отправляем обычное текстовое сообщение
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=notification_text
                    )
                
                successful += 1
                # Небольшая задержка между отправками
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление пользователю {user.telegram_id}: {e}")
                failed += 1
        
        logger.info(f"Уведомления о акции отправлены: {successful} успешно, {failed} ошибок")
        db.close()
        return successful, failed
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений о акции: {e}")
        return 0, 0 