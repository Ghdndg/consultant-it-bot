#!/usr/bin/env python3

import logging
import asyncio
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, 
    ConversationHandler, filters
)
from telegram import BotCommand

from handlers import (
    start, profile, my_points, generate_qr, referral_program, 
    show_promotions, show_statistics, support, help_command,
    button_callback, handle_text, handle_first_name, handle_last_name,
    handle_birth_date, handle_phone, handle_referral_code, handle_gender,
    WAITING_FIRST_NAME, WAITING_LAST_NAME, WAITING_BIRTH_DATE, WAITING_GENDER,
    WAITING_PHONE, WAITING_REFERRAL_CODE
)
from admin_handlers import (
    admin_panel, admin_stats, admin_create_promotion_start,
    admin_create_promotion_title, admin_create_promotion_description, admin_create_promotion_media,
    admin_create_promotion_discount, admin_broadcast_start, admin_broadcast_message, admin_broadcast_media,
    admin_manage_promotions, admin_delete_promotion_confirm, admin_confirm_delete_promotion,
    cancel_admin_action, ADMIN_PROMO_TITLE, ADMIN_PROMO_DESCRIPTION, ADMIN_PROMO_MEDIA,
    ADMIN_PROMO_DISCOUNT, ADMIN_BROADCAST_MESSAGE, ADMIN_BROADCAST_MEDIA, ADMIN_DELETE_PROMO_CONFIRM,
    admin_notifications_menu, admin_send_notifications_now, admin_inactive_stats,
    admin_notification_settings, back_to_admin_menu, toggle_notifications,
    edit_inactivity_days_start, edit_inactivity_days_value, 
    edit_welcome_bonus_start, edit_welcome_bonus_value,
    edit_birthday_bonus_start, edit_birthday_bonus_value,
    edit_points_per_purchase_start, edit_points_per_purchase_value,
    edit_bonus_threshold_start, edit_bonus_threshold_value,
    edit_bonus_amount_start, edit_bonus_amount_value,
    edit_referral_bonus_start, edit_referral_bonus_value,
    edit_notification_weekday_start, edit_notification_weekday_value,
    edit_notification_time_start, edit_notification_hour_value, edit_notification_minute_value,
    ADMIN_EDIT_INACTIVITY_DAYS, ADMIN_EDIT_WELCOME_BONUS, ADMIN_EDIT_BIRTHDAY_BONUS,
    ADMIN_EDIT_POINTS_PER_PURCHASE, ADMIN_EDIT_BONUS_THRESHOLD, ADMIN_EDIT_BONUS_AMOUNT,
    ADMIN_EDIT_REFERRAL_BONUS, ADMIN_EDIT_NOTIFICATION_WEEKDAY, ADMIN_EDIT_NOTIFICATION_HOUR,
    ADMIN_EDIT_NOTIFICATION_MINUTE,
    admin_charts_menu, admin_chart_monthly_stats, admin_chart_points,
    admin_giveaway_menu,
    admin_giveaway_broadcast, admin_giveaway_stop, admin_giveaway_top, admin_giveaway_notify_participants,
    admin_gift_menu, admin_gift_manage, admin_gift_delete_confirm,
    admin_gift_points_start, admin_gift_points_amount, admin_gift_points_days,
    admin_gift_points_description, admin_gift_points_gender, admin_gift_points_finish,
    ADMIN_GIFT_AMOUNT, ADMIN_GIFT_DAYS, ADMIN_GIFT_DESCRIPTION, ADMIN_GIFT_GENDER
)

import config
from database import create_tables, safe_migrate

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO if config.DEBUG else logging.WARNING
)
logger = logging.getLogger(__name__)

async def post_init(application):
    try:
        safe_migrate()   # Безопасно добавляем новые колонки в существующую БД
        create_tables()  # Создаём новые таблицы если их нет
        logger.info("База данных инициализирована")
        
        if config.ENABLE_NOTIFICATIONS:
            try:
                from notifications import setup_notifications
                await setup_notifications(application)
                logger.info("Система уведомлений запущена")
            except Exception as e:
                logger.error(f"Ошибка запуска системы уведомлений: {e}")
        
        commands = [
            BotCommand("start", "Начать работу с ботом"),
            BotCommand("profile", "Мой профиль"),
            BotCommand("points", "Мои баллы"),
            BotCommand("qr", "Мой QR код"),
            BotCommand("stats", "Статистика"),
            BotCommand("promotions", "Активные акции"),
            BotCommand("referral", "Реферальная программа"),
            BotCommand("support", "Поддержка"),
            BotCommand("help", "Справка"),
            BotCommand("admin", "Админ панель (только для администраторов)")
        ]
        
        await application.bot.set_my_commands(commands)
        logger.info("Команды бота установлены")
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации: {e}")

