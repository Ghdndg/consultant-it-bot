import random
import string
import qrcode
import logging
from io import BytesIO
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import User, Purchase, PointsHistory, Promotion, Giveaway, GiveawayParticipant, HolidayGift, get_db
import config
from typing import Optional

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, telegram_id: int, username: str = None, first_name: str = None, last_name: str = None):
        existing_user = self.db.query(User).filter(User.telegram_id == telegram_id).first()
        if existing_user:
            return existing_user
            
        referral_code = self.generate_referral_code()
        
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            referral_code=referral_code
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user_by_telegram_id(self, telegram_id: int):
        return self.db.query(User).filter(User.telegram_id == telegram_id).first()

    def get_user_by_referral_code(self, referral_code: str):
        return self.db.query(User).filter(User.referral_code == referral_code).first()

    def generate_referral_code(self):
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not self.db.query(User).filter(User.referral_code == code).first():
                return code

    def update_user_contact(self, telegram_id: int, phone: str = None):
        user = self.get_user_by_telegram_id(telegram_id)
        if user:
            if phone:
                user.phone = phone
            self.db.commit()
            return user
        return None

    def create_incomplete_user(self, telegram_id: int, username: str = None):
        """Создает неполную запись пользователя для последующего завершения регистрации"""
        existing_user = self.db.query(User).filter(User.telegram_id == telegram_id).first()
        if existing_user:
            return existing_user
            
        referral_code = self.generate_referral_code()
        
        user = User(
            telegram_id=telegram_id,
            username=username,
            referral_code=referral_code,
            is_registered=False  # Пользователь еще не завершил регистрацию
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def complete_registration(self, telegram_id: int, first_name: str, last_name: str, birth_date, phone: str, username: str = None, gender: str = None):
        """Создает пользователя с полными данными (пользователь создается только при завершении регистрации)"""
        # Проверяем, существует ли уже пользователь
        user = self.get_user_by_telegram_id(telegram_id)
        # Если пользователь уже зарегистрирован, новые бонусы не выдаем
        was_registered = user.is_registered if user else False
        
        if user:
            # Если пользователь уже существует, обновляем его данные
            user.first_name = first_name
            user.last_name = last_name
            user.birth_date = birth_date
            user.phone = phone
            user.is_registered = True
            if username:
                user.username = username
            if gender is not None:
                user.gender = gender
        else:
            # Создаем нового пользователя с полными данными
            referral_code = self.generate_referral_code()
            
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                birth_date=birth_date,
                phone=phone,
                referral_code=referral_code,
                is_registered=True,
                points=0,
                gender=gender
            )
            
            self.db.add(user)
        
        self.db.commit()
        self.db.refresh(user)

        # Праздничные бонусы выдаем только один раз - в момент успешной регистрации
        if not was_registered and user.is_registered:
            try:
                loyalty_service = LoyaltyService(self.db)
                loyalty_service.award_holiday_gifts(user.id)
            except Exception as e:
                logger.error(f"Ошибка при начислении праздничных бонусов: {e}")

        return True

    def get_user_referrals(self, user_id: int):
        """Получает список пользователей, приглашенных данным пользователем"""
        return self.db.query(User).filter(
            User.referred_by == user_id,
            User.is_registered == True
        ).order_by(User.registration_date.desc()).all()

