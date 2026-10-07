# 微察：AI 微表情智能审讯辅助系统

面向公安审讯场景的本地化微表情辅助分析 Demo（Flask + OpenCV + MediaPipe + SQLite + ECharts）。
系统输出仅为**辅助研判参考**，不构成测谎结论、司法鉴定意见或定案依据。

## 一、环境搭建（一次性的，换电脑/换目录都要重做）

> ⚠️ 虚拟环境**不可跨目录拷贝**。`.venv` 里记录了创建它的 Python 绝对路径，
> 把项目整体复制到别处后 `.venv\Scripts\python.exe` 会报
> `No Python at '...'`。遇到这种情况不要修修补补，直接按下面重建。

```bat
:: 1) 中文路径/临时目录易出问题，先按操作指南把 TMP 指到纯英文目录
set TMP=C:\tmp
set TEMP=C:\tmp

:: 2) 用项目自带的便携 Python 3.11.7 重建虚拟环境（base 在项目内，路径自洽）
python\python.exe -m venv .venv --clear

:: 3) 激活并安装依赖（需联网）
.venv\Scripts\activate
pip install -r requirements.txt

:: 4) 环境验证：必须 5 行全部正常打印，才继续往下做
python check_env.py
```

期望输出：Python 3.11.7 / Flask 3.0.3 / OpenCV 4.11.0 / MediaPipe 0.10.14 / NumPy 1.26.4。

> `requirements.txt` 只声明 `opencv-contrib-python`，**不要再单独加 `opencv-python`**：
> 两个包共用同一个 `cv2` 目录，同时声明会让实际版本随安装顺序漂移，导致环境不可复现。

## 一点五、❗ 命门：项目必须放在纯英文路径下

已实测确认：`check_env.py` 能过（`import mediapipe` 不报错），但**真正创建 FaceMesh 推理图时会直接失败**：

```
FileNotFoundError: The path does not exist:
  ...\mediapipe/modules/face_landmark/face_landmark_front_cpu.binarypb
```

而这个文件其实存在。原因是 MediaPipe 的原生 C++ 层在 Windows 上不认非 ASCII 路径。
判定方法：用 `subst Z: "<项目目录>"` 把同一个目录映射成纯 ASCII 盘符后跑同一份代码，
`FaceMesh` 立即初始化成功（已验证）。

两个选择：

