# University Information API

A small FastAPI and MySQL project for managing students and class enrollments. It also provides SQL-based enrollment statistics.

I first developed the university API in 2024. I revisited it in November 2026 to improve the data model, finish the enrollment workflow, and add tests and Docker support.

## Run with Docker

With Docker Desktop running:

```sh
docker compose up --build -d
```

Open http://localhost:8000/docs to try the API. MySQL is initialized automatically from `uni.sql` on the first run. The API uses port `8000` and the demo MySQL server uses local port `3307`.

Stop with `docker compose down`. To start over with the original sample data, run `docker compose down -v` first. **This deletes the demo database volume.** Credentials in `compose.yaml` are for local testing only.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/students` | List students |
| POST | `/students` | Create a student |
| GET | `/students/{student_id}` | Get one student |
| GET | `/students/{student_id}/classes` | List a student's classes |
| GET | `/classes` | List classes and professors |
| POST | `/enrollments` | Enroll a student in a class |
| GET | `/analytics/overview` | Enrollment statistics |

Example requests:

```http
POST /students HTTP/1.1
Content-Type: application/json

{"name": "Alex Meyer", "phone": "+12025550188"}
```

```http
POST /enrollments HTTP/1.1
Content-Type: application/json

{"student_id": 14, "class_id": 6}
```

Phones use international format. Duplicate phone numbers or enrollments return `409`; an enrollment with an unknown student or class returns `404`.

## Data and analytics

`uni.sql` creates four related tables: `STDinfo`, `PROFinfo`, `CLASSinfo`, and `ENROLLinfo`. It uses foreign keys and unique constraints to protect the relationships.

On a fresh database, the fictional sample data has 20 students, 4 professors, 6 classes, and 18 enrollments. The analytics endpoint uses `NOT EXISTS` to count students without enrollments and `LEFT JOIN` / `GROUP BY` to include classes with zero enrollments.

## Tests

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

For the MySQL integration test, start Docker Compose and enable the test. On Windows CMD:

```cmd
set RUN_MYSQL_TESTS=1
python -m pytest -q
```

On Linux/macOS, run `RUN_MYSQL_TESTS=1 python -m pytest -q`. The integration test creates temporary records, checks changes relative to the existing data, and removes its records afterward. GitHub Actions runs the same suite with a fresh MySQL container.

## Run without Docker

Use a separate MySQL 8 database, import `uni.sql` into it, and set `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME`. The SQL file drops and recreates the demo tables, so don't import it into a database you need to keep. Then run:

```sh
python -m pip install -r requirements.txt
python -m uvicorn API_uni:app --reload
```

## Project history

The 2024 version supported student insertion, table browsing, student listing, and class lookup. The 2026 update introduced REST-style routes, enrollment creation, schema constraints, cleaner sample data, SQL analytics, tests, and Docker. The original commits remain in the [project repository](https://github.com/iamkianasedighi/APIuniByKianaSedighi).
