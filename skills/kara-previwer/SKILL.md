---
name: kara-previwer
description: 在浏览器交给用户审核首次制作或修改的 karaoke 字幕，支持比较、调参、截帧反馈和采用快照。
---

# 评审外部模板

使用已保存的 `.nto` 和对齐后的媒体提交样式审核。模板设计参见 `kara-templater` 作者指南。评审和整曲导出复用同一个 Scene 构建函数，默认统一使用 `offset_ms: -100`（提前 100 ms 显示扫色，保证预览与成片所见即所得；仅在用户明确指定其他偏移时覆盖）。后续需要整曲交付时，从第一版起就用 `register(registry)` 注册可编译模板，并在方案中填写 `compiler.project`。[可运行模板](../vibekara-export/assets/template.py) · [方案格式](../../kara-previwer/README.md#方案文件)

优先沿用已验证的编译环境。首次缺少环境时，按[安装教程](../../INSTALL.md)配置共享 uv 环境，并将返回的解释器填入 `compiler.python`。

首轮多方向比选与组件库自编辑（`composition` + `compose_track()`）均为**可选项**，而非强制流程：

- **方向开放或用户希望自助试放组合时**：用同一份 `.nto` 和对齐媒体发布几套有明显差异的完整候选，在「预览」用动态短片展示视觉差异并在主播放器同一时刻切换；如需开放浏览器特效库拖拽与属性自编辑，再配置 `composition` 并用 `effect_components(script_height=...)` 按 `composition_height` 查可调范围，给适合即时比较的实色扫描线参数加绑定。
- **用户已有明确方向或要求定制细节特效时**：可直接提交定制模板（1 套主打方案或 2–3 套聚焦候选），只暴露字体、独立字号、描边、配色、强度等关键细调参数，无需强行套用组件库；用户已指定收藏或效果时，直接围绕指定方案制作。拿不准用户偏好时可先简短询问。

各方案沿用默认的双行左右交替布局，用户主动要求时再调整。[发布可编辑组合](../../kara-previwer/README.md#发布可编辑的组合) · [首轮方案、导唱符和验收](../../docs/first-review.md)

整曲评审默认提供可拖动时间轴，把起播位置设在代表性入唱前，便于核对注音和换行。有对齐的 MV 或故事板时使用带原唱音轨的无字幕 MP4，由评审器实时叠字幕。指定片段时只发布对应时间范围。比较多个候选时共用媒体和时间区间，写清可见差异并核对字体候选。查询控件用 [catalog.py](../../kara-previwer/scripts/catalog.py)。[画面与时间轴](../../kara-previwer/README.md#整曲时间轴) · [复用收藏](../../kara-previwer/README.md#播放与收藏)

当方案启用可编辑组合（`composition`）时，「编辑」工作区支持画面停靠、调宽或收起，并与「预览」共用播放器和时间轴：在「属性」调整字体、描边、模糊和排版（按实际声部覆盖，可点「跳到和声」定位）；在「特效」的「单选方案」与「可叠加」中搜索、试放、调参并拖拽替换/插入动效与粒子。普通定制模板则在编辑区直接展示注册的参数控件与分组。

## 发布、反馈与采用

用 Python 直接运行[评审脚本](../../kara-previwer/README.md#for-ai-agents)。用相同的 root 和 port 启动 `serve.py` 和 `create_session.py`，再用 `publish.py SESSION proposal.json --base 0` 发布。打开会话验证画面、音频和字幕后，发给用户会话链接及起播位置。保留会话供用户反馈或采用，确认线程通知是否已绑定。用户要求持续处理或等待采用时，按[会话事件说明](../../kara-previwer/README.md#事件恢复与构建)持续收取事件。

- 用 `wait_for_events.py` 或 `pending_events.py` 读取「以这套继续」提交的交接事件。事件保存所选方向、当时的完整组合、参数值和时间，可能另附意见。用 `claim_feedback.py SESSION TOKEN` 标记处理中，再用 `revise.py SESSION patch.json --base BASE --feedback TOKEN` 发布修订。优先用事件的 `base`，早期事件只有 `version`。截帧反馈沿用这条路径。更换模板时，在 patch 中填 `manifest`。修改组合时提供完整的 `composition`。
- 从事件流读到「采用这版」后运行 `snapshot.py SESSION APPROVED`，其中 `APPROVED` 为输出目录。核对返回的版本、候选编号和 token 与采用事件一致。快照保留实际使用的组合、参数值、模板和打轴输入。有指定交付帧率时，给 `snapshot.py` 加 `--fps`。把快照和输出要求交给导出阶段。
- 续作先运行 `session_state.py`。已有采用时核对快照。未采用时用 `pending_events.py` 查待处理事件，从本地最后处理的用户事件继续。只有反馈修订发布或采用输入保存后才记录对应事件 ID。已有处理结果时按 token 复用。将会话位置、游标和采用快照写入 `production.md` 的评审段。
