## Proxmox Lab Manager

Backend: FastAPI (`backend/`), frontend: React/Node.js (`frontend/`).

### Запуск backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="sqlite+aiosqlite:///./app.db"
export PROXMOX_API_URL="https://your-proxmox:8006"
export PROXMOX_TOKEN_ID="user@pve!token"
export PROXMOX_TOKEN_SECRET="SECRET"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Важно:** `--host 0.0.0.0` нужен, чтобы в панель можно было зайти по IP с другой машины (иначе backend слушает только localhost и авторизация по IP не сработает).
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

При первом запуске можно создать админа:

```bash
curl -X POST http://localhost:8000/auth/init-admin
```

Админ (веб-панель администратора): логин `Admin`, пароль `Admin`.

**Восстановление входа в приложение:** если после «Удалить всех студентов» или сбоя вы не можете войти в панель, заново создайте админа (без авторизации):
```bash
curl -X POST https://ВАШ-PROD-URL/auth/init-admin
```
В ответ придёт токен; логин/пароль снова будут `Admin` / `Admin`.

### Запуск frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend будет на `http://localhost:3000`, backend — `http://localhost:8000`.

**Если не запускается (порты заняты):** если видите `Address already in use` / `EADDRINUSE` — backend или frontend уже запущены в другом терминале. Либо используйте уже запущенное, либо освободите порты:

```bash
# Кто слушает 8000 и 3000
ss -tulpn | grep -E '8000|3000'

# Остановить backend (uvicorn на 8000)
pkill -f "uvicorn app.main:app"

# Остановить frontend (webpack на 3000)
pkill -f "webpack-dev-server"
```

После этого снова запустите backend и frontend в двух терминалах.

**Переменные окружения фронта** — в папке `frontend/` создайте файл `.env` (можно скопировать из `.env.example`). Переменные подхватываются при сборке/запуске `npm run dev`:

| Переменная | Описание |
|------------|----------|
| `REACT_APP_API_URL` | URL backend (например `http://192.168.10.5:8000`). Если не задано — используется тот же хост, порт 8000. |

### Перенос проекта на другую машину

Скрипт установки зависимостей и отдельная памятка: [`scripts/setup-new-machine.sh`](scripts/setup-new-machine.sh), [`docs/SETUP_NEW_MACHINE.md`](docs/SETUP_NEW_MACHINE.md).

1. **Backend**
   - Старый `.venv` с другой машины лучше не использовать (другая версия Python/пути). Создайте новый:
     ```bash
     cd backend
     rm -rf .venv
     python3 -m venv .venv
     source .venv/bin/activate
     pip install -r requirements.txt
     ```
   - Обновите `backend/.env`: укажите **URL вашего Proxmox** и токен (на другой машине был `PROXMOX_API_URL=https://192.168.1.14:8006` — замените на хост/IP вашего кластера).
   - База SQLite: файл `backend/app.db` создаётся при первом запуске. Если копировали проект с другой машины и нужны старые данные — скопируйте и `app.db`.

2. **Frontend**
   - Нужен **Node.js** (npm). Установите, если нет: например `apt install nodejs npm` или с [nodejs.org](https://nodejs.org).
   - Зависимости ставятся заново: `cd frontend && npm install && npm run dev`.
   - Если фронт открывается с другой машины в браузере, в `frontend/.env` задайте `REACT_APP_API_URL=http://<IP-бэкенда>:8000`.

После этого backend и frontend на новой машине будут работать так же, как на старой.

**Обновление БД (если база создана до добавления «существующая ВМ»):**
```bash
sqlite3 backend/app.db "ALTER TABLE labs ADD COLUMN use_existing_vm BOOLEAN NOT NULL DEFAULT 0;"
```

### Создание стенда: шаблон или существующая ВМ

- **Шаблон (клонирование):** укажите VMID шаблона, название, пул (node). При выдаче студенту создаётся клон ВМ, в Proxmox в Notes подписывается УЗ студента, машина запускается.
- **Существующая ВМ:** включите «Существующая ВМ (не клонировать)», укажите VMID уже созданной машины, пул и название. При выдаче студенту эта ВМ получает права студента, в Notes пишется УЗ, машина запускается. При снятии стенда ВМ не удаляется, только снимаются права и очищаются Notes.

### Минимальные права студентов в Proxmox (без ROOT)

Чтобы новые УЗ могли только настраивать **свои** машины, выданные админом, в Proxmox нужно создать роль с ограниченными привилегиями и указать её в `backend/.env`:

```env
PROXMOX_STUDENT_ROLE=StudentRole
```

**Создание роли в Proxmox:**

1. **Datacenter** → **Permissions** → **Roles** → **Create**.
2. Имя роли: `StudentRole` (или другое — тогда укажите его в `PROXMOX_STUDENT_ROLE`).
3. Включите **только** эти привилегии (остальные оставьте выключенными):
   - **Sys.Audit** — просмотр интерфейса, вход в систему
   - **VM.Audit** — просмотр своих ВМ
   - **VM.Console** — консоль ВМ
   - **VM.PowerMgmt** — запуск/остановка/перезагрузка ВМ
   - **VM.Config.Network** — настройка сети ВМ (при необходимости)
   - **VM.Config.HWType** — изменение типа оборудования ВМ (при необходимости)
   - **VM.Config.CDROM** — монтирование ISO (при необходимости)
4. **Не включайте:** VM.Allocate, VM.Clone, Datastore.*, Permissions.*, Group.*, Pool.Allocate, Realm.*, SDN.* и прочие права уровня админа.

После этого при создании студента и при выдаче стенда ему будет назначаться только эта роль (на путь `/` и на его ВМ), без прав администратора.

### Backend без прав root в Proxmox

Чтобы **не давать root** для API, используйте отдельную служебную учётку с минимальными правами.

**1. Роль для сервиса (в Proxmox):**

- **Datacenter** → **Permissions** → **Roles** → **Create**.
- Имя: `LabManagerService`.
- Включите **только** привилегии, нужные приложению:
  - **Realm.AllocateUser** — создание учёток студентов в realm pve
  - **Permissions.Modify** — назначение ACL (роль студента на `/` и на ВМ)
  - **VM.Allocate**, **VM.Clone** — создание ВМ из шаблона при выдаче стенда
  - **Datastore.AllocateTemplate** — использование шаблонов при клонировании
  - **Sys.Audit** — просмотр нод/путей при работе API
- Остальное (Permissions.Modify на уровне датацентра можно оставить, но не давать Group.Allocate, Realm.Allocate, Pool.Allocate и т.п., если не нужны) — выключено.

**2. Служебный пользователь и токен:**

- **Users** → **Add**: пользователь, например `svc-lab@pve`, пароль по желанию.
- **Permissions** → **Add** → User Permission: пользователь `svc-lab@pve`, Path `/`, Role **LabManagerService**.
- **Permissions** → **API Tokens** → Add: User `svc-lab@pve`, Token ID например `api`, **без** ограничения прав (Privilege Separation выключен).
- Секрет токена сохранить — он понадобится в `.env`.

**3. Подставить в backend:**

В `backend/.env` укажите токен **этой** учётки, а не root:

```env
PROXMOX_TOKEN_ID=svc-lab@pve!api
PROXMOX_TOKEN_SECRET=<секрет_токена>
```

После перезапуска backend будет работать от имени `svc-lab@pve` с ролью **LabManagerService**, без прав root.

