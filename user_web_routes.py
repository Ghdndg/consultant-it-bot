#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Веб-интерфейс для пользователей программы лояльности
Авторизация через Telegram ID
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from database import get_db, User, Purchase, PointsHistory, GiveawayParticipant
from services import UserService, LoyaltyService, QRService
from datetime import datetime, timedelta
import logging
import random
import threading
from telegram_notifications import run_notification_sync
from io import BytesIO
import string

logger = logging.getLogger(__name__)

# Создаем Blueprint для пользовательских маршрутов
user_bp = Blueprint('user', __name__, url_prefix='/user')

# Хранилище кодов подтверждения (в памяти)
# В продакшене лучше использовать Redis или БД
verification_codes = {}
code_lock = threading.Lock()

def generate_verification_code():
    """Генерация 6-значного кода"""
    return str(random.randint(100000, 999999))

def store_verification_code(telegram_id: int, code: str):
    """Сохранение кода с таймаутом 5 минут"""
    with code_lock:
        verification_codes[telegram_id] = {
            'code': code,
            'expires_at': datetime.now() + timedelta(minutes=5),
            'attempts': 0
        }

def verify_code(telegram_id: int, code: str) -> bool:
    """Проверка кода"""
    with code_lock:
        if telegram_id not in verification_codes:
            return False
        
        code_data = verification_codes[telegram_id]
        
        # Проверка срока действия
        if datetime.now() > code_data['expires_at']:
            del verification_codes[telegram_id]
            return False
        
        # Проверка кода
        if code_data['code'] == code:
            del verification_codes[telegram_id]
            return True
        
        # Увеличиваем счетчик попыток
        code_data['attempts'] += 1
        if code_data['attempts'] >= 5:
            # Блокируем после 5 неудачных попыток
            del verification_codes[telegram_id]
        
        return False

def cleanup_expired_codes():
    """Очистка истекших кодов (запускается периодически)"""
    with code_lock:
        now = datetime.now()
        expired = [tid for tid, data in verification_codes.items() 
                   if now > data['expires_at']]
        for tid in expired:
            del verification_codes[tid]

def generate_web_credentials():
    """Генерация логина и пароля для веб-входа"""
    # Генерируем логин: user + случайные цифры
    login = 'user' + ''.join(random.choices(string.digits, k=6))
    
    # Генерируем пароль: 8 символов (буквы + цифры)
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    return login, password

