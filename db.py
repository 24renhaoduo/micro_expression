"""SQLite 数据层（教程第十六节）。

为什么不用 Flask-SQLAlchemy：
    教程第十六节示例用 SQLAlchemy ORM。这里改用标准库 sqlite3 + 显式建表语句，
    三个理由：
    1. 少一层魔法，schema 就是这段 SQL，答辩被问"数据库长什么样"能直接指给他看；
    2. Flask test_client、脚本、后台任务都能共用同一个 init_db()，不依赖 app context；
    3. requirements 里的 Flask-SQLAlchemy 仍然装着，将来要迁 ORM 不用改依赖。

⚠️ 表名是 `cases` 不是 `case`：CASE 是 SQL 保留字，
   `CREATE TABLE case (...)` 会直接抛 sqlite3.OperationalError（本项目实测踩过）。

数据库只存**路径与结果**，视频本体留在 uploads/（教程第十六节：视频本体不入库）。
所有写入带时间戳，供第十九节报告的"分析时间"与审计需求（计划书 3.3.7）。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_no     TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    remark      TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS video (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     INTEGER NOT NULL REFERENCES cases(id),
    filename    TEXT NOT NULL,
    path        TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    duration    REAL NOT NULL DEFAULT 0,
    fps         REAL NOT NULL DEFAULT 0,
    width       INTEGER NOT NULL DEFAULT 0,
    height      INTEGER NOT NULL DEFAULT 0,
    frame_count INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_video_case ON video(case_id);

CREATE TABLE IF NOT EXISTS question_anchor (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     INTEGER NOT NULL REFERENCES cases(id),
    anchor_no   TEXT NOT NULL,
    question    TEXT,
    start_frame INTEGER NOT NULL,
    end_frame   INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_anchor_case ON question_anchor(case_id);

CREATE TABLE IF NOT EXISTS analysis (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id        INTEGER NOT NULL REFERENCES video(id),
    params_json     TEXT NOT NULL,
    result_json     TEXT NOT NULL,
    window_count    INTEGER NOT NULL DEFAULT 0,
    max_risk        REAL NOT NULL DEFAULT 0,
    green_count     INTEGER NOT NULL DEFAULT 0,
    yellow_count    INTEGER NOT NULL DEFAULT 0,
    red_count       INTEGER NOT NULL DEFAULT 0,
    grey_count      INTEGER NOT NULL DEFAULT 0,
    fps_assumed     INTEGER NOT NULL DEFAULT 0,
    elapsed_seconds REAL NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analysis_video ON analysis(video_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    config.ensure_directories()
    connection = sqlite3.connect(str(config.DATABASE_PATH))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> Path:
    """建库建表，幂等。返回数据库文件路径。"""
    with connect() as connection:
        connection.executescript(SCHEMA)
    return config.DATABASE_PATH


def _case_exists(connection: sqlite3.Connection, case_id: int) -> bool:
    return connection.execute("SELECT 1 FROM cases WHERE id = ?", (case_id,)).fetchone() is not None


def create_case(case_no: str, name: str, remark: str = "") -> int:
    case_no = (case_no or "").strip()
    name = (name or "").strip()
    if not case_no or not name:
        raise ValueError("case_no 与 name 都不能为空")
    with connect() as connection:
        try:
            cursor = connection.execute(
                "INSERT INTO cases (case_no, name, remark, created_at) VALUES (?, ?, ?, ?)",
                (case_no, name, remark, _now()))
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"案号已存在：{case_no}") from exc
        return int(cursor.lastrowid)


def list_cases() -> List[Dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT c.*, COUNT(v.id) AS video_count
               FROM cases c LEFT JOIN video v ON v.case_id = c.id
               GROUP BY c.id ORDER BY c.id DESC""").fetchall()
    return [dict(row) for row in rows]


