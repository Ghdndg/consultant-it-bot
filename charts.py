import matplotlib
matplotlib.use('Agg')  # Устанавливаем backend для работы без GUI
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import calendar
import io
from database import get_db, User, Purchase, PointsHistory
from sqlalchemy import func, extract
import matplotlib.dates as mdates
from collections import defaultdict
import numpy as np

# Настройка matplotlib для русского языка
plt.rcParams['font.family'] = ['DejaVu Sans', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# Русские названия месяцев
RUSSIAN_MONTHS = {
    1: 'Янв', 2: 'Фев', 3: 'Мар', 4: 'Апр', 5: 'Май', 6: 'Июн',
    7: 'Июл', 8: 'Авг', 9: 'Сен', 10: 'Окт', 11: 'Ноя', 12: 'Дек'
}

# Настройка стиля
sns.set_style("whitegrid")
sns.set_palette("husl")

def generate_monthly_stats_chart():
    """Генерирует график статистики по месяцам"""
    db = get_db()
    
    try:
        # Получаем данные начиная с мая 2025 года
        current_date = datetime.now()
        start_date = datetime(2025, 5, 1)  # Начинаем с 1 мая 2025 года
        
        # Данные по регистрациям
        registrations = db.query(
            extract('year', User.registration_date).label('year'),
            extract('month', User.registration_date).label('month'),
            func.count(User.id).label('count')
        ).filter(
            User.registration_date >= start_date
        ).group_by(
            extract('year', User.registration_date),
            extract('month', User.registration_date)
        ).all()
        
        # Данные по покупкам
        purchases = db.query(
            extract('year', Purchase.purchase_date).label('year'),
            extract('month', Purchase.purchase_date).label('month'),
            func.count(Purchase.id).label('count'),
            func.sum(Purchase.amount).label('total')
        ).filter(
            Purchase.purchase_date >= start_date
        ).group_by(
            extract('year', Purchase.purchase_date),
            extract('month', Purchase.purchase_date)
        ).all()
        
        # Данные по баллам
        points_stats = db.query(
            extract('year', PointsHistory.created_date).label('year'),
            extract('month', PointsHistory.created_date).label('month'),
            func.sum(PointsHistory.points_change).filter(PointsHistory.points_change > 0).label('earned'),
            func.sum(PointsHistory.points_change).filter(PointsHistory.transaction_type == 'redemption').label('redeemed'),
            func.sum(PointsHistory.points_change).filter(
                PointsHistory.points_change < 0,
                PointsHistory.transaction_type != 'redemption'
            ).label('returned')
        ).filter(
            PointsHistory.created_date >= start_date
        ).group_by(
            extract('year', PointsHistory.created_date),
            extract('month', PointsHistory.created_date)
        ).all()
        
        # Подготовка данных для графика (от мая 2025 до текущего месяца)
        months = []
        current_year = start_date.year
        current_month = start_date.month
        
        while datetime(current_year, current_month, 1) <= current_date:
            months.append((current_year, current_month))
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1
        
        month_labels = []
        reg_data = []
        purchase_data = []
        revenue_data = []
        points_earned_data = []
        points_redeemed_data = []
        points_returned_data = []
        
        for year, month in months:
            month_labels.append(f"{RUSSIAN_MONTHS[month]} {year}")
            
            # Регистрации
            reg_count = next((r.count for r in registrations if r.year == year and r.month == month), 0)
            reg_data.append(reg_count)
            
            # Покупки
            purchase_count = next((p.count for p in purchases if p.year == year and p.month == month), 0)
            purchase_data.append(purchase_count)
            
            # Выручка
            revenue = next((p.total for p in purchases if p.year == year and p.month == month), 0)
            revenue_data.append(float(revenue or 0))
            
            # Баллы
            points_earned = next((p.earned for p in points_stats if p.year == year and p.month == month), 0)
            points_redeemed = next((p.redeemed for p in points_stats if p.year == year and p.month == month), 0)
            points_returned = next((p.returned for p in points_stats if p.year == year and p.month == month), 0)
            points_earned_data.append(int(points_earned or 0))
            points_redeemed_data.append(int(abs(points_redeemed or 0)))
            points_returned_data.append(int(abs(points_returned or 0)))
        
        # Создание графика
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('📊 Статистика по месяцам', fontsize=16, fontweight='bold')
        
        # График 1: Регистрации
        ax1.plot(month_labels, reg_data, marker='o', linewidth=2, markersize=6, color='#1f77b4')
        ax1.set_title('👥 Новые регистрации', fontweight='bold')
        ax1.set_ylabel('Количество')
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='x', rotation=45)
        
        # График 2: Покупки
        ax2.plot(month_labels, purchase_data, marker='s', linewidth=2, markersize=6, color='#ff7f0e')
        ax2.set_title('🛒 Количество покупок', fontweight='bold')
        ax2.set_ylabel('Количество')
        ax2.grid(True, alpha=0.3)
        ax2.tick_params(axis='x', rotation=45)
        
        # График 3: Выручка
        ax3.bar(month_labels, revenue_data, color='#2ca02c', alpha=0.7)
        ax3.set_title('💰 Выручка (₽)', fontweight='bold')
        ax3.set_ylabel('Рубли')
        ax3.grid(True, alpha=0.3)
        ax3.tick_params(axis='x', rotation=45)
        
        # График 4: Баллы
        width = 0.25
        x = np.arange(len(month_labels))
        ax4.bar(x - width, points_earned_data, width, label='Начислено', color='#2ca02c', alpha=0.7)
        ax4.bar(x, points_redeemed_data, width, label='Списанные', color='#d62728', alpha=0.7)
        ax4.bar(x + width, points_returned_data, width, label='Возвращенные', color='#ff7f0e', alpha=0.7)
        ax4.set_title('🎁 Баллы', fontweight='bold')
        ax4.set_ylabel('Баллы')
        ax4.set_xticks(x)
        ax4.set_xticklabels(month_labels, rotation=45)
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Сохранение в буфер
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        
        return buffer
        
    except Exception as e:
        print(f"Ошибка генерации графика: {e}")
        return None
    finally:
        db.close()

