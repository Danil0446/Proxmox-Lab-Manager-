from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .dependencies import get_current_user
from .models import StudentLabInstance, StudentProfile, User
from .schemas import StudentLabInstanceRead


router = APIRouter(prefix="/me", tags=["student"])


@router.get("/labs", response_model=list[StudentLabInstanceRead])
async def list_my_labs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == user.id))
    student = result.scalar_one_or_none()
    if not student:
        return []

    lab_result = await db.execute(
        select(StudentLabInstance).where(StudentLabInstance.student_id == student.id)
    )
    instances = lab_result.scalars().all()
    return instances