def main():
    
    if config.BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.error("❌ Не установлен токен бота! Проверьте файл config.py или переменные окружения.")
        print("❌ Не установлен токен бота!")
        print("📝 Чтобы запустить бота:")
        print("1. Создайте бота через @BotFather в Telegram")
        print("2. Получите токен")
        print("3. Создайте файл .env и добавьте:")
        print("   BOT_TOKEN=ваш_токен_бота")
        print("   ADMIN_USER_ID=ваш_telegram_id")
        return
    
    application = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()
    
    # application.add_handler(CommandHandler("start", start))  # Удаляем, теперь обрабатывается через ConversationHandler
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("points", my_points))
    application.add_handler(CommandHandler("qr", generate_qr))
    application.add_handler(CommandHandler("stats", show_statistics))
    application.add_handler(CommandHandler("promotions", show_promotions))
    application.add_handler(CommandHandler("referral", referral_program))
    application.add_handler(CommandHandler("support", support))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_panel))
    
    # ConversationHandler для регистрации пользователей
    registration_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_first_name)],
            WAITING_LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_last_name)],
            WAITING_BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_birth_date)],
            WAITING_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_gender)],
            WAITING_PHONE: [
                MessageHandler(filters.CONTACT, handle_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone)
            ],
            WAITING_REFERRAL_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_referral_code)]
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False
    )
    
    application.add_handler(registration_handler)
    

    
    create_promotion_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_create_promotion_start, pattern="^admin_create_promotion$")],
        states={
            ADMIN_PROMO_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_promotion_title)],
            ADMIN_PROMO_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_promotion_description)],
            ADMIN_PROMO_MEDIA: [
                CallbackQueryHandler(admin_create_promotion_media, pattern="^(add_media|skip_media|cancel_admin)$"),
                MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, admin_create_promotion_media)
            ],
            ADMIN_PROMO_DISCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_promotion_discount)]
        },
        fallbacks=[CallbackQueryHandler(cancel_admin_action, pattern="^cancel$")]
    )
    
    broadcast_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern="^admin_broadcast$")],
        states={
            ADMIN_BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_message)],
            ADMIN_BROADCAST_MEDIA: [
                CallbackQueryHandler(admin_broadcast_media, pattern="^(add_media|skip_media|cancel_admin)$"),
                MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, admin_broadcast_media)
            ]
        },
        fallbacks=[CallbackQueryHandler(cancel_admin_action, pattern="^cancel$")]
    )
    
    # ConversationHandler для настроек
    settings_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(edit_inactivity_days_start, pattern="^edit_inactivity_days$"),
            CallbackQueryHandler(edit_welcome_bonus_start, pattern="^edit_welcome_bonus$"),
            CallbackQueryHandler(edit_birthday_bonus_start, pattern="^edit_birthday_bonus$"),
            CallbackQueryHandler(edit_points_per_purchase_start, pattern="^edit_points_per_purchase$"),
            CallbackQueryHandler(edit_bonus_threshold_start, pattern="^edit_bonus_threshold$"),
            CallbackQueryHandler(edit_bonus_amount_start, pattern="^edit_bonus_amount$"),
            CallbackQueryHandler(edit_referral_bonus_start, pattern="^edit_referral_bonus$"),
            CallbackQueryHandler(edit_notification_weekday_start, pattern="^edit_notification_weekday$"),
            CallbackQueryHandler(edit_notification_time_start, pattern="^edit_notification_time$")
        ],
        states={
            ADMIN_EDIT_INACTIVITY_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_inactivity_days_value)],
            ADMIN_EDIT_WELCOME_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_welcome_bonus_value)],
            ADMIN_EDIT_BIRTHDAY_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_birthday_bonus_value)],
            ADMIN_EDIT_POINTS_PER_PURCHASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_points_per_purchase_value)],
            ADMIN_EDIT_BONUS_THRESHOLD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_bonus_threshold_value)],
            ADMIN_EDIT_BONUS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_bonus_amount_value)],
            ADMIN_EDIT_REFERRAL_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_referral_bonus_value)],
            ADMIN_EDIT_NOTIFICATION_WEEKDAY: [CallbackQueryHandler(edit_notification_weekday_value, pattern="^(weekday_\d+|admin_notification_settings)$")],
            ADMIN_EDIT_NOTIFICATION_HOUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_notification_hour_value)],
            ADMIN_EDIT_NOTIFICATION_MINUTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_notification_minute_value)]
        },
        fallbacks=[CallbackQueryHandler(cancel_admin_action, pattern="^cancel$")]
    )
    
    gift_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_gift_points_start, pattern="^admin_gift_points_start$")],
        states={
            ADMIN_GIFT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_gift_points_amount)],
            ADMIN_GIFT_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_gift_points_days)],
            ADMIN_GIFT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_gift_points_description)],
            ADMIN_GIFT_GENDER: [CallbackQueryHandler(admin_gift_points_gender, pattern="^gift_gender_")],
        },
        fallbacks=[CallbackQueryHandler(cancel_admin_action, pattern="^cancel$")]
    )
    
    application.add_handler(create_promotion_handler)
    application.add_handler(broadcast_handler)
    application.add_handler(settings_handler)
    application.add_handler(gift_handler)

    # ConversationHandler для создания розыгрыша ОТКЛЮЧЕН - используйте веб-интерфейс
    # giveaway_handler = ConversationHandler(...)
    # application.add_handler(giveaway_handler)
    
    application.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    application.add_handler(CallbackQueryHandler(admin_manage_promotions, pattern="^admin_manage_promotions$"))
    application.add_handler(CallbackQueryHandler(admin_delete_promotion_confirm, pattern=r"^delete_promo_\d+$"))
    application.add_handler(CallbackQueryHandler(admin_confirm_delete_promotion, pattern="^confirm_delete_promo$"))
    application.add_handler(CallbackQueryHandler(admin_notifications_menu, pattern="^admin_notifications$"))
    application.add_handler(CallbackQueryHandler(admin_send_notifications_now, pattern="^admin_send_notifications$"))
    application.add_handler(CallbackQueryHandler(admin_inactive_stats, pattern="^admin_inactive_stats$"))
    application.add_handler(CallbackQueryHandler(admin_notification_settings, pattern="^admin_notification_settings$"))
    application.add_handler(CallbackQueryHandler(toggle_notifications, pattern="^toggle_notifications$"))
    application.add_handler(CallbackQueryHandler(back_to_admin_menu, pattern="^back_to_admin$"))
    
    # Обработчики графиков
    application.add_handler(CallbackQueryHandler(admin_charts_menu, pattern="^admin_charts_menu$"))
    application.add_handler(CallbackQueryHandler(admin_chart_monthly_stats, pattern="^chart_monthly_stats$"))
    application.add_handler(CallbackQueryHandler(admin_chart_points, pattern="^chart_points$"))

    # Розыгрыш (админ/кассир)
    application.add_handler(CallbackQueryHandler(admin_giveaway_menu, pattern="^admin_giveaway_menu$"))
    application.add_handler(CallbackQueryHandler(admin_giveaway_broadcast, pattern=r"^admin_giveaway_broadcast_\d+$"))
    application.add_handler(CallbackQueryHandler(admin_giveaway_stop, pattern=r"^admin_giveaway_stop_\d+$"))
    application.add_handler(CallbackQueryHandler(admin_giveaway_top, pattern=r"^admin_giveaway_top_\d+$"))
    application.add_handler(CallbackQueryHandler(admin_giveaway_notify_participants, pattern=r"^admin_giveaway_notify_participants_\d+$"))
    
    # Праздничные подарки
    application.add_handler(CallbackQueryHandler(admin_gift_menu, pattern="^admin_gift_menu$"))
    application.add_handler(CallbackQueryHandler(admin_gift_manage, pattern="^admin_gift_manage$"))
    application.add_handler(CallbackQueryHandler(admin_gift_delete_confirm, pattern=r"^delete_holiday_\d+$"))
    
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Общий обработчик текста должен быть в самом конце
    # чтобы не перехватывать сообщения ConversationHandler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("🤖 Телеграм бот программы лояльности запущен!")
    logger.info(f"👤 Администратор: {config.ADMIN_USER_ID}")
    logger.info(f"🔧 Режим отладки: {config.DEBUG}")
    
    if config.ENABLE_NOTIFICATIONS:
        logger.info(f"📢 Уведомления включены (порог: {config.INACTIVITY_DAYS_THRESHOLD} дней)")
    else:
        logger.info("📢 Уведомления отключены")
    
    print("🚀 Бот успешно запущен!")
    print(f"👤 Администратор: ID {config.ADMIN_USER_ID}")
    print(f"📋 Всего администраторов: {len(config.ADMIN_IDS)}")
    print(f"🔧 Режим отладки: {'Включен' if config.DEBUG else 'Выключен'}")
    print(f"📢 Уведомления: {'Включены' if config.ENABLE_NOTIFICATIONS else 'Выключены'}")
    
    if config.DEBUG:
        print(f"📋 Список админов: {config.ADMIN_IDS}")
    
    print("⚙️ Для остановки нажмите Ctrl+C")
    
    application.run_polling(
        allowed_updates=['message', 'callback_query'],
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main() 