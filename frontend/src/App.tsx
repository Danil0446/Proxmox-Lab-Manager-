import React, { useEffect, useMemo, useState } from "react";
import { StudentList } from "./components/StudentList";
import { StandStatusBadge } from "./components/StandStatusBadge";
import { StandActionButton } from "./components/StandActionButton";

export type StandStatus = "idle" | "starting" | "running" | "error";

export interface Student {
  id: number;
  name: string;
  group: string;
  email: string;
  standStatus: StandStatus;
  standStartedAt?: number | null;
  standResources?: {
    cpu: string;
    memory: string;
    disk: string;
  };
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const App: React.FC = () => {
  const [students, setStudents] = useState<Student[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [search, setSearch] = useState("");
  const [now, setNow] = useState<number>(Date.now());
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [login, setLogin] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);

  useEffect(() => {
    const id = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);

    return () => window.clearInterval(id);
  }, []);

  const filteredStudents = useMemo(
    () =>
      students.filter(
        (s) =>
          s.name.toLowerCase().includes(search.toLowerCase()) ||
          s.group.toLowerCase().includes(search.toLowerCase()) ||
          s.email.toLowerCase().includes(search.toLowerCase())
      ),
    [students, search]
  );

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const selectAllVisible = () => {
    const ids = filteredStudents.map((s) => s.id);
    setSelectedIds(ids);
  };

  const clearSelection = () => setSelectedIds([]);

  const fetchStudents = async (token: string) => {
    try {
      const res = await fetch(`${API_URL}/students`, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      if (!res.ok) {
        throw new Error("Не удалось загрузить список студентов");
      }

      const data: Student[] = await res.json();
      setStudents(data);
      setGlobalError(null);
    } catch (e) {
      setGlobalError(
        e instanceof Error ? e.message : "Ошибка при загрузке студентов"
      );
    }
  };

  const startStandsForSelected = async () => {
    if (selectedIds.length === 0) return;
    if (!authToken) return;

    setStudents((prev) =>
      prev.map((s) =>
        selectedIds.includes(s.id)
          ? { ...s, standStatus: "starting" }
          : s
      )
    );

    try {
      const res = await fetch(`${API_URL}/stands/start`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify({ studentIds: selectedIds })
      });

      if (!res.ok) {
        throw new Error("Не удалось запустить стенды");
      }

      const data: Student[] = await res.json();
      setStudents(data);
      setGlobalError(null);
    } catch (e) {
      setGlobalError(
        e instanceof Error ? e.message : "Ошибка при запуске стендов"
      );
    }
  };

  const stopStandsForSelected = async () => {
    if (selectedIds.length === 0) return;
    if (!authToken) return;

    try {
      const res = await fetch(`${API_URL}/stands/stop`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify({ studentIds: selectedIds })
      });

      if (!res.ok) {
        throw new Error("Не удалось выключить стенды");
      }

      const data: Student[] = await res.json();
      setStudents(data);
      setGlobalError(null);
    } catch (e) {
      setGlobalError(
        e instanceof Error ? e.message : "Ошибка при выключении стендов"
      );
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ username: login, password })
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const message =
          data?.detail ??
          (res.status === 401
            ? "Неверный логин или пароль"
            : "Ошибка при входе");
        setLoginError(message);
        setIsAuthenticated(false);
        setAuthToken(null);
        return;
      }

      const data: { token: string } = await res.json();
      setIsAuthenticated(true);
      setAuthToken(data.token);
      setLoginError(null);
      setPassword("");
      await fetchStudents(data.token);
    } catch (error) {
      setLoginError("Не удалось связаться с сервером");
      setIsAuthenticated(false);
      setAuthToken(null);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="app-root">
        <main className="app-main app-main-centered">
          <section className="card login-card">
            <div className="card-header">
              <div>
                <h2>Вход администратора</h2>
                <p className="card-subtitle">
                  Только администратор имеет доступ к панели управления
                  стендами.
                </p>
              </div>
            </div>
            <form className="login-form" onSubmit={handleLogin}>
              <label className="field">
                <span className="field-label">Логин</span>
                <input
                  type="text"
                  className="field-input"
                  value={login}
                  onChange={(e) => setLogin(e.target.value)}
                  placeholder="admin"
                  autoComplete="username"
                />
              </label>
              <label className="field">
                <span className="field-label">Пароль</span>
                <input
                  type="password"
                  className="field-input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="********"
                  autoComplete="current-password"
                />
              </label>
              {loginError && <p className="error">{loginError}</p>}
              <div className="login-actions">
                <button type="submit" className="btn btn-primary">
                  Войти
                </button>
              </div>
              <p className="hint">
                Тестовые данные: <code>admin / admin123</code>
              </p>
            </form>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="app-root">
      <header className="app-header">
        <div>
          <h1>Панель администратора</h1>
          <p className="app-header-subtitle">
            Управление студентами и их стендами
          </p>
        </div>
        <div className="header-actions">
          <input
            type="search"
            className="search-input"
            placeholder="Поиск по имени, группе или email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </header>

      <main className="app-main">
        <section className="card">
          <div className="card-header">
            <div>
              <h2>Список студентов</h2>
              <p className="card-subtitle">
                Выберите одного или нескольких студентов и поднимите стенды.
              </p>
            </div>
            <div className="card-header-actions">
              {globalError && <p className="error">{globalError}</p>}
              <button
                className="btn btn-ghost"
                type="button"
                onClick={selectAllVisible}
              >
                Выделить всех на странице
              </button>
              <button
                className="btn btn-ghost"
                type="button"
                onClick={clearSelection}
                disabled={selectedIds.length === 0}
              >
                Снять выделение
              </button>
              <button
                className="btn btn-danger"
                type="button"
                onClick={stopStandsForSelected}
                disabled={selectedIds.length === 0}
              >
                Выключить стенды
              </button>
              <StandActionButton
                type="button"
                onClick={startStandsForSelected}
                disabled={selectedIds.length === 0}
                label={
                  selectedIds.length === 0
                    ? "Выберите студентов"
                    : `Поднять стенды (${selectedIds.length})`
                }
              />
            </div>
          </div>

          <StudentList
            students={filteredStudents}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelect}
            now={now}
            renderStatus={(status) => <StandStatusBadge status={status} />}
          />
        </section>
      </main>
    </div>
  );
};

