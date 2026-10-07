"""微察 Flask 入口。

已接通的能力（教程章节对应）：
    第十节   首页
    第十一节 视频参数 + SHA-256（services/video_utils.py）
    第十五节 上传闭环 + /uploads 回取
    第十六节 SQLite 案件/视频/锚定/分析落库（db.py）
    第十七节 问题锚定（services/question_anchor.py）
    第十八节 结果页 /result/<analysis_id>

单位纪律：锚定与窗口一律以**帧号**对齐；秒只在 fps 已知时才用于展示，
且必须带"帧率假设"标记（config.FPS_ASSUMED_NOTE）。用秒对帧号算重合度不会报错，
只会把 0 算成 1.0——这是本项目已验证过的陷阱。
"""

import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

import config
import db
from services import analysis_service
from services.question_anchor import Anchor, calculate_overlap
from services.video_utils import calculate_sha256, get_video_info

# 路径单一来源改为 config，避免 app.py 与 config.py 两套定义各自漂移
UPLOAD_DIR = config.UPLOAD_DIR
OUTPUT_DIR = config.OUTPUT_DIR
INSTANCE_DIR = config.INSTANCE_DIR
config.ensure_directories()

ALLOWED_EXTENSIONS = {"mp4", "avi", "mov", "mkv"}

app = Flask(__name__, instance_relative_config=True)
app.config.from_mapping(
    SECRET_KEY="dev-only-change-me",
    MAX_CONTENT_LENGTH=500 * 1024 * 1024,
    UPLOAD_FOLDER=str(UPLOAD_DIR),
)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _video_row(video_id: int):
    with db.connect() as connection:
        row = connection.execute(
            "SELECT id, case_id, filename, path, sha256, duration, fps, width, height, "
            "frame_count FROM video WHERE id = ?", (video_id,)).fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------------------- 页面

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/result/<int:analysis_id>")
def result_page(analysis_id):
    """教程第十八节结果页：把窗口逐条摆出来，点击行让视频跳到对应位置。"""
    record = db.get_analysis(analysis_id)
    if record is None:
        return render_template("error.html", message=f"分析记录不存在：{analysis_id}"), 404

    windows = record["result"].get("windows", [])
    anchors = db.anchors_for_case(record["case_id"])
    for window in windows:
        window["anchor_hits"] = [
            anchor for anchor in anchors
            if calculate_overlap(window["start_frame"], window["end_frame"],
                                 anchor["start_frame"], anchor["end_frame"]) > 0]
    return render_template("result.html", record=record, windows=windows, anchors=anchors,
                           fps_note=config.FPS_ASSUMED_NOTE if record["fps_assumed"] else "")


@app.get("/uploads/<path:filename>")
def serve_upload(filename):
    """教程第十五节要求的视频回取路由，结果页播放依赖它。"""
    return send_from_directory(str(UPLOAD_DIR), filename)


# ------------------------------------------------------------------- 第十一/十五节

@app.post("/api/uploads")
def upload_video():
    file = request.files.get("video")
    if not file or not file.filename:
        return jsonify({"error": "请选择视频文件"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "只支持 MP4、AVI、MOV、MKV 文件"}), 400

    original_name = file.filename
    suffix = Path(original_name).suffix.lower()
    # secure_filename 会剔除全部非 ASCII 字符，纯中文文件名会得到空串；
    # 同时同名文件会互相覆盖。因此用“安全名 + UUID 短码 + 原始后缀”落盘，
    # 原始文件名只用于回显，不作为磁盘路径。
    safe_stem = secure_filename(Path(original_name).stem) or "video"
    filename = f"{safe_stem}_{uuid.uuid4().hex[:8]}{suffix}"
    save_path = UPLOAD_DIR / filename
    file.save(save_path)

    try:
        info = get_video_info(save_path)
        sha256 = calculate_sha256(save_path)
    except Exception as exc:
        # 教程第二十二节：视频读不出来要明说原因，不能假装上传成功
        return jsonify({"error": f"视频读取失败：{exc}", "filename": filename}), 400

    if not info["can_decode"]:
        return jsonify({
            "error": "文件头可解析但解不出任何一帧，请先用 FFmpeg 转成 H.264 MP4 后重试。",
            "filename": filename,
            "info": info,
        }), 400

    summary = (f"上传成功并读到视频：{info['duration']} 秒 · "
               f"{info['width']}×{info['height']} · {info['fps']} fps · "
               f"共 {info['frame_count']} 帧")
    return jsonify({
        "filename": filename,
        "original_name": original_name,
        "message": summary,
        "info": info,
        "sha256": sha256,
        "note": "下一步：POST /api/cases/<case_id>/videos 登记进案件，"
                "再 POST /api/videos/<video_id>/analyze 出结果页。",
    })


# --------------------------------------------------------------- 第十六/十七节

@app.post("/api/cases")
def create_case():
    payload = request.get_json(silent=True) or {}
    try:
        case_id = db.create_case(str(payload.get("case_no", "")),
                                 str(payload.get("name", "")),
                                 str(payload.get("remark", "")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"case_id": case_id, "message": f"案件已创建（id={case_id}）"}), 201


@app.get("/api/cases")
def list_cases():
    return jsonify({"cases": db.list_cases()})