1. **推荐：把整个项目移到纯英文无空格路径**（如教程原本写的 `E:\micro-expression\`）。
   移动后必须按第一节重建 `.venv`。现在重建成本最低，越往后越贵。
2. 不想搬：每次开工前先映射盘符，并**始终用盘符路径运行**：
   ```bat
   subst X: "E:\临时站（看见就清）\micro-expression (1)\micro-expression"
   X:
   X:\.venv\Scripts\activate
   X:\python app.py
   ```
   用完删除：`subst X: /D`

> OpenCV 不受此问题影响（第十一节的视频读取在当前中文路径下已验证可用），
> 卡住的只有 MediaPipe。但从第十二节往后全都依赖它，所以这个门必须过。

## 二、启动

```bat
.venv\Scripts\activate
python app.py
```

浏览器访问：http://127.0.0.1:5000

## 三、当前进度（对照《保姆级技术路线与 Demo 实现教程》章节）

| 教程章节 | 内容 | 状态 |
| --- | --- | --- |
| 第十节 | Flask 首页 | ✅ 完成（`templates/index.html`） |
| 第十一节 | 视频信息读取 + SHA-256 | ✅ 完成（`services/video_utils.py`） |
| 第十二节 | MediaPipe 人脸关键点检测 | ✅ 完成（`services/face_analyzer.py`，实测 478 点/帧）|
| 第十五节 | 视频上传闭环 | ✅ 完成（`POST /api/uploads` 返回时长/分辨率/帧率/SHA-256） |
| 第十三节 | 连续帧面部变化特征 | ✅ 完成（`services/feature_extractor.py`，含分区位移） |
| 第十四节 | 情绪参考分析与风险评分 | ✅ 完成（`services/emotion_analyzer.py`，含与教程的三处已声明偏差） |
| 编排层 | 十一→十四串成一条链 | ✅ 完成（`services/analysis_service.py`） |
| 第十六节 | SQLite 建模与存储 | ✅ 完成（`db.py`：cases / video / question_anchor / analysis）|
| 第十七节 | 问题锚定与重合度 | ✅ 完成（`services/question_anchor.py` + 锦点入库，红色档已可触发） |
| 第十八节 | 结果页 | ✅ 完成（`/result/<id>`，`templates/result.html`，点击行跳转采样帧） |
| 照片表情判断 | 单帧读数 + 双照相对判据 | ✅ 完成（`/photo`，实测数字直接印在页面上）|
| 数据集接入 | Lab-SMEM 226 段加载与体检 | ✅ 完成（`services/dataset_loader.py`，不依赖 openpyxl） |
| 方案 A 评测 | 峰值定位命中率（全量 226 段） | ✅ 完成（`tests/apex_localization_test.py`，结论见第六节） |
| 第十六节 | SQLite 建模与存储 | ⬜ 下一步（`models.py` 仍是占位） |
| 第十八节 | 结果页 + ECharts | ⬜ |
| 第十九节 | 报告生成 | ⬜ |
| 第二十节 | Deepfake 参考筛查 | ⬜ |

## 四、目录结构

```
app.py                      Flask 入口与路由
db.py                       SQLite 数据层（表名 cases，case 是 SQL 保留字）
config.py                   路径/帧率/采样口径等环境相关配置（单一来源）
check_env.py                环境自检
models.py                   旧占位文件（实际建表已移至 db.py）
services/                   核心处理模块，逐节增量实现
  video_utils.py            视频参数读取、SHA-256 校验
  image_io.py               绕开 cv2.imread 不认非 ASCII 路径的读图层
  face_analyzer.py          MediaPipe Face Mesh 关键点检测（视频/抽帧两种模式）
  feature_extractor.py      相邻帧位移、分区位移、3秒/1秒滑窗汇总
  emotion_analyzer.py       阈值规则情绪参考标签、风险分、四级预警档位
  action_detector.py        事件幅度曲线、峰值定位、分位标定、随机基线
  question_anchor.py        第十七节问题锚定与重合度
  dataset_loader.py         Lab-SMEM 标注解析与数据体检
  photo_emotion.py          照片构型读数 + 基准照相对判据（关键点索引已标定）
  analysis_service.py       十一→十四的编排层，输出结果页所需 JSON
tests/                      与 services 一一对应的验证脚本
  test_video.py             教程第十一节验证
  face_test.py              教程第十二节验证
  rules_test.py             第十三/十四/十七节与方案A 的规则自检（100 用例）
  database_flow_test.py     第十六~十八节闭环（建案→上传→登记→锚定→分析→结果页）
  analysis_test.py          端到端验证（需纯英文路径或 subst 盘符）
  apex_localization_test.py Lab-SMEM 全量峰值定位评测
  photo_emotion_eval.py     照片单帧分类与变化方向的实测
  photo_api_test.py         /photo 接口 24 条用例
  emotion_discriminability.py 情绪类别判别力实测（AUC / UF1 / UAR）
docs/                       排查与接口记录
  环境路径问题排查记录.md   MediaPipe 非 ASCII 路径问题的完整证据链
templates/ static/          前端页面与资源
test_data/                  测试视频与 Lab-SMEM（.gitignore 已整目录忽略）
uploads/ outputs/ instance/ 运行时产物
python/                     便携 Python 3.11.7（venv 的 base）
```

## 五、手动验证命令

```bat
:: 第十一节：读取视频参数与哈希（当前中文路径也能过）
python tests\test_video.py
python tests\test_video.py test_data\你的视频.mp4