class LoyaltyService:
    def __init__(self, db: Session):
        self.db = db

    def add_purchase(self, user_id: int, amount: float, description: str = "", points_used: int = 0):
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        # Проверяем, достаточно ли баллов для списания
        if points_used > 0:
            if user.points < points_used:
                return None  # Недостаточно баллов
            
            # Списываем баллы
            user.points -= points_used
            
            # Добавляем запись в историю о списании баллов
            redemption_history = PointsHistory(
                user_id=user_id,
                points_change=-points_used,
                transaction_type='redemption',
                description=f"Скидка при покупке: {description or 'без описания'}"
            )
            self.db.add(redemption_history)

        # ВАЖНО: Начисляем бонусы только с реально потраченных денег (сумма - использованные баллы)
        real_money_spent = amount - points_used
        points_earned = int(real_money_spent * config.POINTS_PER_PURCHASE / 100)
        
        purchase = Purchase(
            user_id=user_id,
            amount=amount,
            points_earned=points_earned,
            points_used=points_used,  # Сохраняем количество потраченных баллов
            description=description
        )
        
        user.points += points_earned
        user.total_spent += amount
        
        points_history = PointsHistory(
            user_id=user_id,
            points_change=points_earned,
            transaction_type='purchase',
            description=f"Покупка: {description} (с реальной суммы {real_money_spent:.2f})"
        )
        
        self.db.add(purchase)
        self.db.add(points_history)
        
        # ОТКЛЮЧЕНО: бонус за порог (давался при каждой покупке)
        # bonus_points = self.check_bonus_eligibility(user)
        # if bonus_points > 0:
        #     self.add_bonus_points(user_id, bonus_points, "Бонус за достижение порога")
        
        self.db.commit()
        return purchase, points_earned

    def redeem_points(self, user_id: int, points_to_redeem: int, description: str = ""):
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or user.points < points_to_redeem:
            return False

        user.points -= points_to_redeem
        
        points_history = PointsHistory(
            user_id=user_id,
            points_change=-points_to_redeem,
            transaction_type='redemption',
            description=description
        )
        
        self.db.add(points_history)
        self.db.commit()
        return True

    def return_purchase(self, purchase_id: int):
        """Возврат покупки - возвращает потраченные баллы и отбирает начисленные"""
        purchase = self.db.query(Purchase).filter(Purchase.id == purchase_id).first()
        if not purchase or purchase.is_returned:
            return False, "Покупка не найдена или уже возвращена"

        user = self.db.query(User).filter(User.id == purchase.user_id).first()
        if not user:
            return False, "Пользователь не найден"

        # Возвращаем потраченные при покупке баллы (если были)
        if purchase.points_used > 0:
            user.points += purchase.points_used
            
            # Добавляем запись в историю о возврате потраченных баллов
            points_history_return = PointsHistory(
                user_id=purchase.user_id,
                points_change=purchase.points_used,
                transaction_type='return',
                description=f"Возврат потраченных баллов за покупку: {purchase.description}"
            )
            self.db.add(points_history_return)

        # Отбираем баллы, которые были начислены за покупку
        if purchase.points_earned > 0:
            user.points -= purchase.points_earned
            
            # Добавляем запись в историю об отмене начисленных баллов
            points_history_cancel = PointsHistory(
                user_id=purchase.user_id,
                points_change=-purchase.points_earned,
                transaction_type='return',
                description=f"Отмена начисленных баллов за возвращенную покупку: {purchase.description}"
            )
            self.db.add(points_history_cancel)
        
        # Уменьшаем общую сумму покупок
        user.total_spent -= purchase.amount
        
        # Отмечаем покупку как возвращенную
        purchase.is_returned = True
        purchase.return_date = datetime.now()
        
        self.db.commit()
        
        # Формируем сообщение о возврате
        message_parts = ["Покупка успешно возвращена"]
        if purchase.points_used > 0:
            message_parts.append(f"возвращено {purchase.points_used} потраченных баллов")
        if purchase.points_earned > 0:
            message_parts.append(f"отменено {purchase.points_earned} начисленных баллов")
            
        return True, ". ".join(message_parts).capitalize() + "."

    def add_bonus_points(self, user_id: int, points: int, description: str = "", expiry_date: datetime = None):
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        user.points += points
        
        points_history = PointsHistory(
            user_id=user_id,
            points_change=points,
            transaction_type='bonus',
            description=description,
            expiry_date=expiry_date
        )
        
        self.db.add(points_history)
        self.db.commit()
        return True

    def process_expired_points(self):
        """Находит и списывает просроченные баллы"""
        now = datetime.now()
        expired_entries = self.db.query(PointsHistory).filter(
            PointsHistory.expiry_date < now,
            PointsHistory.is_expired_processed == False,
            PointsHistory.points_change > 0
        ).all()
        
        processed_count = 0
        for entry in expired_entries:
            user = self.db.query(User).filter(User.id == entry.user_id).first()
            if user:
                # Определяем сколько баллов реально сгорает
                # (не больше чем есть у пользователя и не больше чем было начислено)
                burn_amount = min(user.points, entry.points_change)
                
                if burn_amount > 0:
                    user.points -= burn_amount
                    
                    # Создаем запись о списании по истечению срока
                    burn_history = PointsHistory(
                        user_id=user.id,
                        points_change=-burn_amount,
                        transaction_type='expiry',
                        description=f"Сгорание баллов по сроку: {entry.description}"
                    )
                    self.db.add(burn_history)
                
                entry.is_expired_processed = True
                processed_count += 1
        
        if processed_count > 0:
            self.db.commit()
            logger.info(f"Обработано сгоревших начислений: {processed_count}")
        
        return processed_count

    def check_bonus_eligibility(self, user: User):
        if user.points >= config.BONUS_THRESHOLD:
            return config.BONUS_AMOUNT
        return 0

    def apply_referral(self, new_user_id: int, referral_code: str):
        """Применяет реферальный код - начисляет баллы и реферу и новому пользователю"""
        referrer = self.db.query(User).filter(User.referral_code == referral_code).first()
        new_user = self.db.query(User).filter(User.id == new_user_id).first()
        
        if referrer and new_user and referrer.id != new_user.id and not new_user.referred_by:
            # Устанавливаем связь
            new_user.referred_by = referrer.id
            
            # Начисляем баллы реферу (тому кто поделился кодом)
            referrer.points += config.REFERRAL_BONUS
            referrer_history = PointsHistory(
                user_id=referrer.id,
                points_change=config.REFERRAL_BONUS,
                transaction_type='bonus',
                description=f"Реферальный бонус за {new_user.first_name}"
            )
            
            # Начисляем баллы новому пользователю  
            new_user.points += config.REFERRAL_BONUS
            new_user_history = PointsHistory(
                user_id=new_user.id,
                points_change=config.REFERRAL_BONUS,
                transaction_type='bonus',
                description="Бонус за регистрацию по реферальной ссылке"
            )
            
            # Сохраняем все изменения в одной транзакции
            self.db.add(referrer_history)
            self.db.add(new_user_history)
            self.db.commit()

            # Приглашаем приглашенного в активный розыгрыш, если он есть
            try:
                active_giveaway: Optional[Giveaway] = self.get_active_giveaway()
                if active_giveaway and new_user.telegram_id:
                    # Отправляем сообщение с кнопкой "Участвую" в бот
                    from telegram_notifications import send_message_with_inline_button_sync
                    message_text = (
                        f"🎉 Розыгрыш: {active_giveaway.title}\n\n"
                        f"Присоединяйся и зови друзей — победит тот, кто пригласит больше всего за период розыгрыша."
                    )
                    send_message_with_inline_button_sync(
                        telegram_id=new_user.telegram_id,
                        message=message_text,
                        button_text="✅ Участвую",
                        callback_data=f"giveaway_join_{active_giveaway.id}"
                    )
            except Exception as notify_err:
                logger.warning(f"Не удалось отправить приглашение в розыгрыш: {notify_err}")
            
            return True
        return False

    def get_points_history(self, user_id: int, limit: int = 10):
        return self.db.query(PointsHistory).filter(
            PointsHistory.user_id == user_id
        ).order_by(PointsHistory.created_date.desc()).limit(limit).all()

    def get_referral_top(self, limit: int = 10):
        """Получает топ пользователей по количеству приглашенных рефералов"""
        from sqlalchemy import func
        
        # Подзапрос для подсчета рефералов каждого пользователя
        referrals_subquery = self.db.query(
            User.referred_by,
            func.count(User.id).label('count')
        ).filter(
            User.referred_by.isnot(None),
            User.is_registered == True
        ).group_by(User.referred_by).subquery()
        
        # Основной запрос - получаем пользователей с количеством рефералов
        # Используем LEFT JOIN чтобы получить всех пользователей, даже без рефералов
        top_users = self.db.query(
            User,
            func.coalesce(referrals_subquery.c.count, 0).label('referrals_count')
        ).outerjoin(
            referrals_subquery, User.id == referrals_subquery.c.referred_by
        ).filter(
            User.is_registered == True
        ).order_by(
            func.coalesce(referrals_subquery.c.count, 0).desc(),
            User.id.asc()
        ).all()
        
        # Формируем список с данными
        result = []
        for user, count in top_users:
            actual_count = int(count) if count else 0
            # Добавляем только тех, у кого есть рефералы
            if actual_count > 0:
                result.append({
                    'user_id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'username': user.username,
                    'referral_code': user.referral_code,
                    'referrals_count': actual_count,
                    'points': user.points or 0,
                    'telegram_id': user.telegram_id
                })
        
        # Сортируем по количеству рефералов (убывание) и ограничиваем лимитом
        result.sort(key=lambda x: x['referrals_count'], reverse=True)
        return result[:limit]
    
    def get_user_referral_position(self, user_id: int):
        """Получает позицию пользователя в топе рефералов"""
        from sqlalchemy import func
        
        # Получаем пользователя
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        # Получаем количество рефералов у пользователя
        user_referrals_count = self.db.query(User).filter(
            User.referred_by == user_id,
            User.is_registered == True
        ).count()
        
        # Подзапрос для подсчета рефералов каждого пользователя
        referrals_subquery = self.db.query(
            User.referred_by,
            func.count(User.id).label('count')
        ).filter(
            User.referred_by.isnot(None),
            User.is_registered == True
        ).group_by(User.referred_by).subquery()
        
        # Считаем, сколько пользователей имеют больше рефералов
        users_with_more = self.db.query(func.count()).select_from(
            referrals_subquery
        ).filter(
            referrals_subquery.c.count > user_referrals_count
        ).scalar() or 0
        
        position = users_with_more + 1
        
        return {
            'position': position,
            'referrals_count': user_referrals_count,
            'user_id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'username': user.username,
            'referral_code': user.referral_code,
            'points': user.points or 0,
            'telegram_id': user.telegram_id
        }

    def get_user_statistics(self, user_id: int):
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        purchases_count = self.db.query(Purchase).filter(Purchase.user_id == user_id).count()
        referrals_count = self.db.query(User).filter(User.referred_by == user_id).count()
        
        return {
            'points': user.points,
            'total_spent': user.total_spent,
            'purchases_count': purchases_count,
            'referrals_count': referrals_count,
            'registration_date': user.registration_date,
            'referral_code': user.referral_code
        }

    # -------------------- РОЗЫГРЫШ (конкурс по рефералам за период) --------------------
    def get_active_giveaway(self):
        """Получает активный розыгрыш, автоматически завершая истекшие"""
        giveaway = self.db.query(Giveaway).filter(Giveaway.is_active == True).order_by(Giveaway.id.desc()).first()
        
        # Автоматически завершаем розыгрыш, если срок истек
        if giveaway and giveaway.end_date and datetime.now() > giveaway.end_date:
            logger.info(f"Автоматическое завершение розыгрыша {giveaway.id} (срок истек)")
            giveaway.is_active = False
            self.db.commit()
            
            # Отправляем уведомление админам о завершении
            self._notify_admins_giveaway_ended(giveaway)
            
            return None  # Возвращаем None, так как розыгрыш уже неактивен
        
        return giveaway

    def create_giveaway(self, title: str, days: int, description: str = ""):
        """Создать и сразу запустить розыгрыш на N дней (предыдущий активный завершаем)."""
        if days < 1 or days > 365:
            raise ValueError("Дней должно быть от 1 до 365")

        active = self.get_active_giveaway()
        if active:
            active.is_active = False
            if not active.end_date:
                active.end_date = datetime.now()

        now = datetime.now()
        giveaway = Giveaway(
            title=(title or "").strip() or "Розыгрыш",
            description=(description or "").strip(),
            created_date=now,
            start_date=now,
            end_date=now + timedelta(days=days),
            is_active=True
        )
        self.db.add(giveaway)
        self.db.commit()
        self.db.refresh(giveaway)
        return giveaway

    def stop_giveaway(self, giveaway_id: int) -> bool:
        giveaway = self.db.query(Giveaway).filter(Giveaway.id == giveaway_id).first()
        if not giveaway:
            return False
        giveaway.is_active = False
        giveaway.end_date = datetime.now()
        self.db.commit()
        return True

    def join_active_giveaway(self, user_id: int):
        """Добавляет пользователя в активный розыгрыш."""
        giveaway = self.get_active_giveaway()
        if not giveaway:
            return None, "Сейчас нет активного розыгрыша."
        if giveaway.end_date and datetime.now() > giveaway.end_date:
            giveaway.is_active = False
            self.db.commit()
            return None, "Розыгрыш уже завершён."

        existing = self.db.query(GiveawayParticipant).filter(
            GiveawayParticipant.giveaway_id == giveaway.id,
            GiveawayParticipant.user_id == user_id
        ).first()
        if existing:
            return giveaway, "Вы уже участвуете."

        p = GiveawayParticipant(giveaway_id=giveaway.id, user_id=user_id)
        self.db.add(p)
        self.db.commit()
        return giveaway, "✅ Вы участвуете в розыгрыше!"

    def _giveaway_referrals_count(self, giveaway: Giveaway, participant_user_id: int) -> int:
        """Сколько рефералов зарегистрировалось у участника в период розыгрыша."""
        if not giveaway.start_date:
            return 0
        start = giveaway.start_date
        end = giveaway.end_date or datetime.now()

        return int(self.db.query(User).filter(
            User.referred_by == participant_user_id,
            User.is_registered == True,
            User.registration_date >= start,
            User.registration_date <= end
        ).count())

    def get_giveaway_top(self, giveaway_id: int, limit: int = 10, giveaway_obj: Giveaway = None):
        """Получает топ участников розыгрыша. 
        giveaway_obj: опциональный параметр для передачи уже загруженного объекта розыгрыша"""
        giveaway = giveaway_obj or self.db.query(Giveaway).filter(Giveaway.id == giveaway_id).first()
        if not giveaway:
            return []

        participants = self.db.query(GiveawayParticipant).filter(
            GiveawayParticipant.giveaway_id == giveaway_id
        ).all()

        result = []
        for p in participants:
            user = self.db.query(User).filter(User.id == p.user_id).first()
            if not user:
                continue
            cnt = self._giveaway_referrals_count(giveaway, user.id)
            result.append({
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "referrals_count": cnt,
                "points": user.points or 0,
            })

        result.sort(key=lambda x: (x["referrals_count"], x["user_id"]), reverse=True)
        return result[:limit]

    def _notify_admins_giveaway_ended(self, giveaway: Giveaway):
        """Отправляет уведомление админам о завершении розыгрыша"""
        try:
            from telegram_notifications import send_message_with_inline_button_sync
            import config
            
            # Определяем победителя (передаем объект giveaway, чтобы избежать повторного запроса)
            giveaway_top = self.get_giveaway_top(giveaway.id, limit=1, giveaway_obj=giveaway)
            winner_info = "Победителей нет"
            
            if giveaway_top and len(giveaway_top) > 0 and giveaway_top[0]["referrals_count"] > 0:
                winner_data = giveaway_top[0]
                winner = self.db.query(User).filter(User.id == winner_data["user_id"]).first()
                if winner:
                    winner_name = f"{winner.first_name or ''} {winner.last_name or ''}".strip() or f"Участник #{winner.id}"
                    winner_info = f"🏆 Победитель: {winner_name}\n📊 Приглашено друзей: {winner_data['referrals_count']}"
            
            admin_message = f"""
🎉 Розыгрыш завершён автоматически (срок истек)!

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
                        callback_data=f"admin_giveaway_notify_participants_{giveaway.id}"
                    )
                    logger.info(f"Уведомление о завершении розыгрыша отправлено админу {admin_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомлений о завершении розыгрыша: {e}", exc_info=True)

    def get_giveaway_user_position(self, giveaway_id: int, user_id: int):
        giveaway = self.db.query(Giveaway).filter(Giveaway.id == giveaway_id).first()
        if not giveaway:
            return None

        is_participant = self.db.query(GiveawayParticipant).filter(
            GiveawayParticipant.giveaway_id == giveaway_id,
            GiveawayParticipant.user_id == user_id
        ).first()
        if not is_participant:
            return None

        participants = self.db.query(GiveawayParticipant).filter(
            GiveawayParticipant.giveaway_id == giveaway_id
        ).all()

        scores = []
        for p in participants:
            cnt = self._giveaway_referrals_count(giveaway, p.user_id)
            scores.append((p.user_id, cnt))

        scores.sort(key=lambda t: (t[1], t[0]), reverse=True)
        for idx, (uid, cnt) in enumerate(scores, 1):
            if uid == user_id:
                return {"position": idx, "referrals_count": cnt, "user_id": uid}
        return None

    # -------------------- ПРАЗДНИЧНЫЕ БОНУСЫ (ДЛЯ НОВЫХ ПОЛЬЗОВАТЕЛЕЙ) --------------------
    def award_holiday_gifts(self, user_id: int):
        """Начисляет все активные праздничные бонусы новому пользователю."""
        from database import User, HolidayGift
        from telegram_notifications import threaded_notification
        
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return

        from sqlalchemy import or_
        now = datetime.now()
        active_gifts = self.db.query(HolidayGift).filter(
            HolidayGift.is_active == True,
            HolidayGift.start_date <= now,
            or_(HolidayGift.end_date == None, HolidayGift.end_date >= now)
        ).all()
        
        for gift in active_gifts:
            expiry_date = None
            expiry_text = ""
            if gift.days_to_expire > 0:
                expiry_date = datetime.now() + timedelta(days=gift.days_to_expire)
                expiry_text = f"\n⏰ Баллы действительны до {expiry_date.strftime('%d.%m.%Y')}"
            
            self.add_bonus_points(
                user_id=user_id,
                points=gift.amount,
                description=gift.description,
                expiry_date=expiry_date
            )
            logger.info(f"Начислен праздничный бонус {gift.amount} баллов пользователю {user_id}")
            
            # Отправляем уведомление только если есть реальный Telegram ID
            if user.telegram_id > 0:
                notification_msg = f"""
