from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote

import requests

from .config import get_settings


@dataclass
class ProxmoxClient:
    """
    Простая обёртка над Proxmox API по токену.
    Реальные ошибки и проверку сертификатов можно доработать под прод.
    """

    base_url: str
    token_id: str
    token_secret: str

    @classmethod
    def from_settings(cls) -> "ProxmoxClient":
        settings = get_settings()
        return cls(
            base_url=f"{settings.proxmox_api_url}/api2/json",
            token_id=settings.proxmox_token_id,
            token_secret=settings.proxmox_token_secret,
        )

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"PVEAPIToken={self.token_id}={self.token_secret}",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        # Таймаут по умолчанию: чуть больше, чтобы дождаться медленных операций,
        # но всё ещё ограничивать зависание сервиса при проблемах с Proxmox.
        if "timeout" not in kwargs:
            kwargs["timeout"] = 15
        resp = requests.request(method, url, headers=self._headers, verify=False, **kwargs)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", data)

    # --- Users / ACL ---

    def list_users(self, timeout: int | None = None) -> list[dict[str, Any]]:
        """Список пользователей Proxmox (для проверки существования)."""
        kwargs = {} if timeout is None else {"timeout": timeout}
        data = self._request("GET", "/access/users", **kwargs)
        return data if isinstance(data, list) else []

    def user_exists(self, userid: str, timeout: int = 6) -> bool:
        """Проверка, есть ли пользователь в Proxmox. Короткий таймаут, чтобы не зависать при недоступном Proxmox."""
        users = self.list_users(timeout=timeout)
        return any(u.get("userid") == userid for u in users)

    def create_user(
        self,
        userid: str,
        password: str,
        enable: int = 1,
        expire: int | None = None,
        timeout: int = 10,
    ) -> Any:
        payload: dict[str, Any] = {"userid": userid, "password": password, "enable": enable}
        if expire is not None:
            payload["expire"] = expire
        return self._request("POST", "/access/users", data=payload, timeout=timeout)

    def delete_user(self, userid: str) -> Any:
        """Удалить пользователя Proxmox по userid (например, student@pve)."""
        return self._request("DELETE", f"/access/users/{userid}")

    def set_acl(
        self,
        path: str,
        users: str,
        roles: str,
        propagate: int = 0,
        delete: int = 0,
    ) -> Any:
        payload = {
            "path": path,
            "users": users,
            "roles": roles,
            "propagate": propagate,
            "delete": delete,
        }
        return self._request("PUT", "/access/acl", data=payload)

    # --- VM / CT clone & power ---

    def get_next_vmid(self) -> int:
        """Получить следующий свободный VMID в кластере."""
        raw = self._request("GET", "/cluster/nextid")
        return int(raw) if isinstance(raw, str) else int(raw)

    def wait_for_task(self, node: str, upid: str, timeout: int = 300, interval: float = 2.0) -> None:
        """Ждать завершения задачи. При ошибке или таймауте — исключение."""
        deadline = time.monotonic() + timeout
        encoded = quote(upid, safe="")
        path = f"/nodes/{node}/tasks/{encoded}/status"
        while time.monotonic() < deadline:
            data = self._request("GET", path)
            if not isinstance(data, dict):
                break
            status = data.get("status")
            if status == "stopped":
                exitstatus = data.get("exitstatus")
                if exitstatus != "OK":
                    raise RuntimeError(f"Proxmox task failed: exitstatus={exitstatus}, {data}")
                return
            time.sleep(interval)
        raise TimeoutError(f"Proxmox task did not finish within {timeout}s: {upid}")

    def clone_vm(
        self,
        node: str,
        vmid: int,
        newid: int | None = None,
        name: str | None = None,
        full: int = 1,
        target: str | None = None,
        wait: bool = True,
        task_timeout: int = 300,
    ) -> int:
        """
        Клонировать VM. Возвращает VMID созданной ВМ.
        Если newid не задан — берётся следующий свободный из кластера.
        """
        if newid is None:
            newid = self.get_next_vmid()
        # В Proxmox API VMID исходной ВМ уже указан в URL (/qemu/{vmid}/clone),
        # передавать его ещё раз в теле запроса нельзя — это даёт
        # "Parameter verification failed". Поэтому в payload оставляем
        # только параметры новой ВМ.
        # Минимальный набор параметров, который гарантированно
        # принимает Proxmox для клонирования шаблона: newid и full.
        # Имя ВМ задаём отдельным вызовом set_vm_name, так как
        # передача name в clone иногда приводит к "Parameter verification failed".
        payload: dict[str, Any] = {"newid": newid, "full": full}
        if target is not None:
            payload["target"] = target
        # Клонирование может занимать заметное время, даём больший таймаут.
        upid = self._request("POST", f"/nodes/{node}/qemu/{vmid}/clone", data=payload, timeout=60)
        if not isinstance(upid, str) or not upid.startswith("UPID:"):
            raise RuntimeError(f"Unexpected clone response: {upid}")
        if wait:
            self.wait_for_task(node, upid, timeout=task_timeout)
        return newid

    def vm_config(self, node: str, vmid: int) -> dict[str, Any]:
        """Конфиг QEMU VM из Proxmox."""
        data = self._request("GET", f"/nodes/{node}/qemu/{vmid}/config")
        return data if isinstance(data, dict) else {}

    def is_qemu_template(self, node: str, vmid: int) -> bool:
        """
        Проверка, что QEMU VM помечена как template в Proxmox.
        В API это флаг template=1 в конфиге VM.
        """
        cfg = self.vm_config(node=node, vmid=vmid)
        val = cfg.get("template", 0)
        try:
            return int(val) == 1
        except (TypeError, ValueError):
            return False

    def vm_status_action(self, node: str, vmid: int, action: Literal["start", "stop", "reset"]) -> Any:
        return self._request("POST", f"/nodes/{node}/qemu/{vmid}/status/{action}")

    def vm_status(self, node: str, vmid: int) -> dict[str, Any]:
        """Текущий статус ВМ (status: running/stopped)."""
        data = self._request("GET", f"/nodes/{node}/qemu/{vmid}/status/current")
        return data if isinstance(data, dict) else {}

    def set_vm_name(self, node: str, vmid: int, name: str) -> Any:
        """Установить имя ВМ в Proxmox (отображается в списке машин)."""
        return self._request(
            "PUT",
            f"/nodes/{node}/qemu/{vmid}/config",
            data={"name": name},
        )

    def set_vm_description(self, node: str, vmid: int, description: str) -> Any:
        """Установить описание (Notes) ВМ в Proxmox — подпись УЗ студента."""
        return self._request(
            "PUT",
            f"/nodes/{node}/qemu/{vmid}/config",
            data={"description": description},
        )

    def delete_vm(self, node: str, vmid: int, stop_first: bool = True) -> None:
        """Удалить ВМ в Proxmox. Если stop_first — сначала останавливает."""
        if stop_first:
            try:
                cur = self.vm_status(node, vmid)
                if cur.get("status") == "running":
                    upid = self.vm_status_action(node, vmid, "stop")
                    if isinstance(upid, str) and upid.startswith("UPID:"):
                        self.wait_for_task(node, upid, timeout=60)
            except Exception:
                pass
        self._request("DELETE", f"/nodes/{node}/qemu/{vmid}")