def require_user_login(f):
    """Декоратор для проверки авторизации пользователя"""
    def decorated_function(*args, **kwargs):
        if not session.get('user_logged_in'):
            return redirect(url_for('user.user_login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@user_bp.route('/')
def user_index():
    """Главная страница для пользователей"""
    if session.get('user_logged_in'):
        return redirect(url_for('user.user_profile'))
    return redirect(url_for('user.user_login'))

@user_bp.route('/register', methods=['GET', 'POST'])
def user_register():
    """Регистрация новых пользователей по телефону"""
    if request.method == 'POST':
        try:
            phone = request.form.get('phone', '').strip()
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            birth_date_str = request.form.get('birth_date', '').strip()
            gender = request.form.get('gender', '').strip()
            
            if not phone:
                flash('Введите номер телефона', 'error')
                return render_template('user_register.html')
            
            # Проверка формата телефона (базовая)
            phone_clean = ''.join(filter(str.isdigit, phone))
            if len(phone_clean) < 10:
                flash('Некорректный номер телефона', 'error')
                return render_template('user_register.html')
            
            if not birth_date_str:
                flash('Укажите дату рождения', 'error')
                return render_template('user_register.html')
            
            if not gender or gender not in ['male', 'female']:
                flash('Укажите ваш пол', 'error')
                return render_template('user_register.html')
            
            try:
                birth_date_val = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
                
                # Проверяем, что возраст разумный (от 10 до 120 лет)
                today = datetime.now().date()
                age = today.year - birth_date_val.year - ((today.month, today.day) < (birth_date_val.month, birth_date_val.day))
                
                if age < 10 or age > 120:
                    flash('Пожалуйста, укажите корректную дату рождения (возраст от 10 до 120 лет)', 'error')
                    return render_template('user_register.html')
                    
            except ValueError:
                flash('Некорректная дата рождения', 'error')
                return render_template('user_register.html')
            
            # Проверка, не зарегистрирован ли уже пользователь с таким телефоном
            db = get_db()
            existing_user = db.query(User).filter(User.phone == phone_clean).first()
            
            if existing_user:
                db.close()
                flash('Пользователь с таким номером телефона уже зарегистрирован. Войдите через Telegram ID, если вы зарегистрированы в боте.', 'error')
                return redirect(url_for('user.user_login'))
            
            # Создание нового пользователя без Telegram ID (временно)
            # Telegram ID можно будет привязать позже
            user_service = UserService(db)
            
            # Генерируем временный telegram_id (отрицательное число для отличия от реальных)
            import random
            temp_telegram_id = -random.randint(1000000, 9999999)
            
            # Проверяем, что такого ID нет
            while db.query(User).filter(User.telegram_id == temp_telegram_id).first():
                temp_telegram_id = -random.randint(1000000, 9999999)
            
            # Обработка реферального кода
            referral_code_input = request.form.get('referral_code', '').strip().upper()
            referred_by_user = None
            
            if referral_code_input:
                # Ищем пользователя с таким реферальным кодом
                referred_by_user = db.query(User).filter(User.referral_code == referral_code_input).first()
                if not referred_by_user:
                    flash(f'Реферальный код "{referral_code_input}" не найден. Регистрация продолжится без реферального бонуса.', 'warning')
            
            # Создаем пользователя
            user = User(
                telegram_id=temp_telegram_id,  # Временный ID
                phone=phone_clean,
                first_name=first_name if first_name else None,
                last_name=last_name if last_name else None,
                birth_date=birth_date_val,
                gender=gender,
                is_registered=True,
                points=0
            )
            
            # Генерируем реферальный код
            user.referral_code = user_service.generate_referral_code()
            
            # Устанавливаем реферала, если код валиден
            if referred_by_user and referred_by_user.id:
                user.referred_by = referred_by_user.id
            
            # Генерируем логин и пароль для веб-входа
            web_login, web_password = generate_web_credentials()
            
            # Проверяем уникальность логина
            while db.query(User).filter(User.web_login == web_login).first():
                web_login, web_password = generate_web_credentials()
            
            user.web_login = web_login
            user.web_password_hash = web_password  # Храним пароль в открытом виде
            
            db.add(user)
            db.commit()
            db.refresh(user)
            
            # Начисляем 10 баллов за регистрацию всем новым пользователям
            try:
                loyalty_service = LoyaltyService(db)
                registration_bonus = 10
                loyalty_service.add_bonus_points(user.id, registration_bonus, 'Бонус за регистрацию')
                logger.info(f"Бонус за регистрацию начислен пользователю {user.id}: {registration_bonus} баллов")
                
                # Начисляем праздничные бонусы, если есть активные акции
                loyalty_service.award_holiday_gifts(user.id)
            except Exception as e:
                logger.error(f"Ошибка при начислении бонуса за регистрацию: {e}", exc_info=True)
                db.rollback()
            
            # Начисляем дополнительные бонусы за реферала
            if referred_by_user and referred_by_user.id and user.referred_by:
                try:
                    import config
                    loyalty_service = LoyaltyService(db)
                    
                    # Дополнительный бонус новому пользователю за реферальный код (25 баллов)
                    new_user_referral_bonus = config.REFERRAL_BONUS
                    loyalty_service.add_bonus_points(user.id, new_user_referral_bonus, 
                                                   'Дополнительный бонус за регистрацию по реферальной ссылке')
                    
                    # Бонус пригласившему пользователю (25 баллов)
                    referrer_bonus = config.REFERRAL_BONUS
                    loyalty_service.add_bonus_points(referred_by_user.id, referrer_bonus,
                                                    'Бонус за приглашение друга')
                    
                    logger.info(f"Реферальные бонусы начислены: новый пользователь {user.id}, пригласивший {referred_by_user.id}")
                except Exception as e:
                    logger.error(f"Ошибка при начислении реферальных бонусов: {e}", exc_info=True)
                    # Не прерываем регистрацию, если бонусы не начислились
                    db.rollback()
            
            # Авторизуем пользователя
            session['user_logged_in'] = True
            session['user_id'] = user.id
            session['user_telegram_id'] = user.telegram_id
            session['user_name'] = f"{first_name} {last_name}".strip() or f"Пользователь {phone_clean}"
            session['is_web_registered'] = True  # Флаг, что зарегистрирован через веб
            
            # Сохраняем логин и пароль в сессии для показа пользователю
            session['new_web_login'] = web_login
            session['new_web_password'] = web_password
            
            db.close()
            
            flash(f'Регистрация успешна! Добро пожаловать, {session["user_name"]}!', 'success')
            return redirect(url_for('user.user_show_credentials'))
            
        except Exception as e:
            logger.error(f"Ошибка при регистрации пользователя: {e}", exc_info=True)
            flash('Произошла ошибка при регистрации. Попробуйте еще раз.', 'error')
            ref_code = request.args.get('ref', '').strip().upper()
            return render_template('user_register.html', ref_code=ref_code)
    
    # GET запрос - показываем форму регистрации
    # Получаем реферальный код из URL, если есть
    ref_code = request.args.get('ref', '').strip().upper()
    
    return render_template('user_register.html', ref_code=ref_code)

@user_bp.route('/login', methods=['GET', 'POST'])
def user_login():
    """Авторизация существующих пользователей по Telegram ID с подтверждением через код"""
    # Очистка истекших кодов
    cleanup_expired_codes()
    
    if request.method == 'POST':
        # Проверяем, на каком этапе авторизации мы находимся
        verification_code = request.form.get('verification_code', '').strip()
        telegram_id_str = request.form.get('telegram_id', '').strip()
        
        # Этап 2: Проверка кода подтверждения
        if verification_code and session.get('pending_telegram_id'):
            try:
                telegram_id = session.get('pending_telegram_id')
                
                if verify_code(telegram_id, verification_code):
                    # Код верный - авторизуем пользователя
                    db = get_db()
                    user_service = UserService(db)
                    user = user_service.get_user_by_telegram_id(telegram_id)
                    
                    if user:
                        session['user_logged_in'] = True
                        session['user_id'] = user.id
                        session['user_telegram_id'] = user.telegram_id
                        session['user_name'] = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"Пользователь {user.telegram_id}"
                        session.pop('pending_telegram_id', None)
                        
                        # Если у пользователя нет логина/пароля, предлагаем создать
                        if not user.web_login:
                            db.close()
                            flash(f'Добро пожаловать, {session["user_name"]}!', 'success')
                            return redirect(url_for('user.user_create_credentials'))
                        
                        db.close()
                        flash(f'Добро пожаловать, {session["user_name"]}!', 'success')
                        return redirect(url_for('user.user_profile'))
                    else:
                        db.close()
                        session.pop('pending_telegram_id', None)
                        flash('Пользователь не найден в базе данных', 'error')
                        return redirect(url_for('user.user_register'))
                else:
                    flash('Неверный код подтверждения. Проверьте код в Telegram.', 'error')
                    return render_template('user_login.html', 
                                         telegram_id=telegram_id,
                                         show_code_input=True)
                    
            except Exception as e:
                logger.error(f"Ошибка при проверке кода: {e}")
                flash('Произошла ошибка при проверке кода', 'error')
                session.pop('pending_telegram_id', None)
                return render_template('user_login.html')
        
        # Этап 1: Отправка кода подтверждения
        elif telegram_id_str:
            try:
                try:
                    telegram_id = int(telegram_id_str)
                except ValueError:
                    flash('Telegram ID должен быть числом', 'error')
                    return render_template('user_login.html')
                
                # Поиск пользователя в базе данных
                db = get_db()
                user_service = UserService(db)
                user = user_service.get_user_by_telegram_id(telegram_id)
                
                if not user:
                    db.close()
                    flash('Пользователь с таким Telegram ID не найден. Если вы уже зарегистрированы в боте, проверьте ID. Если нет - зарегистрируйтесь по телефону.', 'warning')
                    return redirect(url_for('user.user_register'))
                
                # Генерируем и отправляем код
                code = generate_verification_code()
                store_verification_code(telegram_id, code)
                
                # Отправляем код в Telegram
                message = f"""🔐 Код подтверждения для входа в личный кабинет

Ваш код: {code}

Код действителен 5 минут.
Никому не сообщайте этот код!"""
                
                # Отправка в отдельном потоке, чтобы не блокировать ответ
                def send_code():
                    try:
                        # Используем прямую отправку через Bot API с HTML
                        import asyncio
                        from telegram import Bot
                        import config
                        
                        async def send_with_html():
                            bot = Bot(token=config.BOT_TOKEN)
                            html_message = f"""🔐 <b>Код подтверждения для входа в личный кабинет</b>

Ваш код: <code>{code}</code>

Код действителен 5 минут.
Никому не сообщайте этот код!"""
                            try:
                                await bot.send_message(
                                    chat_id=telegram_id,
                                    text=html_message,
                                    parse_mode='HTML'
                                )
                                return True
                            except Exception as e:
                                logger.error(f"Ошибка отправки кода с HTML: {e}")
                                # Fallback на обычную отправку
                                await bot.send_message(chat_id=telegram_id, text=message)
                                return True
                        
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            success = loop.run_until_complete(send_with_html())
                            if not success:
                                logger.error(f"Не удалось отправить код пользователю {telegram_id}")
                        finally:
                            loop.close()
                    except Exception as e:
                        logger.error(f"Ошибка отправки кода: {e}")
                        # Fallback на старый метод
                        try:
                            run_notification_sync(telegram_id, message)
                        except:
                            pass
                
                thread = threading.Thread(target=send_code, daemon=True)
                thread.start()
                
                # Сохраняем telegram_id в сессии для следующего шага
                session['pending_telegram_id'] = telegram_id
                db.close()
                
                flash('Код подтверждения отправлен в ваш Telegram. Введите его ниже.', 'info')
                return render_template('user_login.html', 
                                     telegram_id=telegram_id,
                                     show_code_input=True)
                
            except Exception as e:
                logger.error(f"Ошибка при отправке кода: {e}")
                flash('Произошла ошибка при отправке кода подтверждения', 'error')
                return render_template('user_login.html')
        else:
            flash('Введите ваш Telegram ID', 'error')
            return render_template('user_login.html')
    
    # GET запрос - показываем форму
    # Если есть pending_telegram_id, показываем поле для кода
    if session.get('pending_telegram_id'):
        return render_template('user_login.html', 
                             telegram_id=session.get('pending_telegram_id'),
                             show_code_input=True)
    
    return render_template('user_login.html')

@user_bp.route('/show-credentials')
@require_user_login
def user_show_credentials():
    """Показ созданных логина и пароля после регистрации"""
    web_login = session.pop('new_web_login', None)
    web_password = session.pop('new_web_password', None)
    
    if not web_login or not web_password:
        return redirect(url_for('user.user_profile'))
    
    return render_template('user_show_credentials.html', 
                         web_login=web_login, 
                         web_password=web_password)

@user_bp.route('/create-credentials', methods=['GET', 'POST'])
@require_user_login
def user_create_credentials():
    """Создание логина и пароля для пользователей, зарегистрированных через Telegram"""
    if request.method == 'POST':
        try:
            db = get_db()
            user_id = session.get('user_id')
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                flash('Пользователь не найден', 'error')
                db.close()
                return redirect(url_for('user.user_login'))
            
            if user.web_login:
                # У пользователя уже есть логин/пароль
                db.close()
                return redirect(url_for('user.user_profile'))
            
            # Генерируем логин и пароль
            web_login, web_password = generate_web_credentials()
            
            # Проверяем уникальность логина
            while db.query(User).filter(User.web_login == web_login).first():
                web_login, web_password = generate_web_credentials()
            
            user.web_login = web_login
            user.web_password_hash = web_password  # Храним пароль в открытом виде
            
            db.commit()
            db.close()
            
            # Сохраняем для показа
            session['new_web_login'] = web_login
            session['new_web_password'] = web_password
            
            flash('Логин и пароль успешно созданы!', 'success')
            return redirect(url_for('user.user_show_credentials'))
            
        except Exception as e:
            logger.error(f"Ошибка при создании логина/пароля: {e}")
            flash('Произошла ошибка при создании логина и пароля', 'error')
            return render_template('user_create_credentials.html')
    
    return render_template('user_create_credentials.html')

@user_bp.route('/login-password', methods=['GET', 'POST'])
def user_login_password():
    """Вход по логину и паролю"""
    if request.method == 'POST':
        try:
            web_login = request.form.get('web_login', '').strip()
            web_password = request.form.get('web_password', '').strip()
            
            if not web_login or not web_password:
                flash('Введите логин и пароль', 'error')
                return render_template('user_login_password.html')
            
            db = get_db()
            user = db.query(User).filter(User.web_login == web_login).first()
            
            if user and user.web_password_hash and user.web_password_hash == web_password:
                # Авторизуем пользователя
                session['user_logged_in'] = True
                session['user_id'] = user.id
                session['user_telegram_id'] = user.telegram_id
                session['user_name'] = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"Пользователь {user.telegram_id}"
                db.close()
                
                flash(f'Добро пожаловать, {session["user_name"]}!', 'success')
                return redirect(url_for('user.user_profile'))
            else:
                db.close()
                flash('Неверный логин или пароль', 'error')
                return render_template('user_login_password.html')
                
        except Exception as e:
            logger.error(f"Ошибка при входе по логину/паролю: {e}")
            flash('Произошла ошибка при входе', 'error')
            return render_template('user_login_password.html')
    
    return render_template('user_login_password.html')

@user_bp.route('/logout')
def user_logout():
    """Выход пользователя"""
    session.pop('user_logged_in', None)
    session.pop('user_id', None)
    session.pop('user_telegram_id', None)
    session.pop('user_name', None)
    session.pop('pending_telegram_id', None)  # Очищаем pending код при выходе
    session.pop('new_web_login', None)
    session.pop('new_web_password', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('user.user_login'))

@user_bp.route('/profile')
@require_user_login
def user_profile():
    """Профиль пользователя"""
    try:
        db = get_db()
        user_id = session.get('user_id')
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            flash('Пользователь не найден', 'error')
            db.close()
            return redirect(url_for('user.user_login'))
        
        # Получаем статистику
        total_purchases = db.query(Purchase).filter(
            Purchase.user_id == user_id,
            Purchase.is_returned == False
        ).count()
        
        total_spent = user.total_spent or 0
        
        # Последние покупки
        recent_purchases = db.query(Purchase).filter(
            Purchase.user_id == user_id,
            Purchase.is_returned == False
        ).order_by(Purchase.purchase_date.desc()).limit(5).all()
        
        # История баллов
        recent_points = db.query(PointsHistory).filter(
            PointsHistory.user_id == user_id
        ).order_by(PointsHistory.created_date.desc()).limit(10).all()
        
        # Реферальная статистика
        referrals_count = db.query(User).filter(User.referred_by == user_id).count()
        referrals = db.query(User).filter(User.referred_by == user_id).all()
        
        # Реферальная ссылка
        referral_link = request.url_root.rstrip('/') + url_for('user.user_register', ref=user.referral_code)
        
        # Проверяем активный розыгрыш
        loyalty_service = LoyaltyService(db)
        active_giveaway = loyalty_service.get_active_giveaway()
        is_participant_in_giveaway = False
        if active_giveaway:
            participant = db.query(GiveawayParticipant).filter(
                GiveawayParticipant.giveaway_id == active_giveaway.id,
                GiveawayParticipant.user_id == user_id
            ).first()
            is_participant_in_giveaway = participant is not None
        
        db.close()
        
        return render_template('user_profile.html', 
                             user=user,
                             total_purchases=total_purchases,
                             total_spent=total_spent,
                             recent_purchases=recent_purchases,
                             recent_points=recent_points,
                             referrals_count=referrals_count,
                             referrals=referrals,
                             referral_link=referral_link,
                             active_giveaway=active_giveaway,
                             is_participant=is_participant_in_giveaway)
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке профиля: {e}")
        flash('Ошибка при загрузке профиля', 'error')
        return redirect(url_for('user.user_login'))

@user_bp.route('/referral-top')
@require_user_login
def user_referral_top():
    """Топ рефералов для пользователей"""
    try:
        db = get_db()
        user_id = session.get('user_id')
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            flash('Пользователь не найден', 'error')
            db.close()
            return redirect(url_for('user.user_login'))
        
        loyalty_service = LoyaltyService(db)
        
        # Получаем топ 10 рефералов
        top_referrals = loyalty_service.get_referral_top(limit=10)
        
        # Получаем позицию текущего пользователя
        user_position = loyalty_service.get_user_referral_position(user_id)
        
        db.close()
        
        return render_template('user_referral_top.html', 
                             top_referrals=top_referrals,
                             user_position=user_position,
                             current_user_id=user_id)
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке топа рефералов: {e}", exc_info=True)
        flash('Ошибка при загрузке топа рефералов', 'error')
        try:
            if 'db' in locals():
                db.close()
        except:
            pass
        return redirect(url_for('user.user_profile'))

@user_bp.route('/points')
@require_user_login
def user_points():
    """История баллов пользователя"""
    try:
        db = get_db()
        user_id = session.get('user_id')
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            flash('Пользователь не найден', 'error')
            db.close()
            return redirect(url_for('user.user_login'))
        
        # Полная история баллов
        points_history = db.query(PointsHistory).filter(
            PointsHistory.user_id == user_id
        ).order_by(PointsHistory.created_date.desc()).all()
        
        db.close()
        
        return render_template('user_points.html', 
                             user=user,
                             points_history=points_history)
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке истории баллов: {e}")
        flash('Ошибка при загрузке истории баллов', 'error')
        return redirect(url_for('user.user_profile'))

@user_bp.route('/purchases')
@require_user_login
def user_purchases():
    """История покупок пользователя"""
    try:
        db = get_db()
        user_id = session.get('user_id')
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            flash('Пользователь не найден', 'error')
            db.close()
            return redirect(url_for('user.user_login'))
        
        # Все покупки
        purchases = db.query(Purchase).filter(
            Purchase.user_id == user_id,
            Purchase.is_returned == False
        ).order_by(Purchase.purchase_date.desc()).all()
        
        db.close()
        
        return render_template('user_purchases.html', 
                             user=user,
                             purchases=purchases)
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке истории покупок: {e}")
        flash('Ошибка при загрузке истории покупок', 'error')
        return redirect(url_for('user.user_profile'))

@user_bp.route('/qr')
@require_user_login
def user_qr():
    """QR-код пользователя для сканирования"""
    try:
        db = get_db()
        user_id = session.get('user_id')
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            flash('Пользователь не найден', 'error')
            db.close()
            return redirect(url_for('user.user_login'))
        
        db.close()
        
        return render_template('user_qr.html', user=user)
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке QR-кода: {e}")
        flash('Ошибка при загрузке QR-кода', 'error')
        return redirect(url_for('user.user_profile'))

@user_bp.route('/qr/image')
@require_user_login
def user_qr_image():
    """Генерация QR-кода на сервере (изображение)"""
    try:
        db = get_db()
        user_id = session.get('user_id')
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            db.close()
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        # Генерируем QR-код на сервере
        qr_image_bytes = QRService.generate_user_qr(user.id, user.telegram_id)
        
        db.close()
        
        # Возвращаем изображение
        return send_file(
            BytesIO(qr_image_bytes),
            mimetype='image/png',
            as_attachment=False
        )
        
    except Exception as e:
        logger.error(f"Ошибка при генерации QR-кода: {e}")
        return jsonify({'error': 'Ошибка генерации QR-кода'}), 500

@user_bp.route('/giveaway')
@require_user_login
def user_giveaway():
    """Страница розыгрыша для пользователей"""
    db = None
    try:
        logger.info(f"Запрос страницы розыгрыша от user_id={session.get('user_id')}")
        db = get_db()
        user_id = session.get('user_id')
        
        if not user_id:
            logger.warning("user_id не найден в сессии")
            flash('Ошибка авторизации', 'error')
            if db:
                db.close()
            return redirect(url_for('user.user_login'))
        
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            logger.warning(f"Пользователь с user_id={user_id} не найден в БД")
            flash('Пользователь не найден', 'error')
            if db:
                db.close()
            return redirect(url_for('user.user_login'))
        
        loyalty_service = LoyaltyService(db)
        
        # Получаем активный розыгрыш
        giveaway = loyalty_service.get_active_giveaway()
        logger.info(f"Активный розыгрыш: {giveaway.id if giveaway else None}")
        
        # Проверяем, участвует ли пользователь
        is_participant = False
        if giveaway:
            participant = db.query(GiveawayParticipant).filter(
                GiveawayParticipant.giveaway_id == giveaway.id,
                GiveawayParticipant.user_id == user_id
            ).first()
            is_participant = participant is not None
        
        # Получаем топ розыгрыша
        giveaway_top = []
        user_position = None
        if giveaway:
            giveaway_top = loyalty_service.get_giveaway_top(giveaway.id, limit=10)
            user_position = loyalty_service.get_giveaway_user_position(giveaway.id, user_id)
            logger.info(
                "Топ розыгрыша: %s участников, позиция пользователя: %s",
                len(giveaway_top),
                user_position.get("position") if isinstance(user_position, dict) else "не участвует"
            )
        
        if db:
            db.close()
        
        logger.info(f"Рендеринг user_giveaway.html: giveaway={giveaway is not None}, is_participant={is_participant}, top_count={len(giveaway_top)}")
        
        return render_template('user_giveaway.html',
                             giveaway=giveaway,
                             is_participant=is_participant,
                             giveaway_top=giveaway_top,
                             user_position=user_position,
                             current_user_id=user_id)
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке розыгрыша: {e}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash(f'Ошибка при загрузке розыгрыша: {str(e)}', 'error')
        try:
            if 'db' in locals():
                db.close()
        except:
            pass
        return redirect(url_for('user.user_profile'))

@user_bp.route('/giveaway/join', methods=['POST'])
@require_user_login
def user_giveaway_join():
    """Участие в розыгрыше"""
    try:
        db = get_db()
        user_id = session.get('user_id')
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            db.close()
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        loyalty_service = LoyaltyService(db)
        giveaway, message = loyalty_service.join_active_giveaway(user_id)
        
        db.close()
        
        if giveaway:
            return jsonify({
                'success': True,
                'message': message,
                'giveaway_id': giveaway.id
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        logger.error(f"Ошибка при участии в розыгрыше: {e}", exc_info=True)
        try:
            if 'db' in locals():
                db.close()
        except:
            pass
        return jsonify({'error': 'Ошибка сервера'}), 500
