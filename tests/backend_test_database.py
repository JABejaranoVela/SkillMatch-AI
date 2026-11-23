"""Verify the disposable PostgreSQL target before migrations or upload tests."""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError


def verified_test_engine() -> Engine:
    raw_url = os.environ.get("SKILLMATCH_UPLOAD_TEST_DATABASE_URL")
    if not raw_url:
        raise ValueError("Set SKILLMATCH_UPLOAD_TEST_DATABASE_URL to the disposable PostgreSQL DB")
    if os.environ.get("ENVIRONMENT") != "test" or raw_url != os.environ.get("DATABASE_URL"):
        raise ValueError("Test and application database URLs must match in ENVIRONMENT=test")
    try:
        url = make_url(raw_url)
    except (ArgumentError, ValueError):
        raise ValueError("Invalid test PostgreSQL URL") from None

    target = (url.host, url.port, url.username)
    hosted_ci = (
        os.environ.get("GITHUB_ACTIONS"),
        os.environ.get("RUNNER_ENVIRONMENT"),
        os.environ.get("GITHUB_JOB"),
    ) == ("true", "github-hosted", "backend-tests")
    allowed_target = target == ("cv-test-db", 5432, "skillmatch_test") or (
        hosted_ci and target == ("127.0.0.1", 5432, "skillmatch_test")
    )
    if (
        url.drivername != "postgresql+psycopg"
        or url.database != "skillmatch_test"
        or url.query
        or not allowed_target
    ):
        raise ValueError("PostgreSQL target does not match the isolated test environment")

    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            identity = connection.execute(text("""
                SELECT datname, pg_catalog.shobj_description(oid, 'pg_database')
                FROM pg_catalog.pg_database
                WHERE datname = pg_catalog.current_database()
            """)).one()
    except SQLAlchemyError:
        engine.dispose()
        raise ValueError("Could not verify the PostgreSQL test database") from None
    if identity != ("skillmatch_test", "skillmatch:disposable-cv-tests"):
        engine.dispose()
        raise ValueError("PostgreSQL test database is missing the disposable marker")
    return engine


if __name__ == "__main__":
    try:
        verified_test_engine().dispose()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print("Verified disposable PostgreSQL database: skillmatch_test")
