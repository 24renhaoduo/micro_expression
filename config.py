"""项目级配置（教程第九节目录树中的 config.py）。

只放"会随部署环境变化"的量，不放业务阈值——情绪与风险阈值属于
services/emotion_analyzer.py 的规则本体，改那里才是改算法。

设计约束：
    路径一律基于 Path(__file__).resolve().parent，不依赖当前工作目录
    （教程评价.docx 第三节第 2 条：相对路径从不同目录启动会写飞到别处）。
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# ---- 运行时目录 ----
UPLOAD_DIR = PROJECT_ROOT / "uploads"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
INSTANCE_DIR = PROJECT_ROOT / "instance"
#: SQLite 库文件。只存路径、参数与结果，视频本体留在 uploads/。
DATABASE_PATH = INSTANCE_DIR / "micro_observe.db"
TEST_DATA_DIR = PROJECT_ROOT / "test_data"
ANALYSIS_OUTPUT_DIR = OUTPUT_DIR / "analysis"

# ---- 数据集 ----
# 用户决定：Lab-SMEM 留在 test_data/ 原地不动（约 6.9 GB、22,232 张 1920×1080 jpg）。
# .gitignore 已忽略整个 test_data/，因此它不会进仓库，但会随目录一起被备份。
DATASET_ROOT = TEST_DATA_DIR / "Lab-SMEM" / "Lab-SMEM"
ANNOTATION_FILE = DATASET_ROOT / "Annotation.xlsx"

#: 数据集标注只给了帧号，没给帧率。用户选择按 25 fps 假设。
DATASET_FPS = 25.0

#: 该帧率是假设值还是实测值。所有导出物（结果页、报告、评测表）都必须带上这个标记。
DATASET_FPS_ASSUMED = True

FPS_ASSUMED_NOTE = "帧率按 25 fps 假设（数据集未提供），所有秒级数值均为推算值"

# ---- 采样口径 ----
#: 连续视频（审讯场景长片段）用 6 帧间隔降算力，教程第十三节建议值
VIDEO_SAMPLE_INTERVAL = 6
#: 数据集片段只有 19—671 帧，必须逐帧，否则 onset→apex 事件只有两三个采样点
DATASET_SAMPLE_INTERVAL = 1

# ---- 展示与合规 ----
#: 是否允许在结果页与报告中展示原始人脸帧。
#: 用户已确认素材为志愿者采集并允许展示，因此默认开启；
#: 但对外发布（比赛材料、公开演示、任何出单位的东西）前，
#: 请另行确认 Lab-SMEM 的使用协议是否允许再展示/再分发原始帧。
EXPOSE_KEYFRAMES = True

#: 单轮评测最多处理多少个片段，用于抽样快速回归
DEFAULT_MAX_CLIPS = 25


def dataset_seconds(frames: float, fps: float | None = None) -> float:
    """把帧数换算成秒。fps 不传时用假设帧率，调用方负责标注 assumed。"""
    effective = fps if fps else DATASET_FPS
    if effective <= 0:
        return 0.0
    return round(frames / effective, 3)


def ensure_directories() -> None:
    """创建运行时目录（含数据库所在的 instance/）。幂等。"""
    for directory in (UPLOAD_DIR, OUTPUT_DIR, INSTANCE_DIR, ANALYSIS_OUTPUT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
