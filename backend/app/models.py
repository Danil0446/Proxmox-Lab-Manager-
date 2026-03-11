import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    STUDENT = "student"


class LabInstanceStatus(str, enum.Enum):
    CREATING = "creating"
    READY = "ready"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    DELETED = "deleted"


class ProxmoxAccountStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.STUDENT)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    student_profile: Mapped["StudentProfile"] = relationship(back_populates="user", uselist=False)


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    group_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    #group_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    #external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="student_profile")
    proxmox_accounts: Mapped[list["ProxmoxAccount"]] = relationship(back_populates="student")
    lab_instances: Mapped[list["StudentLabInstance"]] = relationship(back_populates="student")


class ProxmoxCluster(Base):
    __tablename__ = "proxmox_clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_url: Mapped[str] = mapped_column(Text, nullable=False)
    token_id: Mapped[str] = mapped_column(String(255), nullable=False)
    token_name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_node: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    labs: Mapped[list["Lab"]] = relationship(back_populates="proxmox_cluster")
    proxmox_accounts: Mapped[list["ProxmoxAccount"]] = relationship(back_populates="cluster")
    lab_instances: Mapped[list["StudentLabInstance"]] = relationship(back_populates="cluster")


class Lab(Base):
    __tablename__ = "labs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proxmox_cluster_id: Mapped[int] = mapped_column(ForeignKey("proxmox_clusters.id", ondelete="RESTRICT"))
    template_type: Mapped[str] = mapped_column(String(16), nullable=False)  # qemu / lxc
    template_vmid: Mapped[int] = mapped_column(Integer, nullable=False)
    use_existing_vm: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_node: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cpu_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    memory_mb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    disk_gb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extra_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    proxmox_cluster: Mapped[ProxmoxCluster] = relationship(back_populates="labs")
    lab_instances: Mapped[list["StudentLabInstance"]] = relationship(back_populates="lab")


class ProxmoxAccount(Base):
    __tablename__ = "proxmox_accounts"
    __table_args__ = (UniqueConstraint("student_id", "proxmox_cluster_id", name="uq_student_cluster"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    proxmox_cluster_id: Mapped[int] = mapped_column(
        ForeignKey("proxmox_clusters.id", ondelete="CASCADE"), nullable=False
    )
    userid: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. student123@pve
    realm: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ProxmoxAccountStatus] = mapped_column(
        Enum(ProxmoxAccountStatus), default=ProxmoxAccountStatus.ACTIVE, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    student: Mapped[StudentProfile] = relationship(back_populates="proxmox_accounts")
    cluster: Mapped[ProxmoxCluster] = relationship(back_populates="proxmox_accounts")


class StudentLabInstance(Base):
    __tablename__ = "student_lab_instances"
    __table_args__ = (
        CheckConstraint("proxmox_vmid > 0", name="chk_vmid_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id", ondelete="RESTRICT"), nullable=False)
    proxmox_cluster_id: Mapped[int] = mapped_column(
        ForeignKey("proxmox_clusters.id", ondelete="RESTRICT"), nullable=False
    )
    proxmox_vmid: Mapped[int] = mapped_column(Integer, nullable=False)
    node: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[LabInstanceStatus] = mapped_column(
        Enum(LabInstanceStatus), default=LabInstanceStatus.CREATING, nullable=False
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    name_in_proxmox: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    student: Mapped[StudentProfile] = relationship(back_populates="lab_instances")
    lab: Mapped[Lab] = relationship(back_populates="lab_instances")
    cluster: Mapped[ProxmoxCluster] = relationship(back_populates="lab_instances")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    student_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="SET NULL"), nullable=True
    )
    student_lab_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("student_lab_instances.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