:: 第十三、十四、十七节与方案 A：规则自检（纯数学，89 条用例，不碰 MediaPipe）
python tests\rules_test.py

:: 数据集体检（不需要 MediaPipe，当前路径就能跑）
python -m services.dataset_loader

:: 第十二节：逐帧人脸检测（每 6 帧取一帧，必须在纯英文路径或 subst 盘符下跑）
python tests\face_test.py test_data\face.mp4
python -m services.face_analyzer test_data\face_ref.jpg

:: 端到端：十一→十四全链路，结果落 outputs\analysis\latest_analysis.json
python tests\analysis_test.py
python tests\analysis_test.py test_data\face.mp4 --interval=6 --window=3 --step=1

:: 方案 A：Lab-SMEM 峰值定位评测（需纯英文路径或 subst 盘符）
python tests\apex_localization_test.py --limit=40     :: 约 1.2 分钟
python tests\apex_localization_test.py --all          :: 全量 226 段，约 9 分钟

:: 情绪类别判别力（读上面的 JSON，纯统计，当前路径就能跑）
python tests\emotion_discriminability.py

:: 照片表情判断：实测（检验 A/B）与接口用例（需纯英文路径或 subst 盘符）
python tests\photo_emotion_eval.py
python tests\photo_api_test.py
:: 浏览器打开 http://127.0.0.1:5000/photo

