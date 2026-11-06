"""Opt-in end-to-end check against MySQL exposed by Docker Compose."""

import os
import secrets

import mysql.connector
import pytest
from fastapi.testclient import TestClient

from API_uni import app, get_db

pytestmark = pytest.mark.integration


def test_real_mysql_enrollment_flow():
    if os.getenv("RUN_MYSQL_TESTS") != "1":
        pytest.skip("Set RUN_MYSQL_TESTS=1 to test the Docker MySQL instance")

    config = {
        "host": os.getenv("TEST_DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("TEST_DB_PORT", "3307")),
        "user": os.getenv("TEST_DB_USER", "uni_app"),
        "password": os.getenv("TEST_DB_PASSWORD", "local_app_password"),
        "database": os.getenv("TEST_DB_NAME", "uni"),
    }
    phone = f"+1202555{5000 + secrets.randbelow(5000):04d}"
    created_student_id = None

    def live_db():
        db = mysql.connector.connect(**config)
        try:
            yield db
        finally:
            db.close()

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = live_db
    try:
        with TestClient(app) as client:
            baseline = client.get("/analytics/overview")
            assert baseline.status_code == 200
            before = baseline.json()

            classes = client.get("/classes")
            assert classes.status_code == 200
            assert classes.json(), "The demo database must contain at least one class"
            selected_class = classes.json()[0]
            class_id = selected_class["id"]
            before_class_count = next(
                item["enrollment_count"] for item in before["enrollments_by_class"]
                if item["class_id"] == class_id
            )

            student = client.post("/students", json={"name": "Integration Student", "phone": phone})
            assert student.status_code == 201
            student_id = student.json()["id"]
            created_student_id = student_id

            enrollment = {"student_id": student_id, "class_id": class_id}
            new_enrollment = client.post("/enrollments", json=enrollment)
            assert new_enrollment.status_code == 201
            assert client.post("/enrollments", json=enrollment).status_code == 409
            assert client.post(
                "/students", json={"name": "Duplicate", "phone": phone}
            ).status_code == 409

            student_classes = client.get(f"/students/{student_id}/classes")
            assert student_classes.status_code == 200
            assert student_classes.json() == [selected_class]

            updated = client.get("/analytics/overview").json()
            assert updated["total_students"] == before["total_students"] + 1
            assert updated["total_classes"] == before["total_classes"]
            assert updated["total_enrollments"] == before["total_enrollments"] + 1
            assert updated["students_without_enrollments"] == before["students_without_enrollments"]
            after_class_count = next(
                item["enrollment_count"] for item in updated["enrollments_by_class"]
                if item["class_id"] == class_id
            )
            assert after_class_count == before_class_count + 1
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        # Remove the temporary student and enrollment even if an assertion fails.
        if created_student_id is not None:
            with mysql.connector.connect(**config) as db:
                with db.cursor() as cursor:
                    cursor.execute("DELETE FROM ENROLLinfo WHERE STDid = %s", (created_student_id,))
                    cursor.execute("DELETE FROM STDinfo WHERE id = %s", (created_student_id,))
                db.commit()
