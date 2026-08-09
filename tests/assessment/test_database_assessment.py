from pathlib import Path

from universal_test.core.models.enums import AssessmentStatus
from universal_test.adapters.database.adapter import discover
from universal_test.adapters.database.profile import DatabaseProfile
from universal_test.assessment.database_assessment import assess_database_health, database_testability_signal

FIXTURES = Path(__file__).parent.parent / "fixtures" / "database"


def test_no_result_is_not_assessed():
    category = assess_database_health(None)
    assert category.status == AssessmentStatus.NOT_ASSESSED
    assert category.reason == "database credentials/access were not explicitly configured"


def test_connection_failure_is_not_assessed_never_fail(tmp_path):
    profile = DatabaseProfile(engine="sqlite", readonly=True, path=str(tmp_path / "nope.db"))
    result = discover(profile)
    category = assess_database_health(result)
    assert category.status == AssessmentStatus.NOT_ASSESSED
    assert category.status != AssessmentStatus.FAIL


def test_successful_connection_with_tables_is_pass():
    profile = DatabaseProfile(engine="sqlite", readonly=True, path=str(FIXTURES / "sqlite-relations" / "app.db"))
    result = discover(profile)
    category = assess_database_health(result)
    assert category.status == AssessmentStatus.PASS


def test_no_primary_key_is_info_not_a_downgrade():
    profile = DatabaseProfile(engine="sqlite", readonly=True, path=str(FIXTURES / "sqlite-relations" / "app.db"))
    result = discover(profile)
    category = assess_database_health(result)
    no_pk_finding = next(f for f in category.findings if f.id == "DB-NO-PK")
    assert no_pk_finding.severity.value == "info"
    assert no_pk_finding.status == AssessmentStatus.PASS  # informational, not a defect
    assert category.status == AssessmentStatus.PASS  # doesn't drag the category down


def test_zero_foreign_keys_is_info_not_a_defect(tmp_path):
    import sqlite3
    db_path = tmp_path / "no_fk.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE standalone (id INTEGER PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()

    profile = DatabaseProfile(engine="sqlite", readonly=True, path=str(db_path))
    result = discover(profile)
    category = assess_database_health(result)
    fk_finding = next(f for f in category.findings if f.id == "DB-NO-FK")
    assert fk_finding.severity.value == "info"
    assert category.status == AssessmentStatus.PASS


def test_empty_database_is_unknown(tmp_path):
    import sqlite3
    db_path = tmp_path / "empty.db"
    sqlite3.connect(db_path).close()

    profile = DatabaseProfile(engine="sqlite", readonly=True, path=str(db_path))
    result = discover(profile)
    category = assess_database_health(result)
    assert category.status == AssessmentStatus.UNKNOWN


def test_database_health_never_reaches_fail_status_value():
    # sanity check across every scenario this module produces: never FAIL
    for path in [FIXTURES / "sqlite-basic" / "app.db", FIXTURES / "sqlite-relations" / "app.db"]:
        profile = DatabaseProfile(engine="sqlite", readonly=True, path=str(path))
        category = assess_database_health(discover(profile))
        assert category.status != AssessmentStatus.FAIL


def test_testability_signal_none_when_no_evidence_and_no_result():
    assert database_testability_signal(None, database_detected_in_repo=False) == "NONE"


def test_testability_signal_not_assessed_when_evidence_but_no_result():
    assert database_testability_signal(None, database_detected_in_repo=True) == "NOT_ASSESSED"


def test_testability_signal_good_when_connected_with_tables():
    profile = DatabaseProfile(engine="sqlite", readonly=True, path=str(FIXTURES / "sqlite-basic" / "app.db"))
    result = discover(profile)
    assert database_testability_signal(result, True) == "GOOD"


def test_testability_signal_not_assessed_when_connection_failed(tmp_path):
    profile = DatabaseProfile(engine="sqlite", readonly=True, path=str(tmp_path / "nope.db"))
    result = discover(profile)
    assert database_testability_signal(result, True) == "NOT_ASSESSED"
