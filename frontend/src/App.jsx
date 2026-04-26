import React, { useState, useEffect, useMemo } from "react";
import axios from "axios";

// URL backend: из переменной окружения (frontend/.env) или по умолчанию тот же хост, порт 8000
const API_BASE =
  (typeof process !== "undefined" && process.env?.REACT_APP_API_URL) ||
  window.location.origin.replace("3000", "8000");

function App() {
  const [token, setToken] = useState("");
  const [role, setRole] = useState("");
  const [email, setEmail] = useState("Admin");
  const [password, setPassword] = useState("Admin");
  const [activeTab, setActiveTab] = useState("overview"); // overview | manage

  const [students, setStudents] = useState([]);
  const [studentLabs, setStudentLabs] = useState({});
  const [activeGroup, setActiveGroup] = useState("Все");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStudentIds, setSelectedStudentIds] = useState([]);
  const [now, setNow] = useState(Date.now());

  const [labs, setLabs] = useState([]);
  const [defaultCluster, setDefaultCluster] = useState(null);

  const [newLab, setNewLab] = useState({
    name: "",
    template_vmid: "",
    template_type: "qemu",
    use_existing_vm: false,
    default_node: ""
  });

  const [newStudent, setNewStudent] = useState({
    login: "",
    password: "student123",
    full_name: "",
    group_name: ""
  });
  const [creatingStudent, setCreatingStudent] = useState(false);
  const [templatesInput, setTemplatesInput] = useState({});
  const [issuingStands, setIssuingStands] = useState(false);
  const [loadError, setLoadError] = useState(null);

  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

  const stands = useMemo(() => {
    const groups = {};
    labs.forEach((lab) => {
      const name = (lab.name || "").trim();
      let standName = name || `VMID ${lab.template_vmid}`;
      const parts = name.split(" ");
      const last = parts[parts.length - 1];
      const lastNumber = parseInt(last, 10);
      if (!Number.isNaN(lastNumber) && lastNumber === lab.template_vmid && parts.length > 1) {
        standName = parts.slice(0, -1).join(" ");
      }
      if (!groups[standName]) {
        groups[standName] = { name: standName, labs: [], vmids: [] };
      }
      groups[standName].labs.push(lab);
      groups[standName].vmids.push(lab.template_vmid);
    });
    return Object.values(groups);
  }, [labs]);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const handleLogin = async () => {
    try {
      const form = new URLSearchParams();
      form.append("username", email);
      form.append("password", password);
      const res = await axios.post(`${API_BASE}/auth/login`, form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" }
      });
      setToken(res.data.access_token);
      setRole(email === "Admin" ? "admin" : "student");
    } catch (e) {
      alert("Ошибка логина");
      console.error(e);
    }
  };

  const loadAdminData = async () => {
    if (role !== "admin" || !token) return;
    setLoadError(null);
    try {
      const [studentsRes, labsRes, allLabsRes, clusterRes] = await Promise.all([
        axios.get(`${API_BASE}/admin/students`, { headers: authHeaders }),
        axios.get(`${API_BASE}/admin/student-labs`, { headers: authHeaders }),
        axios.get(`${API_BASE}/admin/labs`, { headers: authHeaders }),
        axios.get(`${API_BASE}/admin/clusters/default`, { headers: authHeaders })
      ]);
      setStudents(studentsRes.data);
      const labsByStudent = {};
      labsRes.data.forEach((lab) => {
        if (!labsByStudent[lab.student_id]) labsByStudent[lab.student_id] = [];
        labsByStudent[lab.student_id].push(lab);
      });
      setStudentLabs(labsByStudent);
      setLabs(allLabsRes.data);
      setDefaultCluster(clusterRes.data);
    } catch (e) {
      console.error(e);
      const msg =
        e.response?.status === 401
          ? "Сессия истекла — войдите снова"
          : `Не удалось загрузить данные с ${API_BASE}. Проверьте: 1) backend запущен (uvicorn), 2) если фронт открыт с другой машины — в frontend/.env задайте REACT_APP_API_URL=http://IP-сервера:8000 и перезапустите npm run dev.`;
      setLoadError(msg);
    }
  };

  useEffect(() => {
    loadAdminData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, token]);

  const handleCreateStudent = async () => {
    if (creatingStudent) return;
    setCreatingStudent(true);
    try {
      await axios.post(`${API_BASE}/admin/students`, newStudent, { headers: authHeaders });
      setNewStudent({ login: "", password: "student123", full_name: "", group_name: "" });
      await loadAdminData();
    } catch (e) {
      const detail = e.response?.data?.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : detail
          ? JSON.stringify(detail)
          : "Ошибка создания студента";
      alert(msg);
      if (msg.includes("Логин уже занят") || msg.includes("логин")) {
        await loadAdminData();
      }
      console.error(e);
    } finally {
      setCreatingStudent(false);
    }
  };

  const toggleSelectStudent = (id) => {
    setSelectedStudentIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const clearSelection = () => setSelectedStudentIds([]);

  const selectAllVisible = (visibleIds) => {
    setSelectedStudentIds(visibleIds);
  };

  const formatDurationFrom = (startedAt) => {
    if (!startedAt) return "—";
    const started = new Date(startedAt).getTime();
    const diffMs = Math.max(0, now - started);
    const totalSeconds = Math.floor(diffMs / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    if (hours > 0) {
      return `${hours}ч ${minutes.toString().padStart(2, "0")}м`;
    }
    return `${minutes.toString().padStart(2, "0")}м ${seconds
      .toString()
      .padStart(2, "0")}с`;
  };

  const formatProxmoxLogin = (value) => {
    if (!value) return "";
    return String(value).split("@")[0];
  };

  const getStandInfoForStudent = (student) => {
    const labsForStudent = studentLabs[student.id] || [];
    if (!labsForStudent.length) {
      return {
        statusLabel: "Не запущен",
        statusClass: "badge-idle",
        duration: "—",
        resources: "—"
      };
    }

    const latest = labsForStudent.reduce((acc, item) => {
      const t = new Date(item.created_at).getTime();
      if (!acc) return { item, ts: t };
      return t > acc.ts ? { item, ts: t } : acc;
    }, null);

    const inst = latest.item;
    const status = inst.status || "";
    let statusLabel = "Не запущен";
    let statusClass = "badge-idle";
    if (status === "running") {
      statusLabel = "Работает";
      statusClass = "badge-running";
    } else if (status === "creating" || status === "ready") {
      statusLabel = "Запуск...";
      statusClass = "badge-starting";
    } else if (status === "error") {
      statusLabel = "Ошибка";
      statusClass = "badge-error";
    }

    const labMeta = labs.find((l) => l.id === inst.lab_id);
    let resources = "—";
    if (labMeta) {
      const cpu = labMeta.cpu_limit ? `${labMeta.cpu_limit} vCPU` : null;
      const mem = labMeta.memory_mb ? `${labMeta.memory_mb} МБ RAM` : null;
      const disk = labMeta.disk_gb ? `${labMeta.disk_gb} ГБ` : null;
      const parts = [cpu, mem, disk].filter(Boolean);
      if (parts.length) {
        resources = parts.join(" · ");
      }
    }

    return {
      statusLabel,
      statusClass,
      duration: formatDurationFrom(inst.created_at),
      resources
    };
  };

  return (
    <div className="app-root">
      <header className="app-header">
        <div>
          <h1>Панель администратора</h1>
          <p className="app-header-subtitle">Управление студентами и их стендами</p>
        </div>
        {token && role === "admin" && (
          <div className="header-actions">
            <button
              type="button"
              className={`btn btn-ghost${activeTab === "overview" ? " btn-primary" : ""}`}
              onClick={() => setActiveTab("overview")}
            >
              Все студенты
            </button>
            <button
              type="button"
              className={`btn btn-ghost${activeTab === "manage" ? " btn-primary" : ""}`}
              onClick={() => setActiveTab("manage")}
            >
              Управление
            </button>
          </div>
        )}
      </header>

      {!token && (
        <main className="app-main app-main-centered">
          <section className="card login-card">
            <div className="card-header">
              <div>
                <h2>Вход администратора</h2>
                <p className="card-subtitle">
                  Только администратор имеет доступ к панели управления стендами.
                </p>
              </div>
            </div>
            <form
              className="login-form"
              onSubmit={(e) => {
                e.preventDefault();
                handleLogin();
              }}
            >
              <label className="field">
                <span className="field-label">Логин</span>
                <input
                  type="text"
                  className="field-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
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
                  autoComplete="current-password"
                />
              </label>
              <div className="login-actions">
                <button type="submit" className="btn btn-primary">
                  Войти
                </button>
              </div>
            </form>
          </section>
        </main>
      )}

      {token && role === "admin" && activeTab === "overview" && (
        <main className="app-main">
          <div className="layout">
            <div className="card">
              <div className="card-header">
                <div>
                  <h2>Все студенты</h2>
                  <p className="card-subtitle">
                    Сводный список студентов и их стендов в одном месте.
                  </p>
                </div>
                <div className="card-header-actions">
                  <input
                    type="search"
                    className="search-input"
                    placeholder="Поиск по имени, группе или email..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
              </div>
              <div className="table-wrapper">
                <table className="table">
                  <thead>
                    <tr>
                      <th style={{ width: 40 }}>
                        <span className="sr-only">Выбор</span>
                      </th>
                      <th>Студент</th>
                      <th>Группа</th>
                      <th>Email</th>
                      <th>Стенд</th>
                      <th>Время работы</th>
                      <th>Ресурсы стенда</th>
                    </tr>
                  </thead>
                  <tbody>
                    {students
                      .filter((s) => {
                        const q = searchQuery.trim().toLowerCase();
                        if (!q) return true;
                        const group = (s.group_name || "Без группы").toLowerCase();
                        const emailVal = (s.user?.login || "").toLowerCase();
                        const nameVal = (s.full_name || "").toLowerCase();
                        return (
                          nameVal.includes(q) ||
                          group.includes(q) ||
                          emailVal.includes(q)
                        );
                      })
                      .map((s) => {
                        const checked = selectedStudentIds.includes(s.id);
                        const info = getStandInfoForStudent(s);
                        return (
                          <tr
                            key={s.id}
                            className={checked ? "row-selected" : ""}
                          >
                            <td>
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => toggleSelectStudent(s.id)}
                              />
                            </td>
                            <td>{s.full_name}</td>
                            <td>{s.group_name || "Без группы"}</td>
                            <td>
                              <a
                                href={`mailto:${s.user?.login || ""}`}
                                className="link"
                              >
                                {s.user?.login}
                              </a>
                            </td>
                            <td>
                              <span className={`badge ${info.statusClass}`}>
                                {info.statusLabel}
                              </span>
                            </td>
                            <td>{info.duration}</td>
                            <td>
                              <span className="resources">{info.resources}</span>
                            </td>
                          </tr>
                        );
                      })}
                    {students.length === 0 && (
                      <tr>
                        <td colSpan={7}>
                          <div className="empty-state">
                            <p>Студентов пока нет. Создайте первого ниже.</p>
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </main>
      )}

      {token && role === "admin" && activeTab === "manage" && (
        <main className="app-main">
          <section className="card card-manage">
            <div className="card-header">
              <div>
                <h2>Управление студентами и стендами</h2>
                <p className="card-subtitle">
                  Стенд — это набор машин. Здесь вы создаёте стенды (наборы ВМ) и выдаёте их студентам.
                </p>
              </div>
            </div>

            <div className="manage-grid">
              <div className="manage-column">
                <h3 className="manage-title">Создать студента</h3>
                <p className="small" style={{ marginBottom: "8px", opacity: 0.9 }}>
                  Занятые логины смотрите в списке ниже. Для Proxmox лучше только латиница и цифры
                  (например student1).
                </p>
                <div className="field">
                  <label>Логин</label>
                  <input
                    value={newStudent.login}
                    onChange={(e) => setNewStudent({ ...newStudent, login: e.target.value })}
                  />
                </div>
                <div className="field">
                  <label>Пароль</label>
                  <input
                    value={newStudent.password}
                    onChange={(e) => setNewStudent({ ...newStudent, password: e.target.value })}
                  />
                </div>
                <div className="field">
                  <label>ФИО</label>
                  <input
                    value={newStudent.full_name}
                    onChange={(e) => setNewStudent({ ...newStudent, full_name: e.target.value })}
                  />
                </div>
                <div className="field">
                  <label>Группа</label>
                  <input
                    value={newStudent.group_name}
                    onChange={(e) => setNewStudent({ ...newStudent, group_name: e.target.value })}
                  />
                </div>
                <button onClick={handleCreateStudent} disabled={creatingStudent}>
                  {creatingStudent ? "Создание…" : "Создать"}
                </button>

                <div className="manage-section">
                  <h3 className="manage-title">Служебные действия</h3>
                  <button
                    onClick={async () => {
                      if (!window.confirm("Удалить всех студентов и их стенды?")) return;
                      try {
                        await axios.delete(`${API_BASE}/admin/students`, { headers: authHeaders });
                        setStudents([]);
                        setStudentLabs({});
                      } catch (e) {
                        console.error(e);
                        alert("Не удалось удалить студентов");
                      }
                    }}
                  >
                    Удалить всех студентов
                  </button>
                </div>
              </div>

              <div className="manage-column manage-column-wide">
                <h3 className="manage-title">Студенты</h3>
            {loadError && (
              <div className="small" style={{ color: "#e88", marginBottom: "8px", maxWidth: "520px" }}>
                {loadError}
                <button type="button" className="small-btn" style={{ marginLeft: "8px", marginTop: "6px" }} onClick={loadAdminData}>
                  Повторить
                </button>
              </div>
            )}
            <div className="tabs">
              <button
                className={activeGroup === "Все" ? "tab active" : "tab"}
                onClick={() => setActiveGroup("Все")}
              >
                Все
              </button>
              {Array.from(new Set(students.map((s) => s.group_name || "Без группы"))).map((g) => (
                <button
                  key={g}
                  className={activeGroup === g ? "tab active" : "tab"}
                  onClick={() => setActiveGroup(g)}
                >
                  {g}
                </button>
              ))}
            </div>
            <ul>
              {students.length === 0 && !loadError && (
                <li className="small">Студентов пока нет. Создайте первого выше.</li>
              )}
              {students
                .filter((s) => activeGroup === "Все" || (s.group_name || "Без группы") === activeGroup)
                .map((s) => (
                  <li key={s.id}>
                    <div>
                      <strong>{s.full_name}</strong> (логин: {s.user.login})
                    </div>
                    <div className="small">
                      Группа: {s.group_name || "Без группы"} | Создан:{" "}
                      {new Date(s.created_at).toLocaleString()}
                    </div>
                    {s.proxmox_login && (
                      <div className="small" style={{ color: "#8af", marginTop: "4px" }}>
                        Вход в Proxmox:{" "}
                        <strong>{formatProxmoxLogin(s.proxmox_login)}</strong> (логин;
                        realm @pve добавится автоматически)
                      </div>
                    )}
                    <div className="small">
                      Стенды:
                      <ul>
                        {(studentLabs[s.id] || []).map((lab) => (
                          <li key={lab.id}>
                            Лаба #{lab.lab_id} – VMID {lab.proxmox_vmid} – статус {lab.status}
                            <button
                              type="button"
                              className="small-btn"
                              onClick={async () => {
                                if (!window.confirm(`Удалить стенд VMID ${lab.proxmox_vmid}? ВМ в Proxmox будет уничтожена.`)) return;
                                try {
                                  await axios.delete(`${API_BASE}/admin/student-labs/${lab.id}`, {
                                    headers: authHeaders
                                  });
                                  loadAdminData();
                                } catch (e) {
                                  console.error(e);
                                  alert(e.response?.data?.detail || "Не удалось удалить стенд");
                                }
                              }}
                            >
                              Удалить стенд
                            </button>
                          </li>
                        ))}
                        {(!studentLabs[s.id] || studentLabs[s.id].length === 0) && (
                          <li>Стендов пока нет</li>
                        )}
                      </ul>
                    </div>
                    <div className="small">
                      Выдать стенд по шаблонам (101-103 или 101, 102, 103):
                      <input
                        type="text"
                        placeholder="101-103 или 101, 102"
                        value={templatesInput[s.id] ?? ""}
                        onChange={(e) =>
                          setTemplatesInput((prev) => ({ ...prev, [s.id]: e.target.value }))
                        }
                        style={{ width: "180px", marginLeft: "6px", marginRight: "6px" }}
                      />
                      <button
                        type="button"
                        className="small-btn"
                        disabled={issuingStands || !(templatesInput[s.id] || "").trim()}
                        onClick={async () => {
                          const raw = (templatesInput[s.id] || "").trim();
                          if (!raw) return;
                          setIssuingStands(true);
                          try {
                            await axios.post(
                              `${API_BASE}/admin/students/${s.id}/stands`,
                              { templates: raw },
                              { headers: authHeaders }
                            );
                            setTemplatesInput((prev) => ({ ...prev, [s.id]: "" }));
                            loadAdminData();
                          } catch (e) {
                            console.error(e);
                            const detail = e.response?.data?.detail;
                            alert(
                              typeof detail === "string"
                                ? detail
                                : detail
                                ? JSON.stringify(detail)
                                : "Не удалось выдать стенды"
                            );
                          } finally {
                            setIssuingStands(false);
                          }
                        }}
                      >
                        Выдать по шаблонам
                      </button>
                    </div>
                    {stands.length > 0 && (
                      <div className="small">
                        Или выбрать стенд:
                        {stands.map((stand) => (
                          <button
                            key={stand.name}
                            className="small-btn"
                            onClick={async () => {
                              const templates = stand.vmids.join(", ");
                              try {
                                await axios.post(
                                  `${API_BASE}/admin/students/${s.id}/stands`,
                                  { templates },
                                  { headers: authHeaders }
                                );
                                loadAdminData();
                              } catch (e) {
                                console.error(e);
                                const detail = e.response?.data?.detail;
                                alert(
                                  typeof detail === "string"
                                    ? detail
                                    : detail
                                    ? JSON.stringify(detail)
                                    : "Не удалось выдать стенд"
                                );
                              }
                            }}
                          >
                            {stand.name}
                          </button>
                        ))}
                      </div>
                    )}
                    <button
                      className="small-btn"
                      onClick={async () => {
                        if (
                          !window.confirm(
                            `Удалить студента "${s.full_name}" (${s.user.login}) и все его стенды?`
                          )
                        )
                          return;
                        try {
                          await axios.delete(`${API_BASE}/admin/students/${s.id}`, {
                            headers: authHeaders
                          });
                          // обновим список после удаления
                          setStudents((prev) => prev.filter((st) => st.id !== s.id));
                          const updatedLabs = { ...studentLabs };
                          delete updatedLabs[s.id];
                          setStudentLabs(updatedLabs);
                        } catch (e) {
                          console.error(e);
                          alert("Не удалось удалить студента");
                        }
                      }}
                    >
                      Удалить студента
                    </button>
                  </li>
                ))}
            </ul>

                <div className="manage-section">
                  <h3 className="manage-title">Создание стенда (набора машин)</h3>
            <p className="small" style={{ marginBottom: "8px" }}>
              VMID через запятую или диапазон: <strong>100-103</strong> (создаст шаблоны для 100, 101, 102, 103)
              или <strong>101, 103</strong> (создаст для 101 и 103). Один стенд — это набор всех указанных машин:
              при выдаче студенту он получит столько ВМ, сколько входит в стенд.
            </p>
            {defaultCluster ? (
              <>
                <div className="field">
                  <label>Префикс названия</label>
                  <input
                    value={newLab.name}
                    onChange={(e) => setNewLab({ ...newLab, name: e.target.value })}
                    placeholder="Шаблон (будет «Шаблон 100», «Шаблон 101»…)"
                  />
                </div>
                <div className="field">
                  <label>VMID машины (диапазон или список)</label>
                  <input
                    value={newLab.template_vmid}
                    onChange={(e) => setNewLab({ ...newLab, template_vmid: e.target.value })}
                    placeholder="100-103 или 101, 103"
                  />
                </div>
                <div className="field">
                  <label>
                    <input
                      type="checkbox"
                      checked={newLab.use_existing_vm || false}
                      onChange={(e) =>
                        setNewLab({ ...newLab, use_existing_vm: e.target.checked })
                      }
                    />
                    {" "}Существующая ВМ (не клонировать — указанная машина будет выдаваться студенту)
                  </label>
                </div>
                <div className="field">
                  <label>Тип</label>
                  <select
                    value={newLab.template_type}
                    onChange={(e) => setNewLab({ ...newLab, template_type: e.target.value })}
                  >
                    <option value="qemu">VM (qemu)</option>
                    <option value="lxc">LXC</option>
                  </select>
                </div>
                <div className="field">
                  <label>Пул (Node)</label>
                  <input
                    value={newLab.default_node}
                    onChange={(e) => setNewLab({ ...newLab, default_node: e.target.value })}
                    placeholder={defaultCluster.default_node}
                  />
                </div>
                <div className="field">
                  <button
                    onClick={async () => {
                      const vmidStr = (newLab.template_vmid || "").trim();
                      const namePrefix = (newLab.name || "").trim() || "Шаблон";
                      if (!vmidStr) {
                        alert("Введите VMID: одно число, диапазон (100-103) или список (101, 103)");
                        return;
                      }
                      try {
                        const res = await axios.post(
                          `${API_BASE}/admin/labs/batch`,
                          {
                            template_vmids: vmidStr,
                            name_prefix: namePrefix,
                            template_type: newLab.template_type,
                            use_existing_vm: newLab.use_existing_vm || false,
                            default_node: newLab.default_node || null,
                            proxmox_cluster_id: defaultCluster.id
                          },
                          { headers: authHeaders }
                        );
                        if (res.data.length > 1) {
                          alert(`Создано шаблонов: ${res.data.length}`);
                        }
                        setNewLab({
                          name: "",
                          template_vmid: "",
                          template_type: "qemu",
                          use_existing_vm: false,
                          default_node: ""
                        });
                        loadAdminData();
                      } catch (e) {
                        console.error(e);
                        const detail = e.response?.data?.detail;
                        alert(
                          typeof detail === "string"
                            ? detail
                            : detail
                            ? JSON.stringify(detail)
                            : "Не удалось создать шаблон"
                        );
                      }
                    }}
                  >
                    {newLab.use_existing_vm ? "Создать стенды (сущ. ВМ)" : "Создать шаблон(ы)"}
                  </button>
                  <button
                    style={{ marginLeft: "8px" }}
                    onClick={async () => {
                      if (!window.confirm("Удалить все шаблоны стендов? Уже выданные стенды останутся.")) return;
                      try {
                        await axios.delete(`${API_BASE}/admin/labs`, { headers: authHeaders });
                        loadAdminData();
                      } catch (e) {
                        console.error(e);
                        const detail = e.response?.data?.detail;
                        alert(
                          typeof detail === "string"
                            ? detail
                            : detail
                            ? JSON.stringify(detail)
                            : "Не удалось удалить шаблоны"
                        );
                      }
                    }}
                  >
                    Удалить все шаблоны
                  </button>
                </div>
                <ul>
                  {stands.map((stand) => (
                    <li key={stand.name}>
                      <strong>{stand.name}</strong> – VMID {stand.vmids.join(", ")}
                      {stand.labs.some((lab) => lab.use_existing_vm) && " — сущ. ВМ"}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p>Кластер Proxmox ещё не инициализирован. Создайте первого студента.</p>
            )}
                </div>
              </div>
            </div>
          </section>
        </main>
      )}
    </div>
  );
}

export default App;

