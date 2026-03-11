from typing import List, Literal, Optional, Dict
import time

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


StandStatus = Literal["idle", "starting", "running", "error"]


class StandResources(BaseModel):
    cpu: str
    memory: str
    disk: str


class Student(BaseModel):
    id: int
    name: str
    group: str
    email: str
    standStatus: StandStatus
    standStartedAt: Optional[int] = None  # Unix time in ms
    standResources: Optional[StandResources] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str


class StandsActionRequest(BaseModel):
    studentIds: List[int]


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_TOKEN = "admin-static-token"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _initial_students() -> Dict[int, Student]:
    # Начальные данные совпадают с mock в фронтенде
    students = [
        Student(
            id=1,
            name="Иван Иванов",
            group="JS-101",
            email="ivan@example.com",
            standStatus="idle",
            standStartedAt=None,
            standResources=StandResources(cpu="2 vCPU", memory="4 ГБ RAM", disk="40 ГБ"),
        ),
        Student(
            id=2,
            name="Анна Петрова",
            group="JS-101",
            email="anna@example.com",
            standStatus="running",
            standStartedAt=_now_ms() - 25 * 60 * 1000,
            standResources=StandResources(cpu="4 vCPU", memory="8 ГБ RAM", disk="60 ГБ"),
        ),
        Student(
            id=3,
            name="Сергей Смирнов",
            group="JS-102",
            email="sergey@example.com",
            standStatus="idle",
            standStartedAt=None,
            standResources=StandResources(cpu="2 vCPU", memory="4 ГБ RAM", disk="40 ГБ"),
        ),
    ]
    return {s.id: s for s in students}


students_db: Dict[int, Student] = _initial_students()


app = FastAPI(title="Student Stands API")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_current_admin(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.split(" ", 1)[1]
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")

    return ADMIN_USERNAME


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    if payload.username != ADMIN_USERNAME or payload.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    return LoginResponse(token=ADMIN_TOKEN)


@app.get("/students", response_model=List[Student])
async def list_students(_: str = Depends(get_current_admin)) -> List[Student]:
    # В реальном проекте здесь должна быть работа с БД
    return list(students_db.values())


@app.post("/stands/start", response_model=List[Student])
async def start_stands(
    payload: StandsActionRequest, _: str = Depends(get_current_admin)
) -> List[Student]:
    # Здесь можно интегрироваться с реальной системой поднятия стендов (VM, Docker, K8s и т.д.)
    now = _now_ms()
    for student_id in payload.studentIds:
        student = students_db.get(student_id)
        if not student:
            continue
        student.standStatus = "running"
        student.standStartedAt = now

    return list(students_db.values())


@app.post("/stands/stop", response_model=List[Student])
async def stop_stands(
    payload: StandsActionRequest, _: str = Depends(get_current_admin)
) -> List[Student]:
    for student_id in payload.studentIds:
        student = students_db.get(student_id)
        if not student:
            continue
        student.standStatus = "idle"
        student.standStartedAt = None

    return list(students_db.values())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

