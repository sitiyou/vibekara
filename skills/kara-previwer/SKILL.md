---
name: kara-previwer
description: 在浏览器交给用户审核首次制作或修改的 karaoke 字幕，支持比较、调参、截帧反馈和采用快照。
---

# 评审外部模板

使用已保存的 `.nto` 和对齐后的媒体提交样式审核。模板设计参见 `kara-templater` 作者指南。评审和整曲导出复用同一个 Scene 构建函数，默认统一使用 `offset_ms: -100`（提前 100 ms 显示扫色，保证预览与成片所见即所得；仅在用户明确指定其他偏移时覆盖）。后续需要整曲交付时，从第一版起就用 `register(registry)` 注册可编译模板，并在方案中填写 `compiler.project`。[可运行模板](../vibekara-export/assets/template.py) · [方案格式](../../kara-previwer/README.md#方案文件)

优先沿用已验证的编译环境。首次缺少环境时，按[安装教程](../../INSTALL.md)配置共享 uv 环境，并将返回的解释器填入 `compiler.python`。

设计方向开放时，用同一份 `.nto` 和对齐媒体发布几套有明显差异的完整候选。为每套候选备好文字和排版属性，再选走字、动效和装饰。在「预览」用动态短片展示视觉差异，主播放器在同一时刻切换候选。用 `effect_components(script_height=...)` 按方案中的 `composition_height` 查可调范围。给适合即时比较的实色扫描线参数加绑定，排版类参数由评审器重建片段。各方案沿用默认的双行左右交替布局，用户主动要求时再调整。用户已指定效果时，围绕指定效果准备候选。[发布可编辑组合](../../kara-previwer/README.md#发布可编辑的组合) · [首轮方案、导唱符和验收](../../docs/first-review.md)

整曲评审默认提供可拖动时间轴，把起播位置设在代表性入唱前，便于核对注音和换行。有对齐的 MV 或故事板时使用带原唱音轨的无字幕 MP4，由评审器实时叠字幕。指定片段时只发布对应时间范围。比较多个候选时共用媒体和时间区间，写清可见差异并核对字体候选。查询控件用 [catalog.py](../../kara-previwer/scripts/catalog.py)。[画面与时间轴](../../kara-previwer/README.md#整曲时间轴) · [复用收藏](../../kara-previwer/README.md#播放与收藏)

「编辑」工作区内的画面可停靠、调宽或收起。两个布局共用播放器，时间轴跟着画面移动，切换时保留同一候选的试放。用「属性」调整字体、描边、模糊和排版。候选属性可共用，只有实际出现的声部可单独覆盖。切换声部时保留播放位置，需要核对就在面板点「跳到和声」。打开「特效」，在「单选方案」按类别比较动画，在「可叠加」浏览动效和粒子。搜索覆盖整个特效库。入场、走字等单选效果可拖到「单选效果」更换同类设置。动效和粒子可重复加入「叠加效果」，拖到间隙插入，拖到某项中央替换。点当前组合里的项目进入参数页，返回后可继续浏览原分类。试放时可以先调参，再将试好的版本加入草稿。

## 发布、反馈与采用

用 Python 直接运行[评审脚本](../../kara-previwer/README.md#for-ai-agents)。用相同的 root 和 port 启动 `serve.py` 和 `create_session.py`，再用 `publish.py SESSION proposal.json --base 0` 发布。打开会话验证画面、音频和字幕后，发给用户会话链接及起播位置。保留会话供用户反馈或采用，确认线程通知是否已绑定。用户要求持续处理或等待采用时，按[会话事件说明](../../kara-previwer/README.md#事件恢复与构建)持续收取事件。

- 用 `wait_for_events.py` 或 `pending_events.py` 读取「以这套继续」提交的交接事件。事件保存所选方向、当时的完整组合、参数值和时间，可能另附意见。用 `claim_feedback.py SESSION TOKEN` 标记处理中，再用 `revise.py SESSION patch.json --base BASE --feedback TOKEN` 发布修订。优先用事件的 `base`，早期事件只有 `version`。截帧反馈沿用这条路径。更换模板时，在 patch 中填 `manifest`。修改组合时提供完整的 `composition`。
- 从事件流读到「采用这版」后运行 `snapshot.py SESSION APPROVED`，其中 `APPROVED` 为输出目录。核对返回的版本、候选编号和 token 与采用事件一致。快照保留实际使用的组合、参数值、模板和打轴输入。有指定交付帧率时，给 `snapshot.py` 加 `--fps`。把快照和输出要求交给导出阶段。
- 续作先运行 `session_state.py`。已有采用时核对快照。未采用时用 `pending_events.py` 查待处理事件，从本地最后处理的用户事件继续。只有反馈修订发布或采用输入保存后才记录对应事件 ID。已有处理结果时按 token 复用。将会话位置、游标和采用快照写入 `production.md` 的评审段。
