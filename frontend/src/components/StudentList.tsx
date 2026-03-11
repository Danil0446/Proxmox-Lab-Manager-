import React from "react";
import type { StandStatus, Student } from "../App";

interface Props {
  students: Student[];
  selectedIds: number[];
  onToggleSelect: (id: number) => void;
  now: number;
  renderStatus: (status: StandStatus) => React.ReactNode;
}

export const StudentList: React.FC<Props> = ({
  students,
  selectedIds,
  onToggleSelect,
  now,
  renderStatus
}) => {
  const formatDuration = (startedAt?: number | null): string => {
    if (!startedAt) return "—";

    const diffMs = Math.max(0, now - startedAt);
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

  if (students.length === 0) {
    return (
      <div className="empty-state">
        <p>Под критерии поиска никого не нашли.</p>
      </div>
    );
  }

  return (
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
          {students.map((student) => {
            const checked = selectedIds.includes(student.id);
            return (
              <tr key={student.id} className={checked ? "row-selected" : ""}>
                <td>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggleSelect(student.id)}
                  />
                </td>
                <td>{student.name}</td>
                <td>{student.group}</td>
                <td>
                  <a href={`mailto:${student.email}`} className="link">
                    {student.email}
                  </a>
                </td>
                <td>{renderStatus(student.standStatus)}</td>
                <td>{formatDuration(student.standStartedAt)}</td>
                <td>
                  {student.standResources ? (
                    <span className="resources">
                      {student.standResources.cpu} ·{" "}
                      {student.standResources.memory} ·{" "}
                      {student.standResources.disk}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