def generate_users_growth_chart():
    """Генерирует график роста пользователей"""
    db = get_db()
    
    try:
        current_date = datetime.now()
        start_date = current_date - timedelta(days=365)
        
        # Получаем регистрации по дням за последний год
        daily_registrations = db.query(
            func.date(User.registration_date).label('date'),
            func.count(User.id).label('count')
        ).filter(
            User.registration_date >= start_date
        ).group_by(
            func.date(User.registration_date)
        ).order_by(
            func.date(User.registration_date)
        ).all()
        
        # Подготовка данных
        dates = []
        counts = []
        cumulative = []
        total = 0
        
        for reg in daily_registrations:
            dates.append(reg.date)
            counts.append(reg.count)
            total += reg.count
            cumulative.append(total)
        
        # Создание графика
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        fig.suptitle('📈 Рост пользователей', fontsize=16, fontweight='bold')
        
        # График 1: Ежедневные регистрации
        ax1.plot(dates, counts, marker='o', linewidth=1, markersize=3, color='#1f77b4', alpha=0.7)
        ax1.fill_between(dates, counts, alpha=0.3, color='#1f77b4')
        ax1.set_title('👥 Ежедневные регистрации', fontweight='bold')
        ax1.set_ylabel('Новых пользователей в день')
        ax1.grid(True, alpha=0.3)
        
        # График 2: Кумулятивный рост
        ax2.plot(dates, cumulative, linewidth=3, color='#2ca02c')
        ax2.fill_between(dates, cumulative, alpha=0.3, color='#2ca02c')
        ax2.set_title('📊 Общий рост пользователей', fontweight='bold')
        ax2.set_ylabel('Общее количество')
        ax2.set_xlabel('Дата')
        ax2.grid(True, alpha=0.3)
        
        # Форматирование дат
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
            ax.xaxis.set_major_locator(mdates.MonthLocator())
            ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        
        # Сохранение в буфер
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        
        return buffer
        
    except Exception as e:
        print(f"Ошибка генерации графика роста: {e}")
        return None
    finally:
        db.close()

