from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import User, UserRole
from .schemas import AdminInitRequest, Token
from .security import create_access_token, verify_password


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    username = (form_data.username or "").strip()
    result = await db.execute(select(User).where(User.email == username))
    user = result.scalar_one_or_none()
    if not user and username.lower() == "admin":
        result = await db.execute(select(User).where(User.email == "Admin"))
        user = result.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")

    token = create_access_token({"user_id": user.id, "role": user.role})
    return Token(access_token=token)


@router.post("/init-admin", response_model=Token)
async def init_admin(
    payload: AdminInitRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Инициализация первого администратора:
    логин/пароль задаются через payload.
    """
    admin_exists_result = await db.execute(select(User).where(User.role == UserRole.ADMIN))
    if admin_exists_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Администратор уже инициализирован. Используйте обычный вход.",
        )

    email = (payload.login or "").strip()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Логин администратора обязателен")

    from .security import get_password_hash

    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Логин уже занят")

    user = User(
        email=email,
        password_hash=get_password_hash(payload.password),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"user_id": user.id, "role": user.role})
    return Token(access_token=token)

