import asyncio
import re
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import AsyncSessionLocal

from .config import get_settings
from .database import get_db
from .dependencies import get_current_admin
from .models import (
    Lab,
    LabInstanceStatus,
    ProxmoxAccount,
    ProxmoxCluster,
    StudentLabInstance,
    StudentProfile,
    User,
    UserRole,
)
from .proxmox_client import ProxmoxClient
from .schemas import (
    LabBatchCreate,
    LabCreate,
    LabRead,
    PowerActionRequest,
    ProxmoxClusterRead,
    StandsByTemplatesRequest,
    StudentLabInstanceRead,
    StudentProfileRead,
    UserCreate,
    UserRead,
)
from .security import get_password_hash


router = APIRouter(prefix="/admin", tags=["admin"])


def _normalize_proxmox_userid(login: str, realm: str) -> str:
    """
    Приводит логин к формату, принимаемому Proxmox API (username@realm).
    Proxmox ожидает: имя только из букв/цифр/точки/дефиса/подчёркивания, лучше с маленькой буквы.
    """
    raw = (login or "").strip().split("@")[0]
    raw = raw.lower()
    raw = re.sub(r"[^a-z0-9._-]", "_", raw)
    raw = raw.strip("._-") or "user"
    if raw[0].isdigit():
        raw = "u" + raw
    realm_clean = realm.strip().lower() if realm else "pve"
    return f"{raw}@{realm_clean}"


def _parse_template_vmids(s: str) -> list[int]:
    """Парсит «101-103» или «101, 102, 103» в список VMID."""
    s = s.strip().replace(" ", "")
    if not s:
        return []
    out: list[int] = []
    for part in s.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                lo, hi = int(a.strip()), int(b.strip())
                if lo <= hi:
                    out.extend(range(lo, hi + 1))
            except ValueError:
                continue
        else:
            try:
                out.append(int(part))
            except ValueError:
                continue
    return sorted(set(out))


async def _create_proxmox_user_background(
    student_id: int,
    login: str,
    password: str,
    realm: str,
) -> None:
    """Фоновая задача: создание учётки в Proxmox и запись ProxmoxAccount. Не блокирует ответ пользователю."""
    async with AsyncSessionLocal() as db:
        try:
            settings = get_settings()
            cluster_result = await db.execute(select(ProxmoxCluster).where(ProxmoxCluster.is_default.is_(True)))
            cluster = cluster_result.scalar_one_or_none()
            if not cluster:
                cluster = ProxmoxCluster(
                    name="default",
                    api_url=settings.proxmox_api_url,
                    token_id=settings.proxmox_token_id,
                    token_name=settings.proxmox_token_id,
                    default_node=settings.proxmox_default_node,
                    is_default=True,
                )
                db.add(cluster)
                await db.flush()
            userid = _normalize_proxmox_userid(login, realm)
            proxmox = ProxmoxClient.from_settings()
            if not proxmox.user_exists(userid):
                proxmox.create_user(userid=userid, password=password, enable=1)
            existing = await db.execute(
                select(ProxmoxAccount).where(
                    ProxmoxAccount.student_id == student_id,
                    ProxmoxAccount.proxmox_cluster_id == cluster.id,
                )
            )
            if existing.scalar_one_or_none():
                pass
            else:
                db.add(
                    ProxmoxAccount(
                        student_id=student_id,
                        proxmox_cluster_id=cluster.id,
                        userid=userid,
                        realm=realm,
                    )
                )
            await db.commit()
        except Exception:
            await db.rollback()


def _proxmox_assign_vm_sync(
    proxmox: ProxmoxClient,
    node: str,
    use_existing_vm: bool,
    template_vmid: int,
    clone_name: str,
    student_userid: str | None,
    student_role: str,
) -> int:
    """Синхронные вызовы Proxmox (клон, ACL, имя ВМ, Notes, start). Выполнять в пуле потоков."""
    if use_existing_vm:
        vmid = template_vmid
    else:
        vmid = proxmox.clone_vm(node=node, vmid=template_vmid, name=clone_name)
    try:
        proxmox.set_vm_name(node=node, vmid=vmid, name=clone_name)
    except Exception:
        pass
    vm_acl_path = f"/vms/{vmid}"
    if student_userid:
        proxmox.set_acl(path=vm_acl_path, users=student_userid, roles=student_role, propagate=0)
        try:
            proxmox.set_vm_description(node=node, vmid=vmid, description=f"УЗ: {student_userid}")
        except Exception:
            pass
    try:
        proxmox.vm_status_action(node=node, vmid=vmid, action="start")
    except Exception:
        pass
    return vmid


