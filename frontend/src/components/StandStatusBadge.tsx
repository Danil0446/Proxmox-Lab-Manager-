import React from "react";
import type { StandStatus } from "../App";

interface Props {
  status: StandStatus;
}

const STATUS_LABELS: Record<StandStatus, string> = {
  idle: "Не запущен",
  starting: "Запуск...",
  running: "Работает",
  error: "Ошибка"
};

export const StandStatusBadge: React.FC<Props> = ({ status }) => {
  return <span className={`badge badge-${status}`}>{STATUS_LABELS[status]}</span>;
};

