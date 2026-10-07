# Project memory

微察——AI 微表情智能审讯辅助系统。确认过的长期事实与决定，不是对话日志。
最后核对：2026-10-03。

## 项目定位

- 竞赛项目：中国国际大学生创新大赛（2026）河南赛区选拔赛，高教主赛道·本科生组·创意组，类别"人工智能+"。计划书见 `outputs/微察——AI微表情智能审讯辅助系统.pdf`。
- 技术栈固定：Flask + OpenCV + MediaPipe + SQLite + ECharts，本地离线部署。
- 实现节奏按 `outputs/微察_AI微表情智能审讯辅助系统_保姆级技术路线与Demo实现教程.docx` 的章节推进，进度表在 `README.md` 第三节。
- 合规红线：输出只能是"辅助研判参考"，禁止"说谎/不可信/危险性/抗拒"这类定性表述（措辞细则见 `services/emotion_analyzer.py` 顶部）。

## 已确认的决定（不要再重复问）

- 测试素材用 `test_data/Lab-SMEM`，**志愿者**自发微表情数据，非真实嫌疑人。允许在系统内展示原始帧（`config.EXPOSE_KEYFRAMES`）；对外发布前需另行确认数据集再分发协议。
- 数据集**留在 `test_data/` 原地不动**，不搬项目外。
- 情绪标签体系**先走方案 A**（显著面部动作检测），不直接做四类分类。
- 数据集未给帧率，**按 25 fps 假设**，所有秒级数值必须带"假设值"标记（`config.DATASET_FPS_ASSUMED`）。
- `.gitignore` 已加 `test_data/` 整目录忽略，防止 6.9 GB 真人脸图进仓库。

## 环境的三条硬事实（踩过的坑，别重新推导）

1. **`.venv` 不可跨目录拷贝**。它记录创建时的绝对路径，换目录就报 `No Python at '...'`。重建：`python\python.exe -m venv .venv --clear`（base 是项目内便携 Python 3.11.7）。
2. **MediaPipe 在 Windows 上不吃非 ASCII 路径**。`FaceMesh()` 初始化会报 `FileNotFoundError: ...face_landmark_front_cpu.binarypb`，而该文件其实存在。`check_env.py` 只 import 不建图，**测不出这个问题**。完整证据链见 `docs/环境路径问题排查记录.md`。解法：项目搬到纯英文路径，或每次 `subst X:` 后用盘符运行。
3. **`cv2.imread` 遇到中文路径静默返回 `None`**，会被下游误读成"这帧没有人脸"。已用 `services/image_io.py`（pathlib 读字节 + `cv2.imdecode`）绕开；实测同一文件 imread→None、read_image→正常解出 1920×1080。

补充：`requirements.txt` 只声明 `opencv-contrib-python`，绝不能同时加 `opencv-python`（两者共用 `cv2` 目录，实际版本随安装顺序漂移）。

## 代码事实

- Face Mesh 开 `refine_landmarks=True` → 实际 **478 点**（468 网格 + 10 虹膜），教程正文写 468。下游不要硬编码点数。
- 抽帧/单张图片**必须** `FaceAnalyzer.for_stills()`（`static_image_mode=True`）；视频逐帧连续采样才用默认跟踪模式。实测同一批离散帧：跟踪模式 11/14，图片模式 14/14。
- 全链路目前**没有任何大模型**：只有 MediaPipe 的本地 `.tflite` 小模型 + 手写 if/else 阈值规则。venv 里没装 torch/transformers/onnxruntime。
- 前端"AI 追问"输入框是**纯占位**（`static/js/main.js:681`），不发请求。演示前要接或标注"待接入"。

## Lab-SMEM 数据集实测事实

31 个被试目录 / 226 个片段 / 22,232 张 1920×1080 jpg / 6.9 GB。文件名统一 `%d.jpg`，**帧号是原视频绝对帧号**，且只保留 onset→offset 段（**没有 onset 之前的中性基线帧**）。标注与磁盘 226:226 一一对应，0 段区间内缺帧。

已知数据异常（`services/dataset_loader.py` 的 audit 会显式列出，不静默修）：
- `09/C0023_7` 标注 offset=276，磁盘只到 275
- 5 段 AU 为空（均属 28 号被试 C0101_*）
- 2 段 AU 写作 `u2`/`u17`（未确认标记）

情绪分布：negative 85 / positive 68 / surprise 44 / others 29。

## 评测结论（2026-10-02，全量 226 段，`static_image_mode=True`）

**这两条结论决定了产品话术，答辩材料必须与之一致：**

1. **峰值定位能力不优于随机。** 累积幅度口径 hit@±5 = 15.0%、逐帧速度口径 = 18.6%，随机基线 17.4%；累积幅度存在 **+17 帧系统性偏晚**（176/226 段），根因是**没做人脸配准去漂移**。
2. **位移幅度分不出情绪类别。** one-vs-rest AUC 仅 0.427–0.619（0.5 为无信息）；准确率 29.6% vs 瞎猜 28.6%；**UF1 = 0.251 / UAR = 30.1%**（随机 25%）；negative 召回只有 7%（85 段判对 6 段）。
   → 结果页不得以"情绪识别"名义展示中性/紧张/恐惧标签；计划书"十二种情绪 + 三类心理状态"与 UF1≥0.80 目标需要降级表述或改技术路线。

阈值标定实测：事件幅度 p10=0.00193 / p50=0.00454 / p90=0.01515，教程的 0.003/0.012/0.030 约当 p30/p88/超上界 → **约九成真实微表情事件会被判成"中性/轻度"**。报告里应同时给教程阈值与分位标定值。

结果文件：`outputs/analysis/apex_localization.json`、`outputs/analysis/emotion_discriminability.json`。
复现：`python tests\apex_localization_test.py --all`（约 9 分钟）→ `python tests\emotion_discriminability.py`（秒级）。