:: 第十六~十八节闭环（含结果页渲染断言，35 条用例）
python tests\database_flow_test.py
```

## 三点五、页面还差什么（诚实说明）

- `POST /api/uploads` 已接通，但**首页那个“上传并开始解析”按钮目前只做上传**，
  不建案件也不触发分析（`static/js/main.js` 的表单提交仍是原样）。
  要跑完整链路，目前得按下面顺序手动调 API（`tests/database_flow_test.py` 就是这条链）：
  ```bat
  curl -X POST http://127.0.0.1:5000/api/cases -H "Content-Type: application/json" -d "{\"case_no\":\"DEMO-1\",\"name\":\"演示案件\"}"
  :: 上传后拿 filename，再依次：
  :: POST /api/cases/<case_id>/videos  {"filename": "..."}
  :: POST /api/cases/<case_id>/anchors {"anchor_no":"Q1","question":"...","start_frame":30,"end_frame":60}
  :: POST /api/videos/<video_id>/analyze {"sample_interval":6}
  :: 然后浏览器打开返回的 /result/<analysis_id>
  ```
  把首页按钮接到这条链上，就是下一轮的前端工作。
- `instance/micro_observe.db` 是运行时产物，已跑过两轮测试，里面有 2 条演示案件可直接看 `/result/2`。

## 六、必须知道的实测结论

### 1. 全量 226 段实测：位移规则阈值的定位能力**不优于随机**

任务定义（方案 A）：在 onset→offset 区间里找幅度峰值帧，与标注 apex 比距离。
`static_image_mode=True`，帧率 25 fps 假设，n=226：

| 特征口径 | 误差中位 | hit@±2 | hit@±5 | hit@±10 | 随机基线@±5 | 带符号偏差 |
| --- | --- | --- | --- | --- | --- | --- |
| 相对 onset 的累积幅度 | 21 帧 | 6.2% | 15.0% | 26.1% | 17.4% | +17 帧（176/226 偏晚） |
| 相邻帧位移峰值（速度） | 20 帧 | 8.0% | 18.6% | 33.6% | 17.4% | +5 帧（125/226 偏晚） |

怎么读这张表：

- 累积幅度口径**显著劣于随机**：被头部漂移污染，峰值系统性往后跑（176/226 偏晚）。
- 速度口径无系统偏差（±5、±10 分别只呯1.2 和 0.6 个百分点），在统计上与随机无法区分。
- 结论：**纯位移规则撑不起计划书 3.3.9 的 UF1/UAR ≥80%/83%**。V1.0 必须换成训练模型，
  而这句话现在是有数据的，不再是猜测。
- 最可能的技术缺口：**没做人脸配准/去漂移**。微表情文献里的流程都是先对齐再做光流特征。
  下一个可验证改进就是一次配准，同一套评测脚本直接对比前/后。
- 复现：`python tests\apex_localization_test.py --all`（约 9 分钟）。

### 1b. 配准去漂移后仍然不达标（分层抽样 n=100，每类 25 段）

加入 `services/face_align.py`（468 点最小二乘相似变换对齐到 onset 帧）后，
五种口径在同一次推理下横比（随机基线 ±5 = 19.8%）：

| 口径 | 误差中位 | hit@±2 | hit@±5 | hit@±10 | 最优 AUC | UF1 | 偏晚比例 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 未配准·累积幅度 | 19 帧 | 7.0% | 16.0% | 30.0% | 0.650 | 0.280 | 80% |
| 未配准·逐帧速度 | 16 帧 | 8.0% | 19.0% | 40.0% | 0.668 | 0.311 | 54% |
| 配准·鼻颊 | 14 帧 | 14.0% | 22.0% | 40.0% | 0.675 | 0.349 | 72% |
| 配准·鼻颊+轮廓 | 13 帧 | 14.0% | **24.0%** | 42.0% | 0.664 | 0.332 | 70% |
| 配准·全脸 | 13 帧 | **15.0%** | 23.0% | **44.0%** | 0.658 | **0.385** | 72% |

**两个判据均 FAIL**：判据 A 最好 hit@±5 = 24.0% < 30%；判据 B 最优 AUC = 0.675 < 0.70。

但配准不是白做的，三个指标一性说明它有效：hit@±2 从 7–8% 提到 14–15%（近翻倍）、
误差中位 16→13 帧、偏晚偏差 +14→+8 帧。只是量级不够，且 z 检验下±5 优势不显著（z≈1.1）。

三个必须记下的结论：

1. **偏晚偏差没被完全消除**：4 自由度相似变换不够描述真实头动（转脸需要仿射/分区域建模），
   而且长片段上关键点自身噪声会累积。
2. **surprise 类在配准后反而更差**（0.371→0.315），再次说明幅度类特征不含效价信息，
   配准只能干净地量出“动了多少”，量不出“是什么情绪”。
3. **预登记的判定条件已触发**：规则路线到此为止，转 V1.0 模型化。
   注意：不达标不等于删掉配准——它是任何模型的特征前置，必须保留。

复现：`python tests\alignment_comparison_test.py --limit=100`（约 8 分钟），
结果文件 `outputs/analysis/alignment_comparison.json`。抽样为每类 25 段的**均衡**口径，
所以 UF1/AUC 比自然分布更有利，仍不达标——这不是抽样偏保守能解释的。

### 1c. 模型基线实测（LOSO 31 折 / 226 段 / 23 杂配准特征）

规则路线判 FAIL 后，按预登记转入模型验证。用**已装好的 scikit-learn**
（不新增任何依赖）跑留一被试交叉验证：

| 配置 | 准确率 | UF1 | UAR |
| --- | --- | --- | --- |
| 瞎猜（按类先验） | 28.6% | — | 6.2% |
| LR·只用 peak_amplitude | 24.8% | 0.218 | 26.7% |
| LR·全 23 维 | 33.2% | **0.323** | **36.0%** |
| RF·全 23 维 | **38.5%** | 0.307 | 31.4% |

（上一轮规则法的 UF1 0.385 是在 100 段**均衡抽样**上算的，与 LOSO 口径不同，不能直接横比。）

四个读数：

1. **消融给出了本轮唯一的正向结论**：单用幅度 UF1 0.218（准确率 24.8%，**低于瞎猜**），
   加上区域分布与时序形状后升到 0.323 → **配准后的“动在哪 + 怎么动”确实有信息，
   “动了多少”没有**。
2. 但最优也只有 UF1 0.323 / UAR 36.0%，距计划书目标 0.80 / 83% 差 **2.5 倍**。
3. RF 准确率最高（38.5%）但 UF1 反而低于 LR——因为它把 others 召回压到 0.07、
   surprise 压到 0.16，用少数类呚多数类。这就是**必须报 UF1/UAR而不能报准确率**的理由。
4. 两个模型优势的类别完全不同（LR surprise 0.57 vs RF negative 0.47）→ 小数据下方差很大，
   226 段 / 31 人的天花板就在这里。

要让指标真的动起来，缺的不是调参，是**表征与数据量**：光流/DTCWT/AU 强度类特征，
以及 CASME II + SMIC + SAMM 合并后约 600–1000 段。

复现：`python -m services.clip_features --limit=226`（约 3 分钟）
→ `python tests\model_baselines_test.py`（秒级）。
产物：`outputs/analysis/clip_features.jsonl`、`outputs/analysis/model_baselines.json`。

### 2. 阈值实测标定

226 段事件幅度分位：p10 = 0.00193、p50 = 0.00454、p90 = 0.01515。
教程的 0.003 / 0.012 / 0.030 大致相当于 p30 / p88 / 超出上界，
意味着**约九成真实微表情事件会被判成“中性/轻度”**。报告里应给分位标定值，
并说明它们是 Demo 参数而不是论文结论。

### 3. 情绪类别判别力实测：现在的位移特征分不出表情

以 onset→峰值累积幅度为分数、标注情绪为类别（n=226）：

| 类别 | one-vs-rest AUC | 幅度中位 | 召回率 |
| --- | --- | --- | --- |
| negative | 0.430 | 0.00392 | 7%（85 段只判对 6 段） |
| positive | 0.619 | 0.00557 | 53% |
| surprise | 0.427 | 0.00362 | 50% |
| others | 0.527 | 0.00479 | 10% |

整体：准确率 29.6% vs 瞎猜 28.6%；**UF1 = 0.251、UAR = 30.1%**（随机 UAR 25%）。
AUC 0.43–0.62 说明幅度只反映“脸动了多少”，**不携带效价方向**。
因此结果页呷示的“中性/紧张/恐惧”标签本质是运动量分档，**不能当作情绪识别结果展示**。

### 4. 红色预警现在可以触发

第十七节锚定已实现，`question_overlap` 有真实输入；无锚定时上限仍是 0.51。

### 5. “没检到脸”不再显示绿色

这类窗口单独归为 `grey / 无有效数据`，不计入绿黄红；`calculate_risk` 公式本身未动。

### 6. 两个非 ASCII 路径坑

- MediaPipe 计算图加载失败 → 必须纯英文路径或 subst 盘符（见 `docs/`）。
- `cv2.imread` 碰到中文路径**静默返回 None**，会被下游误读成“没检到人脸”。
  已由 `services/image_io.py`（pathlib 读字节 + `cv2.imdecode`）绕开，实测同一文件
  imread 返回 None、read_image 正常解出 1920×1080。

情绪标签、区域、风险分、阈值与免责声明都在每个窗口的输出里，措辞红线见
`services/emotion_analyzer.py` 顶部注释：只说“检测到紧张相关面部变化、建议人工复核”，
不说“说谎/不可信/危险性/抗拒”。

关于关键点数量：代码开着 `refine_landmarks=True`，实际输出 **478 点**（468 面部网格 + 10 虹膜），
教程正文按 468 描述。下游算特征时不要硬编码这个数。

素材说明：`test_data/test.mp4`（纯色渐变）只能验证“能不能读”；
`test_data/face.mp4`（公开肖像拼接）只能验证“能不能检到脸”；
真实结论一律以 `test_data/Lab-SMEM`（志愿者自发微表情，226 段）为准。
展示原始帧由 `config.EXPOSE_KEYFRAMES` 控制（用户已授权，但对外发布前请再确认数据集协议）。
