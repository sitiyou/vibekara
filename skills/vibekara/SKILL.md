---
name: vibekara
description: 从歌曲素材或已有工程开始，组织整曲 karaoke 制作、续作与交付。
---

在歌曲目录维护 production.md。先读它及已有文件，再读用户配置目录 vibekara/preferences.md（若存在）。一次性要求记在本曲；用户明确要求长期保存时才更新偏好。依次记录录音版本与时长、音源与歌词及画面来源、共同零点、工程/KRC/MIDI 与偏移、样式路径、会话 ID 与存储位置、已处理游标与采用 token、输出帧率与交付文件。路径尽可能相对歌曲目录。

缺素材时调用 vibekara-assets；已有音源和歌词时交给 namioto-nicokara 打轴。用其工作流核对 BPM、带估算相位的量化网格、未量化 GAME、频谱与词音对应，交付可编辑工程、同修订的 KRC/MIDI 和歌曲输入模块 song_input.py。有轴就从样式阶段续作。用户提出样式、动效或要选择时调用 kara-previwer；无样式要求时用 vibekara-export 附带的基础外部模板直接渲染。最后交给 vibekara-export。

整曲默认交付可编辑工程、整曲 hook、原唱导练视频，有同版伴奏则一并导出。需分离伴奏时请用户决定。单阶段请求止于对应产物。新对话先核对记录中的文件以及评审 state/pending，然后继续未完成的交付。

读取 `review preferences` 的 text 和 digest。没有安装评审器时可直接读取 Markdown 开始素材工作。用一行描述一项长期偏好，合并重复，删除已撤销、已被替代和失去适用对象的条目。本曲例外留在 production.md。用 `review preferences --write draft.md --digest DIGEST` 校验后写入；冲突先重读，超出 4096 UTF-8 字节时精简，仍然放不下全部有效内容再请用户取舍。

旧工程没有 production.md 时，从 approved/accepted.json 读取 session、token、版本、选值与 fps，再核对目录中的工程和构建入口。默认会话位于 ~/.local/state/kara-previwer/SESSION，另设目录时运行 `review --root DIR state SESSION` 和 `review --root DIR pending SESSION`。state.cursor 是会话最新事件。仅在对应反馈的修订或采用产物已经落盘后，才把该事件 ID 记作已处理游标；已导出的采用事件仍可能出现在 pending 中。