🎁 Вам подарок за регистрацию!

{gift.description}
💰 Начислено: {gift.amount} бонусных баллов
{expiry_text}

Приятного использования! 🎉
                """
                try:
                    threaded_notification(user.telegram_id, notification_msg.strip())
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления о подарке: {e}")

class QRService:
    @staticmethod
    def generate_user_qr(user_id: int, telegram_id: int):
        qr_data = f"{user_id}_{telegram_id}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=config.QR_CODE_SIZE,
            border=config.QR_CODE_BORDER,
        )
        
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)
        
        return bio.getvalue()

class PromotionService:
    def __init__(self, db: Session):
        self.db = db

    def get_active_promotions(self):
        now = datetime.now()
        return self.db.query(Promotion).filter(
            Promotion.is_active == True,
            Promotion.start_date <= now,
            (Promotion.end_date >= now) | (Promotion.end_date == None)  # Акции без end_date считаются активными
        ).all()

    def create_promotion(self, title: str, description: str, discount_percent: int = None, 
                        points_required: int = None, start_date: datetime = None, 
                        end_date: datetime = None):
        promotion = Promotion(
            title=title,
            description=description,
            discount_percent=discount_percent,
            points_required=points_required,
            start_date=start_date or datetime.now(),
            end_date=end_date
        )
        
        self.db.add(promotion)
        self.db.commit()
        self.db.refresh(promotion)
        return promotion

    def get_promotion_by_id(self, promotion_id: int):
        """Получить акцию по ID"""
        return self.db.query(Promotion).filter(Promotion.id == promotion_id).first()

    def delete_promotion(self, promotion_id: int):
        """Удалить акцию по ID"""
        try:
            promotion = self.db.query(Promotion).filter(Promotion.id == promotion_id).first()
            if promotion:
                self.db.delete(promotion)
                self.db.commit()
                return True
            return False
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка при удалении акции {promotion_id}: {e}")
            return False 