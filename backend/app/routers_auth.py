from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import User, UserRole
from .schemas import Token
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
    db: AsyncSession = Depends(get_db),
):
    """
    Упрощённый эндпоинт для первого запуска:
    создаёт администратора Admin / Admin,
    если его ещё нет, и выдаёт токен.
    """
    email = "Admin"
    from .security import get_password_hash

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            email=email,
            password_hash=get_password_hash("Admin"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token({"user_id": user.id, "role": user.role})
    return Token(access_token=token)

