import React, { useState, useEffect } from "react";
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

  const [students, setStudents] = useState([]);
  const [studentLabs, setStudentLabs] = useState({});
  const [activeGroup, setActiveGroup] = useState("Все");

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

  return (
    <div className="app">
      <h1>Панель администратора</h1>

      {!token && (
        <div className="card">
          <h2>Вход администратора</h2>
          <div className="field">
            <label>Логин</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label>Пароль</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <button onClick={handleLogin}>Войти</button>
        </div>
      )}

      {token && role === "admin" && (
        <div className="layout">
          <div className="card">
            <h2>Создать студента</h2>
            <p className="small" style={{ marginBottom: "8px", opacity: 0.9 }}>
              Занятые логины смотрите в списке «Студенты» ниже. Для Proxmox лучше только латиница и цифры (например student1).
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
          </div>

          <div className="card">
            <h2>Студенты</h2>
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
                        Вход в Proxmox: <strong>{s.proxmox_login}</strong> (вводите именно так, в нижнем регистре)
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
                    {labs.length > 0 && (
                      <div className="small">
                        Или выбрать лабу:
                        {labs.map((lab) => (
                          <button
                            key={lab.id}
                            className="small-btn"
                            onClick={async () => {
                              try {
                                await axios.post(
                                  `${API_BASE}/admin/students/${s.id}/labs/${lab.id}`,
                                  {},
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
                            {lab.name}
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
          </div>
          <div className="card">
            <h2>Служебные действия</h2>
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
          <div className="card">
            <h2>Создание стенда</h2>
            <p className="small" style={{ marginBottom: "8px" }}>
              VMID через запятую или диапазон: <strong>100-103</strong> (создаст 100, 101, 102, 103) или <strong>101, 103</strong> (создаст 101 и 103). Пул и префикс названия — по желанию.
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
                  {labs.map((lab) => (
                    <li key={lab.id}>
                      <strong>{lab.name}</strong> – VMID {lab.template_vmid} ({lab.template_type})
                      {lab.use_existing_vm && " — сущ. ВМ"}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p>Кластер Proxmox ещё не инициализирован. Создайте первого студента.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;

