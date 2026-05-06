from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .models import LabInstanceStatus, ProxmoxAccountStatus, UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int
    role: UserRole


class AdminInitRequest(BaseModel):
    login: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)


class UserBase(BaseModel):
    login: str


class UserCreate(UserBase):
    password: str = Field(min_length=6)
    full_name: str
    group_name: Optional[str] = None
    external_id: Optional[str] = None


class UserRead(UserBase):
    id: int
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True


class StudentProfileRead(BaseModel):
    id: int
    user: UserRead
    full_name: str
    group_name: Optional[str] = None
    external_id: Optional[str] = None
    created_at: datetime
    proxmox_login: Optional[str] = None  # для входа в Proxmox (userid, например qwerty@pve)

    class Config:
        from_attributes = True


class LabBase(BaseModel):
    name: str
    description: Optional[str] = None
    template_type: Literal["qemu", "lxc"]
    template_vmid: int
    use_existing_vm: bool = False
    default_node: Optional[str] = None
    cpu_limit: Optional[int] = None
    memory_mb: Optional[int] = None
    disk_gb: Optional[int] = None


class LabCreate(LabBase):
    proxmox_cluster_id: int


class LabBatchCreate(BaseModel):
    """Создание нескольких шаблонов: VMID через запятую или диапазон 100-103."""
    template_vmids: str  # "100-103" или "101, 102, 103"
    name_prefix: Optional[str] = "Шаблон"  # имя будет «{name_prefix} {vmid}»
    template_type: Literal["qemu", "lxc"] = "qemu"
    use_existing_vm: bool = False
    default_node: Optional[str] = None
    proxmox_cluster_id: int


class LabRead(LabBase):
    id: int
    proxmox_cluster_id: int
    is_active: bool

    class Config:
        from_attributes = True


class ProxmoxClusterRead(BaseModel):
    id: int
    name: str
    api_url: str
    default_node: str
    is_default: bool

    class Config:
        from_attributes = True


class StudentLabInstanceRead(BaseModel):
    id: int
    lab_id: int
    student_id: int
    proxmox_cluster_id: int
    proxmox_vmid: int
    node: str
    status: LabInstanceStatus
    ip_address: Optional[str] = None
    name_in_proxmox: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PowerActionRequest(BaseModel):
    action: Literal["start", "stop", "reset"]


class StandsByTemplatesRequest(BaseModel):
    """Шаблоны: «101-103» или «101, 102, 103»."""
    templates: str


class ProxmoxAccountRead(BaseModel):
    id: int
    student_id: int
    proxmox_cluster_id: int
    userid: str
    realm: str
    status: ProxmoxAccountStatus

    class Config:
        from_attributes = True