@router.post("/students", response_model=StudentProfileRead)
async def create_student(
    payload: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    existing = await db.execute(select(User).where(User.email == payload.login))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Логин уже занят")

    user = User(
        email=payload.login,
        password_hash=get_password_hash(payload.password),
        role=UserRole.STUDENT,
    )
    db.add(user)
    await db.flush()

    student = StudentProfile(
        user_id=user.id,
        full_name=payload.full_name,
        group_name=payload.group_name,
        external_id=payload.external_id,
    )
    db.add(student)
    await db.flush()

    await db.commit()
    await db.refresh(student)
    await db.refresh(user)

    settings = get_settings()
    cluster_result = await db.execute(select(ProxmoxCluster).where(ProxmoxCluster.is_default.is_(True)))
    cluster = cluster_result.scalar_one_or_none()
    if not cluster:
        cluster = ProxmoxCluster(
            name="default",
            api_url=settings.proxmox_api_url,
            token_id=settings.proxmox_token_id,
            token_name=settings.proxmox_token_id,
            default_node=settings.proxmox_default_node,
            is_default=True,
        )
        db.add(cluster)
        await db.commit()
        await db.refresh(cluster)

    background_tasks.add_task(
        _create_proxmox_user_background,
        student.id,
        payload.login,
        payload.password,
        settings.proxmox_student_realm,
    )

    user_read = UserRead(
        id=user.id,
        login=user.email,
        role=user.role,
        is_active=user.is_active,
    )
    proxmox_login = _normalize_proxmox_userid(payload.login, settings.proxmox_student_realm)
    return StudentProfileRead(
        id=student.id,
        user=user_read,
        full_name=student.full_name,
        group_name=student.group_name,
        external_id=student.external_id,
        created_at=student.created_at,
        proxmox_login=proxmox_login,
    )


@router.get("/students", response_model=list[StudentProfileRead])
async def list_students(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    result = await db.execute(
        select(StudentProfile, User)
        .join(User, StudentProfile.user_id == User.id)
        .order_by(StudentProfile.id)
    )
    rows = result.all()
    cluster_result = await db.execute(select(ProxmoxCluster).where(ProxmoxCluster.is_default.is_(True)))
    default_cluster = cluster_result.scalar_one_or_none()
    acc_map: dict[int, str] = {}
    if default_cluster:
        accs = await db.execute(
            select(ProxmoxAccount.student_id, ProxmoxAccount.userid).where(
                ProxmoxAccount.proxmox_cluster_id == default_cluster.id
            )
        )
        for sid, userid in accs.all():
            acc_map[sid] = userid
    out: list[StudentProfileRead] = []
    for student, user in rows:
        user_read = UserRead(
            id=user.id,
            login=user.email,
            role=user.role,
            is_active=user.is_active,
        )
        out.append(
            StudentProfileRead(
                id=student.id,
                user=user_read,
                full_name=student.full_name,
                group_name=student.group_name,
                external_id=student.external_id,
                created_at=student.created_at,
                proxmox_login=acc_map.get(student.id) or _normalize_proxmox_userid(user.email, get_settings().proxmox_student_realm),
            )
        )
    return out


@router.delete("/students", status_code=204)
async def delete_all_students(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Удаляет всех студентов, их профили, стенды и учётки в Proxmox.
    Админов не трогаем.
    """
    settings = get_settings()
    proxmox = ProxmoxClient.from_settings()

    # Сначала выбираем все стенды и proxmox-аккаунты, чтобы удалить ВМ и пользователей в Proxmox.
    instances_result = await db.execute(select(StudentLabInstance))
    instances = instances_result.scalars().all()
    accounts_result = await db.execute(select(ProxmoxAccount))
    accounts = accounts_result.scalars().all()

    # Удаляем все ВМ в Proxmox, связанные со студентами (клонированные; существующие только снимаем ACL).
    for inst in instances:
        node = inst.node or settings.proxmox_default_node
        vm_acl_path = f"/vms/{inst.proxmox_vmid}"
        lab_result = await db.execute(select(Lab).where(Lab.id == inst.lab_id))
        lab = lab_result.scalar_one_or_none()
        use_existing = lab.use_existing_vm if lab else False
        acc_result = await db.execute(
            select(ProxmoxAccount).where(
                ProxmoxAccount.student_id == inst.student_id,
                ProxmoxAccount.proxmox_cluster_id == inst.proxmox_cluster_id,
            )
        )
        acc = acc_result.scalar_one_or_none()
        if acc:
            try:
                proxmox.set_acl(
                    path=vm_acl_path,
                    users=acc.userid,
                    roles=settings.proxmox_student_role,
                    propagate=0,
                    delete=1,
                )
            except Exception:
                pass
        if use_existing:
            try:
                proxmox.set_vm_description(node=node, vmid=inst.proxmox_vmid, description="")
            except Exception:
                pass
        else:
            try:
                proxmox.delete_vm(node=node, vmid=inst.proxmox_vmid)
            except Exception:
                pass

    # Никогда не удалять в Proxmox: root и владельца API-токена (иначе потеряете доступ к prod).
    token_owner = (settings.proxmox_token_id or "").split("!")[0].strip()
    proxmox_never_delete = {"root@pam", "root@pve"}
    if token_owner:
        proxmox_never_delete.add(token_owner)

    for acc in accounts:
        if acc.userid in proxmox_never_delete:
            continue
        try:
            proxmox.delete_user(acc.userid)
        except Exception:
            pass

    # Дополнительно: удаляем из Proxmox только учётки студентов (realm @pve), не трогая root и токен.
    realm_suffix = f"@{settings.proxmox_student_realm}"
    try:
        for u in proxmox.list_users():
            userid = (u.get("userid") or "").strip()
            if not userid or userid in proxmox_never_delete:
                continue
            if userid.startswith("root@"):
                continue
            if userid.endswith(realm_suffix):
                try:
                    proxmox.delete_user(userid)
                except Exception:
                    pass
    except Exception:
        pass

    # После этого чистим БД.
    await db.execute(delete(StudentLabInstance))
    await db.execute(delete(ProxmoxAccount))
    await db.execute(delete(StudentProfile))
    await db.execute(delete(User).where(User.role == UserRole.STUDENT))
    await db.commit()


@router.delete("/students/{student_id}", status_code=204)
async def delete_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Удаляет одного студента, его профиль, все его стенды и учётку в Proxmox.
    """
    settings = get_settings()
    proxmox = ProxmoxClient.from_settings()

    # Находим proxmox-аккаунт студента (userid для Proxmox).
    acc_result = await db.execute(select(ProxmoxAccount).where(ProxmoxAccount.student_id == student_id))
    acc = acc_result.scalar_one_or_none()

    # Удаляем все стенды этого студента: ACL + ВМ в Proxmox.
    instances_result = await db.execute(
        select(StudentLabInstance).where(StudentLabInstance.student_id == student_id)
    )
    instances = instances_result.scalars().all()
    for inst in instances:
        node = inst.node or settings.proxmox_default_node
        vm_acl_path = f"/vms/{inst.proxmox_vmid}"
        lab_result = await db.execute(select(Lab).where(Lab.id == inst.lab_id))
        lab = lab_result.scalar_one_or_none()
        use_existing = lab.use_existing_vm if lab else False
        if acc:
            try:
                proxmox.set_acl(
                    path=vm_acl_path,
                    users=acc.userid,
                    roles=settings.proxmox_student_role,
                    propagate=0,
                    delete=1,
                )
            except Exception:
                pass
        if use_existing:
            try:
                proxmox.set_vm_description(node=node, vmid=inst.proxmox_vmid, description="")
            except Exception:
                pass
        else:
            try:
                proxmox.delete_vm(node=node, vmid=inst.proxmox_vmid)
            except Exception:
                pass

    # Удаляем proxmox-пользователя (никогда не удаляем root и владельца API-токена).
    if acc:
        token_owner = (get_settings().proxmox_token_id or "").split("!")[0].strip()
        safe = acc.userid not in ("root@pam", "root@pve") and acc.userid != token_owner and not acc.userid.startswith("root@")
        if safe:
            try:
                proxmox.delete_user(acc.userid)
            except Exception:
                pass

    # Чистим записи в БД.
    await db.execute(delete(StudentLabInstance).where(StudentLabInstance.student_id == student_id))
    await db.execute(delete(ProxmoxAccount).where(ProxmoxAccount.student_id == student_id))
    await db.execute(delete(StudentProfile).where(StudentProfile.id == student_id))
    subq = select(User.id).join(StudentProfile, StudentProfile.user_id == User.id).where(
        StudentProfile.id == student_id, User.role == UserRole.STUDENT
    )
    await db.execute(delete(User).where(User.id.in_(subq)))
    await db.commit()


@router.get("/student-labs", response_model=list[StudentLabInstanceRead])
async def list_all_student_labs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    result = await db.execute(select(StudentLabInstance))
    instances = result.scalars().all()
    return instances


@router.post("/labs", response_model=LabRead)
async def create_lab(
    payload: LabCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    lab = Lab(
        name=payload.name,
        description=payload.description,
        proxmox_cluster_id=payload.proxmox_cluster_id,
        template_type=payload.template_type,
        template_vmid=payload.template_vmid,
        use_existing_vm=payload.use_existing_vm,
        default_node=payload.default_node,
        cpu_limit=payload.cpu_limit,
        memory_mb=payload.memory_mb,
        disk_gb=payload.disk_gb,
    )
    db.add(lab)
    await db.commit()
    await db.refresh(lab)
    return lab


@router.post("/labs/batch", response_model=list[LabRead])
async def create_labs_batch(
    payload: LabBatchCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Создать несколько шаблонов стендов по VMID: «100-103» (100,101,102,103) или «101, 103».
    """
    vmids = _parse_template_vmids(payload.template_vmids)
    if not vmids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Укажите VMID через запятую или диапазон, например: 100-103 или 101, 103',
        )
    prefix = (payload.name_prefix or "Шаблон").strip() or "Шаблон"
    created: list[Lab] = []
    for vmid in vmids:
        lab = Lab(
            name=f"{prefix} {vmid}".strip(),
            proxmox_cluster_id=payload.proxmox_cluster_id,
            template_type=payload.template_type,
            template_vmid=vmid,
            use_existing_vm=payload.use_existing_vm,
            default_node=payload.default_node,
        )
        db.add(lab)
        await db.flush()
        await db.refresh(lab)
        created.append(lab)
    await db.commit()
    return created


@router.get("/labs", response_model=list[LabRead])
async def list_labs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    result = await db.execute(select(Lab))
    labs = result.scalars().all()
    return labs


@router.delete("/labs", status_code=204)
async def delete_all_labs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Удаляет все шаблоны стендов (лабы).
    Уже выданные стенды студентам не трогаем, поэтому
    запрещаем удаление, если существуют связанные экземпляры.
    """
    has_instances = await db.execute(select(StudentLabInstance).limit(1))
    if has_instances.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя удалить шаблоны: существуют выданные стенды студентов",
        )
    await db.execute(delete(Lab))
    await db.commit()


@router.get("/clusters/default", response_model=ProxmoxClusterRead)
async def get_default_cluster(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Возвращает кластер Proxmox по умолчанию, создавая его при необходимости
    по значениям из .env.
    """
    settings = get_settings()
    cluster_result = await db.execute(select(ProxmoxCluster).where(ProxmoxCluster.is_default.is_(True)))
    cluster = cluster_result.scalar_one_or_none()
    if not cluster:
        cluster = ProxmoxCluster(
            name="default",
            api_url=settings.proxmox_api_url,
            token_id=settings.proxmox_token_id,
            token_name=settings.proxmox_token_id,
            default_node=settings.proxmox_default_node,
            is_default=True,
        )
        db.add(cluster)
        await db.commit()
        await db.refresh(cluster)
    else:
        # Если в .env сменился PROXMOX_DEFAULT_NODE — синхронизируем его с записью кластера,
        # чтобы не оставаться на старом значении (например, "pve" вместо "Debian").
        if settings.proxmox_default_node and cluster.default_node != settings.proxmox_default_node:
            cluster.default_node = settings.proxmox_default_node
            await db.commit()
            await db.refresh(cluster)
    return cluster


@router.post("/students/{student_id}/labs/{lab_id}", response_model=StudentLabInstanceRead)
async def assign_lab_to_student(
    student_id: int,
    lab_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    student_result = await db.execute(select(StudentProfile).where(StudentProfile.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    lab_result = await db.execute(select(Lab).where(Lab.id == lab_id))
    lab = lab_result.scalar_one_or_none()
    if not lab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")

    cluster_result = await db.execute(select(ProxmoxCluster).where(ProxmoxCluster.id == lab.proxmox_cluster_id))
    cluster = cluster_result.scalar_one()

    settings = get_settings()
    proxmox = ProxmoxClient.from_settings()

    node = lab.default_node or cluster.default_node or settings.proxmox_default_node
    name = f"lab-{lab.id}-student-{student.id}"

    if lab.use_existing_vm:
        proxmox_vmid = lab.template_vmid
        existing = await db.execute(
            select(StudentLabInstance).where(
                StudentLabInstance.proxmox_vmid == proxmox_vmid,
                StudentLabInstance.proxmox_cluster_id == cluster.id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ВМ с VMID {proxmox_vmid} уже назначена другому студенту",
            )

    prox_result = await db.execute(
        select(ProxmoxAccount).where(
            ProxmoxAccount.student_id == student.id,
            ProxmoxAccount.proxmox_cluster_id == cluster.id,
        )
    )
    prox_acc = prox_result.scalar_one_or_none()
    if not prox_acc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Учётка студента в Proxmox ещё создаётся. Подождите 5–10 сек и нажмите «Выдать стенд» снова.",
        )
    student_userid = prox_acc.userid

    try:
        proxmox_vmid = await asyncio.to_thread(
            _proxmox_assign_vm_sync,
            proxmox,
            node,
            lab.use_existing_vm,
            lab.template_vmid,
            name,
            student_userid,
            settings.proxmox_student_role,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка Proxmox при выдаче стенда: {e}",
        )

    instance = StudentLabInstance(
        student_id=student.id,
        lab_id=lab.id,
        proxmox_cluster_id=cluster.id,
        proxmox_vmid=proxmox_vmid,
        node=node,
        status=LabInstanceStatus.RUNNING,
        name_in_proxmox=name,
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    return instance


@router.delete("/student-labs/{instance_id}", status_code=204)
async def delete_student_lab(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Удалить стенд: снять ACL в Proxmox; для клонированных ВМ — уничтожить, для существующих — только снять права и очистить Notes."""
    result = await db.execute(select(StudentLabInstance).where(StudentLabInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стенд не найден")

    lab_result = await db.execute(select(Lab).where(Lab.id == instance.lab_id))
    lab = lab_result.scalar_one_or_none()
    use_existing = lab.use_existing_vm if lab else False

    settings = get_settings()
    proxmox = ProxmoxClient.from_settings()
    node = instance.node or settings.proxmox_default_node
    vm_acl_path = f"/vms/{instance.proxmox_vmid}"

    prox_result = await db.execute(
        select(ProxmoxAccount).where(
            ProxmoxAccount.student_id == instance.student_id,
            ProxmoxAccount.proxmox_cluster_id == instance.proxmox_cluster_id,
        )
    )
    prox_acc = prox_result.scalar_one_or_none()
    if prox_acc:
        try:
            proxmox.set_acl(
                path=vm_acl_path,
                users=prox_acc.userid,
                roles=settings.proxmox_student_role,
                propagate=0,
                delete=1,
            )
        except Exception:
            pass
    if use_existing:
        try:
            proxmox.set_vm_description(node=node, vmid=instance.proxmox_vmid, description="")
        except Exception:
            pass
    else:
        try:
            proxmox.delete_vm(node=node, vmid=instance.proxmox_vmid)
        except Exception:
            pass
    await db.delete(instance)
    await db.commit()


@router.post("/students/{student_id}/stands", response_model=list[StudentLabInstanceRead])
async def assign_stands_by_templates(
    student_id: int,
    payload: StandsByTemplatesRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Выдать стенды по шаблонам: «101-103» или «101, 102, 103».
    Для каждого VMID ищется лаба с template_vmid; создаётся клон и ACL.
    """
    vmids = _parse_template_vmids(payload.templates)
    if not vmids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Укажите шаблоны, например: 101-103 или 101, 102, 103',
        )

    student_result = await db.execute(select(StudentProfile).where(StudentProfile.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    cluster_result = await db.execute(select(ProxmoxCluster).where(ProxmoxCluster.is_default.is_(True)))
    cluster = cluster_result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Кластер Proxmox не настроен",
        )

    settings = get_settings()
    proxmox = ProxmoxClient.from_settings()
    prox_result = await db.execute(
        select(ProxmoxAccount).where(
            ProxmoxAccount.student_id == student.id,
            ProxmoxAccount.proxmox_cluster_id == cluster.id,
        )
    )
    prox_acc = prox_result.scalar_one_or_none()
    if not prox_acc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Учётка студента в Proxmox ещё создаётся. Подождите 5–10 сек и попробуйте снова.",
        )
    student_userid = prox_acc.userid

    created: list[StudentLabInstanceRead] = []
    username = student_userid.split("@")[0]
    for idx, template_vmid in enumerate(vmids):
        lab_result = await db.execute(
            select(Lab).where(Lab.proxmox_cluster_id == cluster.id, Lab.template_vmid == template_vmid)
        )
        lab = lab_result.scalars().first()
        if not lab:
            lab = Lab(
                name=f"Шаблон {template_vmid}",
                template_vmid=template_vmid,
                template_type="qemu",
                proxmox_cluster_id=cluster.id,
                default_node=cluster.default_node or settings.proxmox_default_node,
            )
            db.add(lab)
            await db.flush()
        node = lab.default_node or cluster.default_node or settings.proxmox_default_node
        name = f"lab-{lab.id}-student-{student.id}-{idx + 1}-{username}"
        try:
            proxmox_vmid = await asyncio.to_thread(
                _proxmox_assign_vm_sync,
                proxmox,
                node,
                False,
                lab.template_vmid,
                name,
                student_userid,
                settings.proxmox_student_role,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Ошибка Proxmox при выдаче стенда (VMID {template_vmid}): {e}. Уже создано машин: {len(created)}.",
            )
        instance = StudentLabInstance(
            student_id=student.id,
            lab_id=lab.id,
            proxmox_cluster_id=cluster.id,
            proxmox_vmid=proxmox_vmid,
            node=node,
            status=LabInstanceStatus.RUNNING,
            name_in_proxmox=name,
        )
        db.add(instance)
        await db.flush()
        await db.commit()
        await db.refresh(instance)
        created.append(
            StudentLabInstanceRead(
                id=instance.id,
                lab_id=instance.lab_id,
                student_id=instance.student_id,
                proxmox_cluster_id=instance.proxmox_cluster_id,
                proxmox_vmid=instance.proxmox_vmid,
                node=instance.node or "",
                status=instance.status,
                ip_address=instance.ip_address,
                name_in_proxmox=instance.name_in_proxmox,
                created_at=instance.created_at,
            )
        )
    return created


@router.post("/student-labs/{instance_id}/power", response_model=StudentLabInstanceRead)
async def control_lab_power(
    instance_id: int,
    payload: PowerActionRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    result = await db.execute(select(StudentLabInstance).where(StudentLabInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance not found")

    settings = get_settings()
    proxmox = ProxmoxClient.from_settings()
    node = instance.node or settings.proxmox_default_node

    proxmox.vm_status_action(node=node, vmid=instance.proxmox_vmid, action=payload.action)

    if payload.action == "start":
        instance.status = LabInstanceStatus.RUNNING
    elif payload.action == "stop":
        instance.status = LabInstanceStatus.STOPPED

    await db.commit()
    await db.refresh(instance)
    return instance