def generate_revenue_analysis_chart():
    """Генерирует детальный анализ выручки"""
    db = get_db()
    
    try:
        current_date = datetime.now()
        start_date = current_date - timedelta(days=365)
        
        # Данные по месяцам
        monthly_revenue = db.query(
            extract('year', Purchase.purchase_date).label('year'),
            extract('month', Purchase.purchase_date).label('month'),
            func.sum(Purchase.amount).label('revenue'),
            func.avg(Purchase.amount).label('avg_purchase'),
            func.count(Purchase.id).label('purchases')
        ).filter(
            Purchase.purchase_date >= start_date
        ).group_by(
            extract('year', Purchase.purchase_date),
            extract('month', Purchase.purchase_date)
        ).order_by(
            extract('year', Purchase.purchase_date),
            extract('month', Purchase.purchase_date)
        ).all()
        
        # Подготовка данных
        months = []
        revenue_data = []
        avg_purchase_data = []
        purchase_count_data = []
        
        for rev in monthly_revenue:
            months.append(f"{RUSSIAN_MONTHS[int(rev.month)]} {int(rev.year)}")
            revenue_data.append(float(rev.revenue or 0))
            avg_purchase_data.append(float(rev.avg_purchase or 0))
            purchase_count_data.append(int(rev.purchases or 0))
        
        # Создание графика
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('💰 Анализ выручки', fontsize=16, fontweight='bold')
        
        # График 1: Месячная выручка
        bars1 = ax1.bar(months, revenue_data, color='#2ca02c', alpha=0.7)
        ax1.set_title('💰 Выручка по месяцам', fontweight='bold')
        ax1.set_ylabel('Рубли')
        ax1.tick_params(axis='x', rotation=45)
        ax1.grid(True, alpha=0.3)
        
        # Добавляем значения на столбцы
        for bar in bars1:
            height = bar.get_height()
            if height > 0:
                ax1.annotate(f'{height:.0f}₽', 
                           xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 3), textcoords="offset points",
                           ha='center', va='bottom', fontsize=8)
        
        # График 2: Средний чек
        ax2.plot(months, avg_purchase_data, marker='o', linewidth=2, markersize=6, color='#ff7f0e')
        ax2.set_title('💳 Средний чек', fontweight='bold')
        ax2.set_ylabel('Рубли')
        ax2.tick_params(axis='x', rotation=45)
        ax2.grid(True, alpha=0.3)
        
        # График 3: Количество покупок
        bars3 = ax3.bar(months, purchase_count_data, color='#1f77b4', alpha=0.7)
        ax3.set_title('🛒 Количество покупок', fontweight='bold')
        ax3.set_ylabel('Покупки')
        ax3.tick_params(axis='x', rotation=45)
        ax3.grid(True, alpha=0.3)
        
        # График 4: Эффективность (выручка на покупку)
        efficiency = [r/p if p > 0 else 0 for r, p in zip(revenue_data, purchase_count_data)]
        ax4.plot(months, efficiency, marker='s', linewidth=2, markersize=6, color='#d62728')
        ax4.set_title('📈 Выручка на покупку', fontweight='bold')
        ax4.set_ylabel('Рубли/покупка')
        ax4.tick_params(axis='x', rotation=45)
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Сохранение в буфер
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        
        return buffer
        
    except Exception as e:
        print(f"Ошибка генерации анализа выручки: {e}")
        return None
    finally:
        db.close()

