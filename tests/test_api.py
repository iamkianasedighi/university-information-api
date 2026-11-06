from collections import deque

import mysql.connector
import pytest
from fastapi.testclient import TestClient
from mysql.connector import errorcode

from API_uni import app, get_db


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.lastrowid = db.new_id
        self.rows = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.cursors_closed += 1

    def execute(self, sql, params=None):
        self.db.statements.append((sql, params))
        if self.db.error:
            raise self.db.error
        if sql.lstrip().upper().startswith("SELECT"):
            self.rows = self.db.results.popleft()

    def fetchone(self):
        return self.rows

    def fetchall(self):
        return self.rows


class FakeDatabase:
    def __init__(self, *results, error=None, new_id=21):
        self.results = deque(results)
        self.statements = []
        self.error = error
        self.new_id = new_id
        self.committed = False
        self.rolled_back = False
        self.cursors_closed = 0
        self.closed = False

    def cursor(self, **kwargs):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def use_db(db):
    app.dependency_overrides[get_db] = lambda: db


def test_list_students_omits_phones(client):
    db = FakeDatabase([{"id": 1, "name": "Anna", "phone": "+12025550100"}])
    use_db(db)
    response = client.get("/students")
    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "Anna"}]
    assert "phone" not in db.statements[0][0].lower()
    assert db.cursors_closed == 1


def test_get_student_and_missing_student(client):
    use_db(FakeDatabase({"id": 1, "name": "Anna"}))
    assert client.get("/students/1").json() == {"id": 1, "name": "Anna"}
    use_db(FakeDatabase(None))
    assert client.get("/students/99").status_code == 404
    assert client.get("/students/0").status_code == 422


def test_student_insert_is_parameterized(client):
    db = FakeDatabase()
    use_db(db)
    response = client.post("/students", json={"name": "  O'Connor  ", "phone": "+12025550188"})
    assert response.status_code == 201
    assert response.json() == {"id": 21, "name": "O'Connor"}
    assert db.statements == [
        ("INSERT INTO STDinfo (name, phone) VALUES (%s, %s)", ("O'Connor", "+12025550188"))
    ]
    assert db.committed and db.cursors_closed == 1


def test_duplicate_phone_returns_409(client):
    db = FakeDatabase(error=mysql.connector.IntegrityError(errno=errorcode.ER_DUP_ENTRY))
    use_db(db)
    result = client.post("/students", json={"name": "Sara", "phone": "+12025550100"})
    assert result.status_code == 409
    assert db.rolled_back and not db.committed


@pytest.mark.parametrize("payload", [
    {"name": "   ", "phone": "+12025550199"},
    {"name": "Ana", "phone": 12345678},
    {"name": "Ana", "phone": "12345678"},
    {"name": "Ana", "phone": "+123"},
    {"name": "Ana", "phone": "+1202555010011111111111"},
])
def test_reject_invalid_students(client, payload):
    db = FakeDatabase()
    use_db(db)
    assert client.post("/students", json=payload).status_code == 422
    assert not db.statements


def test_classes_include_teachers(client):
    result = [{"id": 1, "name": "Databases", "teacher_id": 1, "teacher_name": "Dr. Weber"}]
    use_db(FakeDatabase(result))
    assert client.get("/classes").json() == result


def test_students_can_have_multiple_classes(client):
    classes = [
        {"id": 1, "name": "Databases", "teacher_id": 1, "teacher_name": "Dr. Weber"},
        {"id": 2, "name": "Algorithms", "teacher_id": 2, "teacher_name": "Dr. Fischer"},
    ]
    db = FakeDatabase({"id": 1}, classes)
    use_db(db)
    assert client.get("/students/1/classes").json() == classes
    assert db.statements[1][1] == (1,)


def test_unenrolled_student_returns_empty_list(client):
    use_db(FakeDatabase({"id": 14}, []))
    assert client.get("/students/14/classes").json() == []
    use_db(FakeDatabase(None))
    assert client.get("/students/999/classes").status_code == 404


def test_enrollment_is_parameterized_and_committed(client):
    db = FakeDatabase(new_id=19)
    use_db(db)
    response = client.post("/enrollments", json={"student_id": 14, "class_id": 6})
    assert response.status_code == 201
    assert response.json() == {"id": 19, "student_id": 14, "class_id": 6}
    assert db.statements == [
        ("INSERT INTO ENROLLinfo (STDid, CLASSid) VALUES (%s, %s)", (14, 6))
    ]
    assert db.committed


@pytest.mark.parametrize("errno,status", [
    (errorcode.ER_DUP_ENTRY, 409),
    (errorcode.ER_NO_REFERENCED_ROW_2, 404),
])
def test_enrollment_constraint_errors(client, errno, status):
    db = FakeDatabase(error=mysql.connector.IntegrityError(errno=errno))
    use_db(db)
    response = client.post("/enrollments", json={"student_id": 1, "class_id": 1})
    assert response.status_code == status
    assert db.rolled_back and not db.committed


def test_invalid_enrollment_returns_422(client):
    db = FakeDatabase()
    use_db(db)
    assert client.post("/enrollments", json={"student_id": 0, "class_id": 1}).status_code == 422
    assert not db.statements


def test_analytics_response(client):
    counts = [
        {"class_id": 1, "class_name": "Databases", "enrollment_count": 5},
        {"class_id": 6, "class_name": "Data Visualization", "enrollment_count": 0},
    ]
    db = FakeDatabase(
        {"total_students": 20, "total_classes": 6, "total_enrollments": 18,
         "students_without_enrollments": 7},
        counts,
    )
    use_db(db)
    result = client.get("/analytics/overview")
    assert result.status_code == 200
    assert result.json()["most_popular_class"] == counts[0]
    assert result.json()["students_without_enrollments"] == 7
    assert "NOT EXISTS" in db.statements[0][0]
    assert "LEFT JOIN" in db.statements[1][0]


def test_no_popular_class_when_all_empty(client):
    use_db(FakeDatabase(
        {"total_students": 1, "total_classes": 1, "total_enrollments": 0,
         "students_without_enrollments": 1},
        [{"class_id": 1, "class_name": "Databases", "enrollment_count": 0}],
    ))
    assert client.get("/analytics/overview").json()["most_popular_class"] is None


def test_mysql_error_does_not_leak_details(client):
    use_db(FakeDatabase(error=mysql.connector.Error("secret database message")))
    response = client.get("/classes")
    assert response.status_code == 500
    assert "secret" not in response.text


def test_get_db_closes_connection(monkeypatch):
    from API_uni import get_db
    db = FakeDatabase()
    monkeypatch.setattr(mysql.connector, "connect", lambda **kwargs: db)
    connection = get_db()
    assert next(connection) is db
    connection.close()
    assert db.closed


def test_connection_error_is_503(client, monkeypatch):
    def unavailable(**kwargs):
        raise mysql.connector.Error("private credentials")
    monkeypatch.setattr(mysql.connector, "connect", unavailable)
    response = client.get("/classes")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_openapi_has_response_models(client):
    schema = client.get("/openapi.json").json()
    assert "409" in schema["paths"]["/students"]["post"]["responses"]
    assert "201" in schema["paths"]["/enrollments"]["post"]["responses"]
    assert "schema" in schema["paths"]["/analytics/overview"]["get"]["responses"]["200"]["content"]["application/json"]
    assert "/fetch_table/" not in schema["paths"]