@app.post("/api/cases/<int:case_id>/videos")
def attach_video(case_id):
    """把已上传的文件登记到案件下。参数从磁盘重算，不信客户端回传。"""
    payload = request.get_json(silent=True) or {}
    filename = str(payload.get("filename", ""))
    save_path = UPLOAD_DIR / Path(filename).name
    if not filename or not save_path.is_file():
        return jsonify({"error": f"文件不在 uploads/ 里：{filename}"}), 404
    try:
        info = get_video_info(save_path)
        sha256 = calculate_sha256(save_path)
        video_id = db.register_video(case_id, filename, save_path, info, sha256)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"video_id": video_id, "info": info, "sha256": sha256}), 201


@app.post("/api/cases/<int:case_id>/anchors")
def add_case_anchor(case_id):
    """录入问题锚定。存的是帧号；start/end 必须来自同一条时间轴口径。"""
    payload = request.get_json(silent=True) or {}
    anchor_no = str(payload.get("anchor_no") or "").strip() or f"Q{int(time.time()) % 10000}"
    try:
        anchor = Anchor(anchor_id=anchor_no,
                        start=float(payload.get("start_frame")),
                        end=float(payload.get("end_frame")),
                        text=str(payload.get("question", "")))
        anchor_id = db.add_anchor(case_id, anchor.anchor_id, anchor.text,
                                  int(anchor.start), int(anchor.end))
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"锚定录入失败：{exc}"}), 400
    return jsonify({"anchor_id": anchor_id, "anchor_no": anchor.anchor_id}), 201


# --------------------------------------------------------------------- 分析落库

@app.post("/api/videos/<int:video_id>/analyze")
def analyze_saved_video(video_id):
    """对已登记的视频跑完整链路并落库，返回结果页地址。"""
    record = _video_row(video_id)
    if record is None:
        return jsonify({"error": f"视频记录不存在：{video_id}"}), 404
    path = Path(record["path"])
    if not path.is_file():
        return jsonify({"error": f"视频文件已不在磁盘：{path}"}), 410

    anchors = [Anchor(a["anchor_no"], a["start_frame"], a["end_frame"], a["question"])
               for a in db.anchors_for_case(record["case_id"])]

    def overlap_provider(start_frame, end_frame):
        return max((calculate_overlap(start_frame, end_frame, a.start, a.end) for a in anchors),
                   default=0.0)

    payload = request.get_json(silent=True) or {}
    options = {}
    for key in ("sample_interval", "window_seconds", "step_seconds", "max_samples"):
        if key in payload:
            options[key] = payload[key]

    started = time.time()
    try:
        result = analysis_service.analyze_video(
            path, overlap_provider=overlap_provider if anchors else None, **options)
    except ValueError as exc:
        return jsonify({"error": f"分析失败：{exc}"}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"分析中断：{type(exc).__name__}: {exc}"}), 500

    elapsed = time.time() - started
    # 上传视频的 fps 是 OpenCV 实测得到的，不是假设值；
    # 只有 Lab-SMEM 那类只有帧号、没有帧率的素材才需要标 assumed。
    analysis_id = db.save_analysis(video_id, result, options, elapsed, fps_assumed=False)
    return jsonify({"analysis_id": analysis_id, "elapsed_seconds": round(elapsed, 2),
                    "summary": result["summary"], "result_url": f"/result/{analysis_id}"})


@app.get("/api/analysis/<int:analysis_id>")
def get_analysis_json(analysis_id):
    record = db.get_analysis(analysis_id)
    if record is None:
        return jsonify({"error": f"分析记录不存在：{analysis_id}"}), 404
    return jsonify(record)


# --------------------------------------------------------------- 照片表情判断

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "bmp", "webp"}


@app.get("/photo")
def photo_page():
    return render_template("photo.html")


@app.post("/api/photo/emotion")
def photo_emotion_api():
    """照片表情判断。

    只给 target → 输出构型读数（单帧分类实测 ≈ 随机，不给类别）。
    同时给 base → 输出 onset→apex 同口径的**相对变化判据**（实测方向正确率 78.8%/81.4%/62.8%）。
    """
    from services import photo_emotion
    from services.face_analyzer import FaceAnalyzer
    from services.image_io import decode_bytes

    target_file = request.files.get("target")
    base_file = request.files.get("base")
    if not target_file or not target_file.filename:
        return jsonify({"error": "请选择要判断的照片"}), 400
    suffix = Path(target_file.filename).suffix.lower().lstrip(".")
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": f"不支持的图片格式 .{suffix}，请用 JPG/PNG/BMP/WEBP"}), 400

    try:
        target_image = decode_bytes(target_file.read())
        base_image = decode_bytes(base_file.read()) if base_file and base_file.filename else None
    except Exception as exc:
        return jsonify({"error": f"图片读取失败：{exc}"}), 400

    # static_image_mode=True：照片不是连续帧，用跟踪模式会漏检（已实测 11/14 vs 14/14）
    analyzer = FaceAnalyzer.for_stills()
    try:
        target_points = analyzer.detect(target_image)
        base_points = analyzer.detect(base_image) if base_image is not None else None
    finally:
        analyzer.close()

    result = photo_emotion.judge_photo(target_points, base_points)
    result["overlay"] = "" if target_points is None else photo_emotion.render_overlay(
        target_image, target_points)
    result["detected"] = target_points is not None
    result["has_base"] = base_points is not None
    result["landmarks"] = 0 if target_points is None else len(target_points)
    return jsonify(result)


@app.errorhandler(413)
def request_entity_too_large(_error):
    return jsonify({"error": "文件大小不能超过 500 MB"}), 413


if __name__ == "__main__":
    db.init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
