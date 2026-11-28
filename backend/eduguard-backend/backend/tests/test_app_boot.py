from fastapi.testclient import TestClient


def test_app_boots_on_sqlite_and_lists_plans():
    import main
    with TestClient(main.app) as client:
        assert client.get("/api/health").status_code == 200
        r = client.get("/api/v1/edu/plans")
        assert r.status_code == 200 and r.json()["enforced"] is False
        assert set(r.json()["plans"]) == {"pho_thong", "tra_phi"}
        me = client.get("/api/v1/edu/me/plan").json()
        assert me["planId"] == "pho_thong" and me["userId"] is None
        st = client.get("/api/v1/edu/llm/status").json()
        assert "anthropic" in st["providers"] and "quiz" in st["routes"]
        assert client.get("/api/v1/edu/templates").json()["data"]


def test_tables_created_including_usage_counters():
    import main  # noqa: F401
    from sqlalchemy import inspect
    from app.core.database import engine
    with TestClient(main.app):
        names = set(inspect(engine).get_table_names())
    assert {"users", "presentations", "edu_usage_counters"} <= names
    cols = {c["name"] for c in inspect(engine).get_columns("users")}
    assert "role" in cols
