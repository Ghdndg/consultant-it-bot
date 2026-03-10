#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для создания иконок PWA из существующего favicon.ico
Требуется: pip install Pillow
"""

from PIL import Image
import os

def create_pwa_icons():
    """Создание иконок для PWA из favicon.ico"""
    
    favicon_path = 'static/favicon.ico'
    
    if not os.path.exists(favicon_path):
        print(f"Ошибка: файл {favicon_path} не найден!")
        print("Создайте favicon.ico в папке static/ или используйте существующий")
        return False
    
    try:
        # Открываем исходную иконку
        img = Image.open(favicon_path)
        
        # Конвертируем в RGBA если нужно
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Создаем иконки разных размеров
        sizes = [192, 512]
        
        for size in sizes:
            # Масштабируем с сохранением пропорций
            icon = img.resize((size, size), Image.Resampling.LANCZOS)
            
            # Создаем квадратную иконку с прозрачным фоном
            square_icon = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            
            # Вставляем иконку по центру
            if icon.width > icon.height:
                new_height = size
                new_width = int(icon.width * (size / icon.height))
                icon = icon.resize((new_width, new_height), Image.Resampling.LANCZOS)
                x_offset = (size - new_width) // 2
                square_icon.paste(icon, (x_offset, 0), icon)
            elif icon.height > icon.width:
                new_width = size
                new_height = int(icon.height * (size / icon.width))
                icon = icon.resize((new_width, new_height), Image.Resampling.LANCZOS)
                y_offset = (size - new_height) // 2
                square_icon.paste(icon, (0, y_offset), icon)
            else:
                square_icon.paste(icon, (0, 0), icon)
            
            # Сохраняем
            output_path = f'static/icon-{size}.png'
            square_icon.save(output_path, 'PNG')
            print(f"✓ Создана иконка: {output_path} ({size}x{size})")
        
        print("\n✅ Иконки PWA созданы успешно!")
        print("\nТеперь пользователи iPhone смогут добавить сайт на главный экран:")
        print("1. Открыть сайт в Safari")
        print("2. Нажать кнопку 'Поделиться' (квадрат со стрелкой)")
        print("3. Выбрать 'На экран «Домой»'")
        
        return True
        
    except Exception as e:
        print(f"Ошибка при создании иконок: {e}")
        return False

if __name__ == '__main__':
    print("Создание иконок для PWA...")
    print("=" * 50)
    create_pwa_icons()
