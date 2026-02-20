"""Category K: PostgreSQL-specific VACUUM/ANALYZE maintenance tests.

Verifies that database maintenance functions work correctly on PostgreSQL.
Requires: docker compose -f docker-compose.pg-test.yml up -d
"""

import pytest
from sqlalchemy import text

from intellibox.database import run_analyze, run_maintenance, run_vacuum
from intellibox.models import Base, ProgramNewsCache, ReportCache
from intellibox.utils.datetime_utils import utcnow
from tests.pg_conftest import PgSessionLocal, pg_engine

pytestmark = pytest.mark.pg


@pytest.fixture(scope="session", autouse=True)
def pg_setup():
    Base.metadata.create_all(bind=pg_engine)
    yield
    Base.metadata.drop_all(bind=pg_engine)
    pg_engine.dispose()


@pytest.fixture(autouse=True)
def pg_clean(pg_setup):
    with pg_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        conn.commit()


class TestPostgresVacuumAnalyze:
    """VACUUM and ANALYZE on PostgreSQL."""

    def test_run_vacuum_succeeds(self):
        """run_vacuum() completes without error on PostgreSQL."""
        run_vacuum(target_engine=pg_engine)

    def test_run_analyze_succeeds(self):
        """run_analyze() completes without error on PostgreSQL."""
        run_analyze(target_engine=pg_engine)

    def test_vacuum_after_deletes(self):
        """VACUUM works after deleting rows (reclaims space)."""
        session = PgSessionLocal()
        for i in range(50):
            session.add(ProgramNewsCache(
                summary=f"News {i}", days_covered=7,
                email_count=i, generated_at=utcnow(),
            ))
        session.commit()
        session.query(ProgramNewsCache).delete()
        session.commit()
        session.close()

        # VACUUM should run without error
        run_vacuum(target_engine=pg_engine)

    def test_analyze_updates_statistics(self):
        """ANALYZE updates query planner statistics without error."""
        session = PgSessionLocal()
        for i in range(20):
            session.add(ReportCache(
                report_data=f'{{"report": {i}}}',
                generated_at=utcnow(),
            ))
        session.commit()
        session.close()

        run_analyze(target_engine=pg_engine)

    def test_run_maintenance_full_cycle(self):
        """run_maintenance() completes all steps on PostgreSQL."""
        session = PgSessionLocal()
        # Seed some data to clean up
        for i in range(10):
            session.add(ProgramNewsCache(
                summary=f"News {i}", days_covered=7,
                email_count=i, generated_at=utcnow(),
            ))
            session.add(ReportCache(
                report_data=f'{{"r": {i}}}',
                generated_at=utcnow(),
            ))
        session.commit()

        result = run_maintenance(session, target_engine=pg_engine)
        session.close()

        assert "program_news_deleted" in result
        assert "report_deleted" in result
        assert "logs_deleted" in result
        assert result["analyze"] == "ok"
        assert result["vacuum"] == "ok"