def register_video(case_id: int, filename: str, path: Path, info: Dict[str, Any],
                   sha256: str) -> int:
    """把已上传的视频登记进案件。视频本体不入库，只存路径与参数。"""
    with connect() as connection:
        if not _case_exists(connection, case_id):
            raise ValueError(f"案件不存在：{case_id}")
        cursor = connection.execute(
            """INSERT INTO video (case_id, filename, path, sha256, duration, fps, width,
                                  height, frame_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (case_id, filename, str(path), sha256, float(info.get("duration", 0)),
             float(info.get("fps", 0)), int(info.get("width", 0)),
             int(info.get("height", 0)), int(info.get("frame_count", 0)), _now()))
        return int(cursor.lastrowid)


def add_anchor(case_id: int, anchor_no: str, question: str,
               start_frame: int, end_frame: int) -> int:
    if end_frame <= start_frame:
        raise ValueError("end_frame 必须晚于 start_frame")
    if start_frame < 0:
        raise ValueError("start_frame 不能为负")
    with connect() as connection:
        if not _case_exists(connection, case_id):
            raise ValueError(f"案件不存在：{case_id}")
        cursor = connection.execute(
            """INSERT INTO question_anchor (case_id, anchor_no, question, start_frame,
                                            end_frame, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (case_id, anchor_no, question, int(start_frame), int(end_frame), _now()))
        return int(cursor.lastrowid)


def anchors_for_case(case_id: int) -> List[Dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM question_anchor WHERE case_id = ? ORDER BY start_frame",
            (case_id,)).fetchall()
    return [dict(row) for row in rows]


def save_analysis(video_id: int, result: Dict[str, Any], params: Dict[str, Any],
                  elapsed_seconds: float = 0.0, fps_assumed: bool = False) -> int:
    """落一份分析结果。汇总计数在写库时算好，结果页不必再解析 JSON。"""
    summary = result.get("summary", {})
    counts = summary.get("risk_level_counts", {})
    with connect() as connection:
        if connection.execute("SELECT 1 FROM video WHERE id = ?", (video_id,)).fetchone() is None:
            raise ValueError(f"视频记录不存在：{video_id}")
        cursor = connection.execute(
            """INSERT INTO analysis (video_id, params_json, result_json, window_count,
                                     max_risk, green_count, yellow_count, red_count,
                                     grey_count, fps_assumed, elapsed_seconds, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (video_id, json.dumps(params, ensure_ascii=False),
             json.dumps(result, ensure_ascii=False),
             int(summary.get("window_count", 0)), float(summary.get("max_risk", 0)),
             int(counts.get("green", 0)), int(counts.get("yellow", 0)),
             int(counts.get("red", 0)), int(counts.get("grey", 0)),
             1 if fps_assumed else 0, round(float(elapsed_seconds), 3), _now()))
        return int(cursor.lastrowid)


def get_analysis(analysis_id: int) -> Optional[Dict[str, Any]]:
    with connect() as connection:
        row = connection.execute(
            """SELECT a.*, v.filename, v.path, v.sha256, v.case_id, v.duration, v.fps,
                      v.width, v.height, v.frame_count, c.case_no, c.name AS case_name
               FROM analysis a JOIN video v ON v.id = a.video_id
               JOIN cases c ON c.id = v.case_id WHERE a.id = ?""",
            (analysis_id,)).fetchone()
    if row is None:
        return None
    record = dict(row)
    record["result"] = json.loads(record.pop("result_json"))
    record["params"] = json.loads(record.pop("params_json"))
    return record


def recent_analyses(limit: int = 20) -> List[Dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT a.id, a.created_at, a.window_count, a.max_risk, a.red_count,
                      a.yellow_count, a.green_count, a.grey_count, a.fps_assumed,
                      v.filename, v.case_id, c.case_no
               FROM analysis a JOIN video v ON v.id = a.video_id
               JOIN cases c ON c.id = v.case_id
               ORDER BY a.id DESC LIMIT ?""", (int(limit),)).fetchall()
    return [dict(row) for row in rows]
