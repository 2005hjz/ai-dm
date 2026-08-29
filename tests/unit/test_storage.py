"""SQLite 遥测存储的单元测试。"""

from __future__ import annotations

from app.storage import TelemetryStore


def test_log_and_query_checks(tmp_path):
    store = TelemetryStore(tmp_path / "t.db")
    store.log_check(
        session_id="s1", turn=1, scene_id="prologue", skill="侦查",
        dc=8, total=12, success=True, degree="成功", expression="1d20",
        meta={"note": "test"},
    )
    store.log_check(
        session_id="s1", turn=2, scene_id="hallway", skill="推理",
        dc=10, total=5, success=False, degree="失败", expression="1d20",
    )
    rows = store.query_checks("s1")
    assert len(rows) == 2
    assert rows[0]["skill"] == "推理"
    assert rows[0]["success"] == 0
    assert rows[1]["success"] == 1
    store.close()


def test_upsert_metrics(tmp_path):
    store = TelemetryStore(tmp_path / "t.db")
    store.upsert_metrics("s1", {"player": "阿梅", "checks": 2, "passed": 1, "failed": 1, "rolls": 3})
    store.upsert_metrics("s1", {"player": "阿梅", "checks": 3, "passed": 1, "failed": 2, "rolls": 4})
    row = store.conn.execute("SELECT checks, passed, failed, rolls FROM session_metrics WHERE session_id='s1'").fetchone()
    assert row == (3, 1, 2, 4)
    store.close()