## 与教程的三处已声明偏差（写在模块 docstring 里，不做暗改）

`services/emotion_analyzer.py`：① 尖峰判定提到中性之前（原顺序会吃掉短时尖峰，而微表情本就是尖峰）；② 情绪区域改为按关键点分组**算出来**而非硬贴；③ "数据不足"窗口单独归 `grey / 无有效数据`，不再显示绿色。`calculate_risk` 公式本身未改。

## 配准与模型基线实测（2026-10-02 补）

**配准对照（n=100 分层）**：五种口径两条判据均 FAIL——最好 hit@±5 = 24.0%（阈值 30%，随机 19.8%）、最优 AUC = 0.675（阈值 0.70）。但配准确实有效：hit@±2 从 7–8% 提到 14–15%，误差中位 16→13 帧，偏晚从 +14 帧降到 +8 帧。`services/face_align.py` **必须保留**，它是任何模型的特征前置。

**模型基线（LOSO 31 折 / 226 段 / 23 维）**：瞎猜 28.6% | LR 仅幅度 24.8%（UF1 0.218，低于瞎猜）| LR 全 23 维 33.2%（UF1 0.323 / UAR 36.0%）| RF 全 23 维 38.5%（UF1 0.307，靠压少数类抬准确率）。
→ **配准后的“动在哪 + 怎么动”有信息，“动了多少”没有**（消融测出来的，本轮唯一正向结论）。但距 UF1≥0.80 仍差 2.5 倍，瓶颈是表征与数据量，不是调参。

## 2026-10-03：SQLite 与结果页已打通

新增 `db.py`（cases / video / question_anchor / analysis 四表）、`app.py` 六个 API +
`/result/<id>` 结果页、`templates/result.html`+`error.html`、`static/css/result.css`、
`tests/database_flow_test.py`（**35 条用例，exit 0**）。
`instance/micro_observe.db` 里已有 2 条演示案件，可直接看 `/result/2`。

本轮踩到并记下的三条：

1. **`case` 是 SQL 保留字**，`CREATE TABLE case (...)` 直接抛 OperationalError → 表名用 `cases`。
2. **重合度一律按帧号算**：`analysis_service` 的 `overlap_provider` 入参已从秒改为帧。
   锦定存的是帧号，而帧率是假设值；用秒对帧号不会报错，只会把 0 算成 1.0。
3. **上传视频的 fps 是 OpenCV 实测值**，落库时 `fps_assumed=0`；只有只有帧号的素材才标假设。

诚实缺口：**首页“上传并开始解析”按钮目前仍只上传**，不建案也不触发分析
（`static/js/main.js` 未改）。完整链路现在靠 API 串，`tests/database_flow_test.py` 就是这条链。

## 数据集申请：只能用户本人发，草稿已就绪

`docs/数据集申请草稿.md`（中/英三封 + 发送前检查清单）。两个坑写在那里：
① CASME 的主办方是**台湾台中的 China Medical University（cmu.edu.tw）**，
与沈阳的中国医科大学（cmu.edu.cn）同名不同校，发错不会有任何回复；
② 搜索引擎没找到官方申请页，**邮箱必须取自原论文通讯作者**，不得凭记忆填。

## 照片表情判断（2026-10-07 新增能力）

用户真实需求是“照片上传→情绪判断”（不是视频时间轴）。已做 `services/photo_emotion.py`
+ `/photo` 页面 + `POST /api/photo/emotion`，接口测试 `tests/photo_api_test.py`（24 条）全绿。

实测口径（`tests/photo_emotion_eval.py`，226 对 onset/apex）：
- **单帧分类只有弱信号**：留一被试准确率 42.0% / UAR 42.0%（四类瞎猜 25.0%，最大类 37.6%）；
  愉快类召回仅 14.7%，惊讶 63.6%，紧张/厌恶 55.3%。→ **只一张照片时只输出读数，不输出类别**。
- **相对变化可用**：以本人平靖帧为基准，方向正确率 愉快 79.4%（n=68）、惊讶 81.8%（n=44）、
  紧张/厌恶 64.3%（n=84）、张口 56.8%（仅辅助）。页面直接把这几个百分比印出来。
- 第一版（用旧索引/旧量纲）实测 19.0%、低于瞎猜，已废弃；标定的解剖 y 坐标序列写在模块 docstring。
- 现场可用演示对（均已实测输出正确类别）：`09/C0023_3`→惊讶、`02/C0006_4`→惊讶、
  `25/C0094_11`→紧张/厌恶；不稳对：`01/C0003_6`（positive 被判惊讶）、`16/C0038_5`（无变化）。

## 下一步（按优先级）

1. ✅ 人脸配准与模型基线已完成（结果见上两节）。规则路线按预登记条件终止。
2. ✅ 第十六节 SQLite + 第十八节结果页已完成（35 条用例全绿）。
3. **首页接线**：把上传按钮接成 建案→登记→分析→跳 /result，这是演示能否跑起来的最后一环。
3. 第十九节报告：建议先做**模板化中文措辞**（零合规风险）。接云端大模型会直接违反计划书 3.3.7 “原始音视频不出单位”。
4. 项目搬到纯英文路径 + `git init`（截至 2026-10-02 仍未做，.gitignore 已安全）。
5. `check_env.py` 补三行真正构建 FaceMesh 的探测（用户尚未同意改该脚本）。
6. ✅ CASME II / SMIC / SAMM 申请信草稿已写（`docs/数据集申请草稿.md`），
   **发送动作只能用户本人做**——这仍是唯一“今天不发就无法补救”的长周期项，
   也是把 UF1 从 0.32 抬上去的现实路径（需要 600–1000 段）。
