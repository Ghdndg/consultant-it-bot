require('dotenv').config();

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const { nanoid } = require('nanoid');
const { GoogleGenerativeAI } = require('@google/generative-ai');

const PORT = process.env.PORT || 4000;
const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-1.5-flash';
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || '';
const ENABLE_LOGS = process.env.ENABLE_LOGS !== 'false';

const allowedOrigins = (process.env.ALLOWED_ORIGINS || '')
  .split(',')
  .map((origin) => origin.trim())
  .filter(Boolean);

const app = express();

app.use(helmet());
app.use(cors({
  origin: (origin, callback) => {
    if (!origin || allowedOrigins.length === 0 || allowedOrigins.includes(origin)) {
      return callback(null, true);
    }
    return callback(new Error('Origin not allowed by CORS'), false);
  }
}));
app.use(express.json({ limit: '2mb' }));
if (ENABLE_LOGS) {
  app.use(morgan('combined'));
}

const stats = {
  startTime: Date.now(),
  totalRequests: 0,
  totalTokens: 0,
  sessions: {}
};

let genAI = null;
if (GEMINI_API_KEY) {
  genAI = new GoogleGenerativeAI(GEMINI_API_KEY);
} else {
  console.warn('[consultant-it-bot] GEMINI_API_KEY не задан, ответы будут заглушками.');
}

const baseSystemPrompt = `
Вы — вежливый и компетентный виртуальный ассистент компании "ИТ-Консультант" (https://consultant-it.ru).
Главная задача — помогать бизнесу в Крыму с ИТ-вопросами: системная интеграция, абонентская поддержка, цифровой маркетинг, юридическое сопровождение.

Правила:
- Общайтесь на русском языке, дружелюбно и по существу.
- Если вопрос вне тематики услуг компании, мягко возвращайте разговор к нашей экспертизе.
- Предлагайте записаться на консультацию, если вопрос требует оценки или внедрения.
- Уточняйте детали (кол-во сотрудников, инфраструктура и т.п.), если это помогает дать релевантный ответ.
- Не выдумывайте факты. Если нет данных — так и скажите, предложив связаться с менеджером.
`;

function buildUserPrompt(message, metadata = {}) {
  const info = [];
  if (metadata.context) info.push(`Контекст пользователя: ${metadata.context}`);
  if (metadata.page) info.push(`Открытая страница: ${metadata.page}`);
  if (metadata.previousTopic) info.push(`Предыдущая тема: ${metadata.previousTopic}`);
  const prefix = info.length ? `${info.join('\n')}\n\n` : '';
  return `${prefix}Сообщение клиента: ${message}`;
}

async function askGemini({ message, metadata }) {
  if (!genAI) {
    return 'Бот временно недоступен. Пожалуйста, попробуйте позже или свяжитесь с менеджером по телефону.';
  }

  const model = genAI.getGenerativeModel({
    model: GEMINI_MODEL,
    systemInstruction: baseSystemPrompt
  });

  const result = await model.generateContent({
    contents: [
      {
        role: 'user',
        parts: [{ text: buildUserPrompt(message, metadata) }]
      }
    ]
  });

  const responseText = result.response.text();
  stats.totalTokens += result.response?.usageMetadata?.totalTokenCount || 0;
  return responseText?.trim() || 'Ответ пуст';
}

app.get('/api/health', (_req, res) => {
  res.json({
    status: 'ok',
    uptime: process.uptime(),
    hasApiKey: Boolean(GEMINI_API_KEY)
  });
});

app.get('/api/stats', (_req, res) => {
  res.json({
    ...stats,
    uptime: Date.now() - stats.startTime
  });
});

app.post('/api/chat', async (req, res) => {
  const { message, sessionId, metadata = {} } = req.body || {};

  if (!message || typeof message !== 'string') {
    return res.status(400).json({ error: 'Поле message обязательно' });
  }

  const safeSessionId = sessionId || `session-${nanoid(8)}`;
  stats.totalRequests += 1;
  stats.sessions[safeSessionId] = {
    lastMessageAt: Date.now(),
    messages: (stats.sessions[safeSessionId]?.messages || 0) + 1
  };

  try {
    const reply = await askGemini({ message, metadata });
    res.json({
      message: reply,
      sessionId: safeSessionId,
      source: genAI ? 'gemini' : 'fallback',
      metadata: {
        responseAt: Date.now(),
        usage: stats.sessions[safeSessionId]
      },
      suggestions: [
        'Какие услуги вы оказываете?',
        'Сколько стоит абонентская поддержка?',
        'Как быстро подключите инженера?'
      ]
    });
  } catch (error) {
    console.error('[consultant-it-bot] Ошибка при обращении к Gemini:', error);
    res.status(502).json({
      error: 'Не удалось получить ответ от ассистента. Попробуйте ещё раз чуть позже.'
    });
  }
});

const server = app.listen(PORT, () => {
  console.log(`[consultant-it-bot] Сервер запущен на http://localhost:${PORT}`);
});

process.on('SIGINT', () => {
  console.log('\n[consultant-it-bot] Выключение...');
  server.close(() => process.exit(0));
});