def generate_points_analytics_chart():
    """Генерирует анализ программы лояльности"""
    db = get_db()
    
    try:
        current_date = datetime.now()
        start_date = current_date - timedelta(days=365)
        
        # Данные по баллам
        points_data = db.query(
            extract('year', PointsHistory.created_date).label('year'),
            extract('month', PointsHistory.created_date).label('month'),
            func.sum(PointsHistory.points_change).filter(PointsHistory.points_change > 0).label('earned'),
            func.sum(PointsHistory.points_change).filter(PointsHistory.transaction_type == 'redemption').label('spent'),
            func.sum(PointsHistory.points_change).filter(
                PointsHistory.points_change < 0,
                PointsHistory.transaction_type != 'redemption'
            ).label('returned'),
            func.count(PointsHistory.id).filter(PointsHistory.points_change > 0).label('earn_transactions'),
            func.count(PointsHistory.id).filter(PointsHistory.transaction_type == 'redemption').label('spend_transactions')
        ).filter(
            PointsHistory.created_date >= start_date
        ).group_by(
            extract('year', PointsHistory.created_date),
            extract('month', PointsHistory.created_date)
        ).order_by(
            extract('year', PointsHistory.created_date),
            extract('month', PointsHistory.created_date)
        ).all()
        
        # Подготовка данных
        months = []
        earned_data = []
        spent_data = []
        net_data = []
        
        for points in points_data:
            months.append(f"{RUSSIAN_MONTHS[int(points.month)]} {int(points.year)}")
            earned = int(points.earned or 0)
            spent = abs(int(points.spent or 0))
            
            earned_data.append(earned)
            spent_data.append(spent)
            net_data.append(earned - spent)
        
        # Создание графика
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('🎁 Анализ программы лояльности', fontsize=16, fontweight='bold')
        
        # График 1: Начисления vs Списания
        width = 0.35
        x = np.arange(len(months))
        bars1 = ax1.bar(x - width/2, earned_data, width, label='Начислено', color='#2ca02c', alpha=0.7)
        bars2 = ax1.bar(x + width/2, spent_data, width, label='Списанные баллы', color='#d62728', alpha=0.7)
        
        ax1.set_title('🎁 Начисления vs Списанные баллы', fontweight='bold')
        ax1.set_ylabel('Баллы')
        ax1.set_xticks(x)
        ax1.set_xticklabels(months, rotation=45)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # График 2: Чистый прирост баллов
        colors = ['#2ca02c' if val >= 0 else '#d62728' for val in net_data]
        bars3 = ax2.bar(months, net_data, color=colors, alpha=0.7)
        ax2.set_title('📊 Чистый прирост баллов', fontweight='bold')
        ax2.set_ylabel('Баллы')
        ax2.tick_params(axis='x', rotation=45)
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        
        # График 3: Накопительная статистика
        cumulative_earned = np.cumsum(earned_data)
        cumulative_spent = np.cumsum(spent_data)
        
        ax3.plot(months, cumulative_earned, marker='o', linewidth=2, label='Накопительно начислено', color='#2ca02c')
        ax3.plot(months, cumulative_spent, marker='s', linewidth=2, label='Накопительно списано', color='#d62728')
        ax3.set_title('📈 Накопительная статистика', fontweight='bold')
        ax3.set_ylabel('Баллы')
        ax3.tick_params(axis='x', rotation=45)
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # График 4: Эффективность программы лояльности
        effectiveness = [(e - s) / e * 100 if e > 0 else 0 for e, s in zip(earned_data, spent_data)]
        ax4.plot(months, effectiveness, marker='D', linewidth=2, markersize=6, color='#ff7f0e')
        ax4.set_title('💯 Эффективность программы (%)', fontweight='bold')
        ax4.set_ylabel('Процент неиспользованных баллов')
        ax4.tick_params(axis='x', rotation=45)
        ax4.grid(True, alpha=0.3)
        ax4.axhline(y=50, color='red', linestyle='--', alpha=0.5, label='50% линия')
        ax4.legend()
        
        plt.tight_layout()
        
        # Сохранение в буфер
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        
        return buffer
        
    except Exception as e:
        print(f"Ошибка генерации анализа лояльности: {e}")
        return None
    finally:
        db.close()

