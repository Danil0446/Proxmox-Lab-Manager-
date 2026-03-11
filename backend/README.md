# Backend (FastAPI) for Student Stands

## Как запустить

1. Перейти в папку backend:

```bash
cd backend
```

2. Установить зависимости (рекомендуется виртуальное окружение):

```bash
pip install -r requirements.txt
```

3. Запустить сервер:

```bash
python main.py
uvicorn app.main:app --reload
```

Сервер по умолчанию поднимается на `http://localhost:8000`.

## Основные эндпоинты

- `POST /auth/login` — логин администратора
  - Тело: `{ "username": "admin", "password": "admin123" }`
  - Ответ: `{ "token": "..." }`

- `GET /students` — список студентов и статусы их стендов
- `POST /stands/start` — запустить стенды для списка студентов
  - Тело: `{ "studentIds": [1, 2, 3] }`
- `POST /stands/stop` — выключить стенды для списка студентов
  - Тело: `{ "studentIds": [1, 2, 3] }`

Все защищённые эндпоинты требуют заголовок:

```text
Authorization: Bearer <token>
```

## Интеграция с фронтендом

Фронтенд (Vite + React) ожидает, что API доступно по адресу
`http://localhost:8000` и использует эти эндпоинты для:

- авторизации администратора;
- загрузки списка студентов;
- запуска/остановки стендов для выбранных студентов.

