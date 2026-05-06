#!/bin/bash

set -euo pipefail

echo "Автор: Ермолаев Д.А 2026. Контактная информация: danil-ermolaev-2016@mail.ru"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_ENV_FILE="$BACKEND_DIR/.env"

log() {
  echo "[install] $1"
}

require_dir() {
  if [[ ! -d "$1" ]]; then
    echo "Ошибка: каталог '$1' не найден. Запустите скрипт из корня проекта."
    exit 1
  fi
}

configure_backend_env() {
  echo ""
  echo "=== Настройка backend/.env ==="
  echo "Введите 6 переменных (можно оставить пустыми):"
  echo "Подсказки:"
  echo "  DATABASE_URL: sqlite+aiosqlite:///./app.db"
  echo "  API_URL: https://localhost:8006"
  echo "  PROXMOX_TOKEN_ID: root@pam!test"
  echo "  PROXMOX_TOKEN_SECRET: 26c24da6-3afe-43e2-8d1f-f46eabb9b91b"
  echo "  PROXMOX_DEFAULT_NODE: Название ноды (например debian)"
  echo "  PROXMOX_STUDENT_REALM: pve"
  echo "  PROXMOX_STUDENT_ROLE: StudentRole"
  echo ""

  read -r -p "URL API Proxmox (PROXMOX_API_URL) [пример: https://localhost:8006]: " API_URL
  read -r -p "Идентификатор токена (PROXMOX_TOKEN_ID) [пример: root@pam!test]: " TOKEN_ID
  read -r -s -p "Секрет токена (PROXMOX_TOKEN_SECRET) [пример: 26c24da6-3afe-43e2-8d1f-f46eabb9b91b]: " TOKEN_SECRET
  echo ""
  read -r -p "Узел по умолчанию (PROXMOX_DEFAULT_NODE) [пример: debian]: " DEFAULT_NODE
  read -r -p "Realm для студентов (PROXMOX_STUDENT_REALM) [пример: pve]: " STUDENT_REALM
  read -r -p "Роль для студентов (PROXMOX_STUDENT_ROLE) [пример: StudentRole]: " STUDENT_ROLE

  {
    echo "DATABASE_URL=sqlite+aiosqlite:///./app.db"
    echo "PROXMOX_API_URL=${API_URL}"
    echo "PROXMOX_TOKEN_ID=${TOKEN_ID}"
    echo "PROXMOX_TOKEN_SECRET=${TOKEN_SECRET}"
    echo "PROXMOX_DEFAULT_NODE=${DEFAULT_NODE}"
    echo "PROXMOX_STUDENT_REALM=${STUDENT_REALM}"
    echo "PROXMOX_STUDENT_ROLE=${STUDENT_ROLE}"
  } > "$BACKEND_ENV_FILE"

  log "backend/.env сохранен: $BACKEND_ENV_FILE"
}

main() {
  log "Проверка структуры проекта..."
  require_dir "$BACKEND_DIR"
  require_dir "$FRONTEND_DIR"

  log "Установка системных пакетов (Ubuntu/Debian)..."
  apt-get update -y
  apt-get install -y python3 python3-venv python3-pip curl vim
  apt-get install -y nodejs || true
  if ! command -v npm >/dev/null 2>&1; then
    apt-get install -y npm
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo "Ошибка: npm не найден после установки nodejs/npm."
    echo "Проверьте источники APT (возможен конфликт NodeSource и Debian)."
    echo "Проверка: node -v && npm -v && apt-cache policy nodejs npm"
    exit 1
  fi
  log "npm версия: $(npm -v)"

  log "Создание backend виртуального окружения..."
  if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
    python3 -m venv "$BACKEND_DIR/.venv"
  fi

  log "Установка Python-зависимостей backend..."
  "$BACKEND_DIR/.venv/bin/pip" install --upgrade pip
  if [[ -f "$BACKEND_DIR/requirements.txt" ]]; then
    "$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"
  else
    echo "Ошибка: файл '$BACKEND_DIR/requirements.txt' не найден."
    echo "Добавьте зависимости backend в requirements.txt и повторите запуск."
    exit 1
  fi

  log "Установка npm-зависимостей frontend..."
  if [[ -f "$FRONTEND_DIR/package-lock.json" ]]; then
    npm --prefix "$FRONTEND_DIR" ci
  else
    npm --prefix "$FRONTEND_DIR" install
  fi

  if [[ ! -f "$FRONTEND_DIR/.env" && -f "$FRONTEND_DIR/.env.example" ]]; then
    cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
    log "Создан frontend/.env из .env.example"
  fi

  configure_backend_env

  echo ""
  log "Готово. Запуск:"
  echo "1) Backend (терминал 1):"
  echo "   cd \"$BACKEND_DIR\""
  echo "   source .venv/bin/activate"
  echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
 # echo ""
  #echo "2) Создать админа (терминал 2, первый запуск):"
  #echo "   curl -X POST http://localhost:8000/auth/init-admin"
 # echo ""
  echo "3) Frontend (терминал 3):"
  echo "   cd \"$FRONTEND_DIR\""
  echo "   npm run dev"
}

main "$@"