def generate_points_chart():
    """Генерирует график по баллам"""
    db = get_db()
    
    try:
        # Получаем данные начиная с мая 2025 года
        current_date = datetime.now()
        start_date = datetime(2025, 5, 1)  # Начинаем с 1 мая 2025 года
        
        # Данные по баллам
        points_stats = db.query(
            extract('year', PointsHistory.created_date).label('year'),
            extract('month', PointsHistory.created_date).label('month'),
            func.sum(PointsHistory.points_change).filter(PointsHistory.points_change > 0).label('earned'),
            func.sum(PointsHistory.points_change).filter(PointsHistory.transaction_type == 'redemption').label('redeemed'),
            func.sum(PointsHistory.points_change).filter(
                PointsHistory.points_change < 0,
                PointsHistory.transaction_type != 'redemption'
            ).label('returned')
        ).filter(
            PointsHistory.created_date >= start_date
        ).group_by(
            extract('year', PointsHistory.created_date),
            extract('month', PointsHistory.created_date)
        ).all()
        
        # Подготовка данных (от мая 2025 до текущего месяца)
        months = []
        current_year = start_date.year
        current_month = start_date.month
        
        while datetime(current_year, current_month, 1) <= current_date:
            months.append((current_year, current_month))
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1
        
        month_labels = []
        points_earned_data = []
        points_redeemed_data = []
        points_returned_data = []
        
        for year, month in months:
            month_labels.append(f"{RUSSIAN_MONTHS[month]} {year}")
            
            # Баллы
            points_earned = next((p.earned for p in points_stats if p.year == year and p.month == month), 0)
            points_redeemed = next((p.redeemed for p in points_stats if p.year == year and p.month == month), 0)
            points_returned = next((p.returned for p in points_stats if p.year == year and p.month == month), 0)
            points_earned_data.append(int(points_earned or 0))
            points_redeemed_data.append(int(abs(points_redeemed or 0)))
            points_returned_data.append(int(abs(points_returned or 0)))
        
        # Создание графика
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 12))
        fig.suptitle('🎁 Статистика баллов', fontsize=16, fontweight='bold')
        
        # График 1: Начисления vs Списания vs Возвраты
        width = 0.25
        x = np.arange(len(month_labels))
        ax1.bar(x - width, points_earned_data, width, label='Начислено', color='#2ca02c', alpha=0.7)
        ax1.bar(x, points_redeemed_data, width, label='Списанные баллы', color='#d62728', alpha=0.7)
        ax1.bar(x + width, points_returned_data, width, label='Возвращенные баллы', color='#ff7f0e', alpha=0.7)
        ax1.set_title('🎁 Начисления vs Списания vs Возвраты', fontweight='bold')
        ax1.set_ylabel('Баллы')
        ax1.set_xticks(x)
        ax1.set_xticklabels(month_labels, rotation=45)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # График 2: Чистый прирост
        net_points = [e - r - ret for e, r, ret in zip(points_earned_data, points_redeemed_data, points_returned_data)]
        colors = ['#2ca02c' if val >= 0 else '#d62728' for val in net_points]
        ax2.bar(month_labels, net_points, color=colors, alpha=0.7)
        ax2.set_title('📊 Чистый прирост баллов', fontweight='bold')
        ax2.set_ylabel('Баллы')
        ax2.tick_params(axis='x', rotation=45)
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        
        plt.tight_layout()
        
        # Сохранение в буфер
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        
        return buffer
        
    except Exception as e:
        print(f"Ошибка генерации графика баллов: {e}")
        return None
    finally:
        db.close() 