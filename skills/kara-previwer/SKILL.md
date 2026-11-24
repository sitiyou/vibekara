---
name: kara-previwer
description: 在浏览器交给用户审核首次制作或修改的 karaoke 字幕，支持比较、调参、截帧反馈和采用快照。
---

# 评审外部模板

使用已保存的 `.nto` 和对齐后的媒体提交样式审核。设计交给 `kara-templater` 作者指南。评审和整曲导出复用同一个 Scene 构建函数。后续需要整曲交付时，从第一版起就用 `register(registry)` 注册可编译模板，并在方案中填写 `compiler.project`。[可运行模板](../vibekara-export/assets/template.py) · [方案格式](../../kara-previwer/README.md#方案文件)

设计方向开放时，首轮用同一段画面比较几个主机制有明显差异的完整方案，让用户先选方向。查效果目录了解有哪些机制，再按本曲筛选。选定方向后根据反馈开放细调。各方案沿用默认的双行左右交替布局，用户主动要求时再调整布局。用户指定了唯一效果或已经进入定向修订时，按指定范围提交。[首轮方案、导唱符和验收](../../docs/first-review.md)

整曲评审默认提供可拖动时间线，把起播位置设在代表性入唱前，便于核对注音和换行。有对齐的 MV 或故事板时使用带原唱音轨的无字幕 MP4，由评审器实时叠字幕。指定片段时只发布对应时间范围。比较多个候选时共用媒体和时间区间，写清可见差异并核对字体候选。查询控件用 [catalog.py](../../kara-previwer/scripts/catalog.py)。[画面与时间线](../../kara-previwer/README.md#整曲时间线) · [复用收藏](../../kara-previwer/README.md#播放与收藏)

## 发布、反馈与采用

用 Python 直接运行[评审脚本](../../kara-previwer/README.md#for-ai-agents)。用相同的 root 和 port 启动 `serve.py` 和 `create_session.py`，再用 `publish.py SESSION proposal.json --base 0` 发布。打开会话验证画面、音频和字幕后，发给用户会话链接及起播位置。保留会话供用户反馈或采用，确认线程通知是否已绑定。用户要求持续处理或等待采用时，按[会话事件说明](../../kara-previwer/README.md#事件恢复与构建)持续收取事件。

- 收到反馈后用 `claim_feedback.py SESSION TOKEN`，读取用户完整选值和批注图片，再用 `revise.py SESSION patch.json --base VERSION --feedback TOKEN` 发布修订。需要新增能力或替换模板时，在 patch 中填 `manifest` 指向新方案。局部修订聚焦用户实际提出的变化。
- 收到采用后，以采用事件的版本、方向、完整选值和 token 为准。需要重建整曲时运行 `snapshot.py SESSION APPROVED`，交付规格另有帧率时加 `--fps`。交给导出阶段的是采用快照和本次输出要求。
- 续作先运行 `session_state.py`。已有采用时核对快照。未采用时用 `pending_events.py` 查待处理事件，从本地最后处理的用户事件继续。只有反馈修订发布或采用输入保存后才记录对应事件 ID。已有处理结果时按 token 复用。将会话位置、游标和采用快照写入 `production.md` 的评审段。
