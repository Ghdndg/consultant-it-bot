#!/usr/bin/env python3

import asyncio
import logging
import threading
from telegram import Bot
from telegram.request import HTTPXRequest
from telegram.error import TelegramError
import config

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.request = HTTPXRequest(connect_timeout=30, read_timeout=30)
        self.bot = Bot(token=config.BOT_TOKEN, request=self.request)
    
    async def send_document(self, chat_id: int, file_path: str, caption: str = None):
        try:
            with open(file_path, 'rb') as f:
                await self.bot.send_document(chat_id=chat_id, document=f, caption=caption or '')
            logger.info(f"Файл отправлен в чат {chat_id}: {file_path}")
            return True
        except TelegramError as e:
            logger.error(f"Ошибка отправки файла в чат {chat_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке файла: {e}")
            return False
    
    async def send_purchase_notification(self, telegram_id: int, purchase_amount: float, 
                                       points_earned: int, total_points: int, 
                                       description: str = ""):
        try:
            discount_info = ""
            if "использовано" in description:
                discount_info = "\n💰 В покупке использованы бонусные баллы!"
            
            message = f"""
🛒 Новая покупка зарегистрирована!

💰 Сумма покупки: {purchase_amount:.2f} ₽
🎁 Начислено баллов: +{points_earned}
💳 Общий баланс: {total_points} баллов{discount_info}

{f"📝 Описание: {description}" if description else ""}

Спасибо за покупку! 🎉
            """
            
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message.strip()
            )
            
            logger.info(f"Уведомление о покупке отправлено пользователю {telegram_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"Ошибка отправки уведомления пользователю {telegram_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке уведомления: {e}")
            return False

def send_purchase_notification_sync(telegram_id: int, purchase_amount: float,
                                  points_earned: int, total_points: int,
                                  description: str = ""):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    notifier = TelegramNotifier()
    
    try:
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                notifier.send_purchase_notification(
                    telegram_id, purchase_amount, points_earned, total_points, description
                ),
                loop
            )
            return future.result(timeout=10)
        else:
            return loop.run_until_complete(
                notifier.send_purchase_notification(
                    telegram_id, purchase_amount, points_earned, total_points, description
                )
            )
    except Exception as e:
        logger.error(f"Ошибка в send_purchase_notification_sync: {e}")
        return False

def send_document_sync(chat_id: int, file_path: str, caption: str = None):
    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        notifier = TelegramNotifier()
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                notifier.send_document(chat_id, file_path, caption),
                loop
            )
            return future.result(timeout=20)
        else:
            return loop.run_until_complete(
                notifier.send_document(chat_id, file_path, caption)
            )
    except Exception as e:
        logger.error(f"Ошибка в send_document_sync: {e}")
        return False

async def send_notification_to_user(telegram_id: int, message: str):
    """Отправляет простое сообщение пользователю асинхронно."""
    request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    bot = Bot(token=config.BOT_TOKEN, request=request)
    try:
        async with bot:
            await bot.send_message(chat_id=telegram_id, text=message)
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления пользователю {telegram_id}: {e}")
        return False

def run_notification_sync(telegram_id: int, message: str):
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(send_notification_to_user(telegram_id, message))
            return result
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Ошибка в run_notification_sync: {e}")
        return False


def send_message_with_inline_button_sync(telegram_id: int, message: str, button_text: str, callback_data: str) -> bool:
    """Отправляет сообщение с inline-кнопкой (callback_data) синхронно.
    Автоматически использует уже запущенный event loop, если он есть.
    """
    import asyncio
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    import threading

    async def _send():
        request = HTTPXRequest(connect_timeout=30, read_timeout=30)
        bot = Bot(token=config.BOT_TOKEN, request=request)
        try:
            markup = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, callback_data=callback_data)]])
            async with bot:
                await bot.send_message(chat_id=telegram_id, text=message, reply_markup=markup)
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения (инлайн) пользователю {telegram_id}: {e}")
            return False

    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # Если цикл уже запущен, отправляем в отдельном потоке
            result = [False]
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result[0] = new_loop.run_until_complete(_send())
                finally:
                    new_loop.close()
            
            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()
            thread.join(timeout=15)  # Увеличен таймаут до 15 секунд
            return result[0]
        else:
            return bool(loop.run_until_complete(_send()))

    except Exception as e:
        logger.error(f"Ошибка send_message_with_inline_button_sync: {e}", exc_info=True)
        return False

class AsyncNotificationSender:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.bot = None
    
    async def init_bot(self):
        if not self.bot:
            request = HTTPXRequest(connect_timeout=30, read_timeout=30)
            self.bot = Bot(token=self.bot_token, request=request)
            await self.bot.initialize()
    
    async def send_notification(self, telegram_id: int, message: str):
        await self.init_bot()
        try:
            await self.bot.send_message(chat_id=telegram_id, text=message)
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления {telegram_id}: {e}")
            return False
    
    async def send_bulk_notifications(self, notifications: list):
        await self.init_bot()
        successful = 0
        failed = 0
        
        for telegram_id, message in notifications:
            try:
                await self.bot.send_message(chat_id=telegram_id, text=message)
                successful += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления {telegram_id}: {e}")
                failed += 1
        
        return successful, failed

async def test_notification_system():
    try:
        notifier = TelegramNotifier()
        
        test_result = await notifier.send_purchase_notification(
            telegram_id=config.ADMIN_USER_ID,
            purchase_amount=100.0,
            points_earned=10,
            total_points=50,
            description="Тестовая покупка для проверки уведомлений"
        )
        
        if test_result:
            logger.info("✅ Тест уведомлений прошел успешно")
            return True
        else:
            logger.error("❌ Тест уведомлений провален")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка теста уведомлений: {e}")
        return False

def threaded_notification(telegram_id: int, message: str):
    def notification_worker():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                success = loop.run_until_complete(send_notification_to_user(telegram_id, message))
                logger.info(f"Уведомление отправлено в потоке: {success}")
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка в потоке уведомлений: {e}")
    
    thread = threading.Thread(target=notification_worker, daemon=True)
    thread.start()
    return thread

# Алиас для совместимости
TelegramNotificationService = TelegramNotifier

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    async def main():
        print("🧪 Тестирование системы уведомлений...")
        success = await test_notification_system()
        print(f"Результат: {'✅ Успешно' if success else '❌ Ошибка'}")
    
    asyncio.run(main()) 