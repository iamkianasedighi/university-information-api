"""University records and enrollment statistics, built with FastAPI and MySQL."""

import logging
import os

import mysql.connector
from mysql.connector import errorcode
from fastapi import Depends, FastAPI, HTTPException, Path, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="University Information API", version="2.0.0")
logger = logging.getLogger(__name__)

OVERVIEW_SQL = """
SELECT
    (SELECT COUNT(*) FROM STDinfo) AS total_students,
    (SELECT COUNT(*) FROM CLASSinfo) AS total_classes,
    (SELECT COUNT(*) FROM ENROLLinfo) AS total_enrollments,
    (SELECT COUNT(*) FROM STDinfo AS s
     WHERE NOT EXISTS (
         SELECT 1 FROM ENROLLinfo AS e WHERE e.STDid = s.id
     )) AS students_without_enrollments
"""

CLASS_ENROLLMENTS_SQL = """
SELECT c.id AS class_id, c.name AS class_name,
       COUNT(e.id) AS enrollment_count
FROM CLASSinfo AS c
LEFT JOIN ENROLLinfo AS e ON e.CLASSid = c.id
GROUP BY c.id, c.name
ORDER BY enrollment_count DESC, c.id
"""


class StudentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$", max_length=16)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Name cannot be blank")
        return name


class StudentOut(BaseModel):
    id: int
    name: str


class ClassOut(BaseModel):
    id: int
    name: str
    teacher_id: int
    teacher_name: str


class EnrollmentCreate(BaseModel):
    student_id: int = Field(gt=0)
    class_id: int = Field(gt=0)


class EnrollmentOut(EnrollmentCreate):
    id: int


class ClassCount(BaseModel):
    class_id: int
    class_name: str
    enrollment_count: int


class OverviewOut(BaseModel):
    total_students: int
    total_classes: int
    total_enrollments: int
    students_without_enrollments: int
    enrollments_by_class: list[ClassCount]
    most_popular_class: ClassCount | None


def get_db():
    try:
        db = mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "uni"),
            connection_timeout=5,
        )
    except mysql.connector.Error:
        logger.exception("Could not connect to MySQL")
        raise HTTPException(status_code=503, detail="Database unavailable") from None

    try:
        yield db
    finally:
        db.close()


@app.exception_handler(mysql.connector.Error)
async def database_error_handler(request: Request, exc: mysql.connector.Error):
    logger.error("Database error at %s: %s", request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Database operation failed"})


@app.get("/students", response_model=list[StudentOut])
def list_students(db=Depends(get_db)):
    with db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT id, name FROM STDinfo ORDER BY id")
        return cursor.fetchall()


@app.post(
    "/students",
    status_code=201,
    response_model=StudentOut,
    responses={409: {"description": "Phone number is already registered"}},
)
def create_student(data: StudentCreate, db=Depends(get_db)):
    try:
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO STDinfo (name, phone) VALUES (%s, %s)",
                (data.name, data.phone),
            )
            student_id = cursor.lastrowid
        db.commit()
    except mysql.connector.IntegrityError as exc:
        db.rollback()
        if exc.errno == errorcode.ER_DUP_ENTRY:
            raise HTTPException(status_code=409, detail="Phone number already registered") from None
        raise
    except mysql.connector.Error:
        db.rollback()
        raise
    return {"id": student_id, "name": data.name}


@app.get("/students/{student_id}", response_model=StudentOut)
def get_student(student_id: int = Path(gt=0), db=Depends(get_db)):
    with db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT id, name FROM STDinfo WHERE id = %s", (student_id,))
        student = cursor.fetchone()
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@app.get("/classes", response_model=list[ClassOut])
def list_classes(db=Depends(get_db)):
    with db.cursor(dictionary=True) as cursor:
        cursor.execute(
            """
            SELECT c.id, c.name, p.id AS teacher_id, p.name AS teacher_name
            FROM CLASSinfo AS c
            JOIN PROFinfo AS p ON p.id = c.teacher
            ORDER BY c.id
            """
        )
        return cursor.fetchall()


@app.get("/students/{student_id}/classes", response_model=list[ClassOut])
def student_classes(student_id: int = Path(gt=0), db=Depends(get_db)):
    with db.cursor(dictionary=True, buffered=True) as cursor:
        cursor.execute("SELECT id FROM STDinfo WHERE id = %s", (student_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Student not found")
        cursor.execute(
            """
            SELECT c.id, c.name, p.id AS teacher_id, p.name AS teacher_name
            FROM ENROLLinfo AS e
            JOIN CLASSinfo AS c ON c.id = e.CLASSid
            JOIN PROFinfo AS p ON p.id = c.teacher
            WHERE e.STDid = %s
            ORDER BY c.id
            """,
            (student_id,),
        )
        return cursor.fetchall()


@app.post(
    "/enrollments",
    status_code=201,
    response_model=EnrollmentOut,
    responses={
        404: {"description": "Student or class does not exist"},
        409: {"description": "Student is already enrolled in this class"},
    },
)
def create_enrollment(data: EnrollmentCreate, db=Depends(get_db)):
    try:
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO ENROLLinfo (STDid, CLASSid) VALUES (%s, %s)",
                (data.student_id, data.class_id),
            )
            enrollment_id = cursor.lastrowid
        db.commit()
    except mysql.connector.IntegrityError as exc:
        db.rollback()
        if exc.errno == errorcode.ER_DUP_ENTRY:
            raise HTTPException(status_code=409, detail="Student already enrolled in this class") from None
        if exc.errno == errorcode.ER_NO_REFERENCED_ROW_2:
            raise HTTPException(status_code=404, detail="Student or class not found") from None
        raise
    except mysql.connector.Error:
        db.rollback()
        raise
    return {"id": enrollment_id, "student_id": data.student_id, "class_id": data.class_id}


@app.get("/analytics/overview", response_model=OverviewOut)
def enrollment_overview(db=Depends(get_db)):
    with db.cursor(dictionary=True, buffered=True) as cursor:
        cursor.execute(OVERVIEW_SQL)
        totals = cursor.fetchone()
        cursor.execute(CLASS_ENROLLMENTS_SQL)
        counts = cursor.fetchall()

    # A class with zero enrollments should not be called most popular.
    popular = counts[0] if counts and counts[0]["enrollment_count"] > 0 else None
    return {**totals, "enrollments_by_class": counts, "most_popular_class": popular}
