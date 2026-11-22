---
name: kara-previwer
description: 用实际歌曲片段评审外部 karaoke 模板，发布多方向提案、接收截帧反馈并保存采用快照。
---

使用 review CLI。按 kara-templater 指南设计外部模板，遵守已指定的字体、背景与动效。在同一有入唱、注音和换行的片段提供可明显区分的方向，说明画面上能看到的差异。字体候选用本曲歌词试样，选渲染环境实际支持的字族和字重。允许混搭与自由意见；下一轮围绕用户实际提交的选值，只突出所提细节。

运行 review create 歌名、review publish SESSION proposal.json --base 0，交付会话网址。独立宿主使用 review wait SESSION --after ID --timeout 30，首次 ID 为 0；超时继续等。按事件顺序处理，重复 token 读取已有结果。反馈先 claim，读其完整参数与所附图，再按反馈发布修订；采用事件里的版本和值决定导出。落盘成功后才把游标及 token 写回 production.md。中断后用 review state 和 review pending 核对记录并从游标续等。宿主推送可唤醒同一处理流程。

先运行 `review catalog` 查询控件。首轮以 alternatives 列出同片段的其他 manifest，以 presets 混搭当前模板的参数。提供 sample 的实际歌词、fonts 候选和参数 groups。收到反馈时将 values 差量、focus 和 summary 写入 patch.json，执行 `review revise SESSION patch.json --base VERSION --feedback TOKEN`。若需新增视觉能力，更新外部模板后重新 publish。保存的模板可从网页「收藏」选择，在本曲生成新版本。

发布前确认服务端口已监听；需要时运行 `review serve`。create、serve 与后续命令共用 root 和 port。完整方案格式与示例见仓库的 [评审器 README](../../kara-previwer/README.md)。如果旧会话采用时的字体已缺失，先列出现可解析的替代字族与字重，从歌曲快照发起新一轮评审并重新采用。

用户明确要复用收藏时，先查 review preferences；在首轮 manifest 填 favorite ID、目标 clip 和 compiler 的 python、KRC、MIDI、本曲偏移，即可直接从收藏开始。

整曲评审优先提供可拖动的完整媒体。通常在发布时编译整曲 hook，省略 clip.segment_frames。浏览器一次加载后按媒体时间绘制，跳转无须请求字幕分段。若实测整曲资源超过设备容量，或需要缩短频繁改稿的编译等待，再用 clip.segment_frames 启用分段。用 clip.entry_frame 指向有代表性的实唱或上次反馈处。原 MV 与录音对齐后，用带音轨的整曲视频作 clip.audio 并设置 motion=true。发布后检查远处冷跳转、跨段扫色、原曲时间截帧及结尾，保留相同媒体时钟供后续修订。
