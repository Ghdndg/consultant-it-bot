# Consultant-IT Bot

Самостоятельный backend для ассистента consultant-it.ru и готовый JS-виджет для встраивания на любой лендинг.

## Состав

- `server.js` — Express-приложение с маршрутами `POST /api/chat`, `GET /api/health`, `GET /api/stats`, проксирующее запросы к Google Gemini.
- `public/widget.js` — автономный фронтенд-виджет (кнопка + окно чата), который отправляет запросы на настроенный API.
- `.env.example` — образец переменных окружения.
- `.eslintrc.cjs`, `package.json` — конфигурация линтера и зависимостей.

## Требования

- Node.js 18+ (поддержка fetch и AbortController на сервере).
- Действующий API-ключ Google Gemini (через Google AI Studio).

## Настройка backend

```bash
cd consultant-it-bot
cp .env.example .env            # заполните GEMINI_API_KEY и список доменов
npm install
npm run dev                     # запуск с hot-reload через nodemon
# либо npm start для продакшена
```

Переменные окружения:

| Переменная          | Значение                                               |
|---------------------|--------------------------------------------------------|
| `GEMINI_API_KEY`    | Ключ Gemini (обязательно)                              |
| `PORT`              | Порт сервера (по умолчанию 4000)                       |
| `GEMINI_MODEL`      | Модель Gemini (`gemini-1.5-flash`, `gemini-1.5-pro`…)  |
| `ALLOWED_ORIGINS`   | Список доменов через запятую для CORS                  |
| `ENABLE_LOGS`       | `true/false` для включения morgan                      |

### Эндпойнты

- `POST /api/chat` — принимает `{ message, sessionId?, metadata? }`, возвращает `{ message, sessionId, suggestions, metadata }`.
- `GET /api/health` — проверка готовности.
- `GET /api/stats` — простая статистика с момента запуска.

## Деплой

1. Залить код на сервер (VPS).
2. Настроить `pm2`/`systemd` для `npm start`.
3. Пробросить HTTPS (например, nginx → `http://127.0.0.1:4000`).

Пример блока nginx:

```
location /api/ {
  proxy_pass http://127.0.0.1:4000/api/;
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-Proto $scheme;
}
```

## Встраивание виджета

1. Раздайте `public/widget.js` со своего CDN/серверa (или подключите через `express.static`).
2. Добавьте на лендинг:

```html
<script
  src="https://api.consultant-it.ru/widget.js"
  data-api-url="https://api.consultant-it.ru/api/chat"
  data-brand="Consultant-IT"
  data-accent="#00e0ff"
  defer
></script>
```

Параметры:

- `data-api-url` — URL вашего backend-а.
- `data-brand` — подпись в шапке.
- `data-accent` — основной цвет градиента (hex).

## Тестирование

1. `npm run dev` — локальный запуск.
2. В браузере открыть `index.html` (лендинг) с подключённым `widget.js`, убедиться, что сообщения отправляются.
3. Проверить `/api/health` и `/api/stats` в браузере или через `curl`.

## TODO / идеи развития

- Подключить постоянное хранилище истории (Redis, PostgreSQL).
- Добавить очередь запросов к Gemini и кэширование FAQ.
- Реализовать быстрые ответы и индикатор набора в API.

