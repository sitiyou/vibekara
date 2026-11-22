---
name: vibekara-export
description: 从已打轴 KRC/MIDI 或采用的外部模板导出整曲 hook 和原唱、伴奏 karaoke 视频。
---

正式视频默认导出为 **1920×1080、60 fps**。用户或交付要求指定其他规格时按指定值。评审片段的尺寸和帧率只用于预览。先核对歌曲记录的时间基准、MIDI 类型与交付规格。无样式要求时，把[基础外部模板](assets/template.py)复制到打轴阶段交付的 `song_input.py` 旁，用安装了 Namioto 和 kara-templater 的解释器运行 `python template.py`。该入口读取歌曲数据并调用 `Scene.export_hook`，在歌曲目录输出 `lyrics.hook`。根据交付规格调整导出帧率。复查实际字体对全曲文字和注音的覆盖。

定制方案使用评审采用的外部模板、完整选值和输入快照。评审编译器从 KRC/MIDI 构造同样的语义输入；让其 MIDI 模式、声部映射和偏移与打轴交接一致，预唱提前量只应用一次。

低清动画 MV 升至 1080p 时，优先从最高质量的原始画面试用 **2× Adore**。用含细线、小字和运动的短片段与普通缩放同帧比较，检查细节、色彩、闪烁与过锐。按原帧率做一次超分，保留宽高比、色彩范围和时间基准；如模型需要补齐输入尺寸，推理后按倍率裁掉补边。随后缩放至交付尺寸、对齐音画并转换帧率，最后叠加目标分辨率的字幕。可复用同一份超分画面制作原唱和伴奏版本。

沿用歌曲构建入口或使用 FFmpeg 的 Vulkan/libplacebo custom_shader_path 叠加整曲 hook。先按成片帧率生成画面，等比缩放并补边至目标尺寸，再叠加同帧率的 hook，使字幕在每个输出帧上重新绘制。静态封面按目标帧率循环到音频结尾。伴奏版复用视频流并换入同时间基准的音轨。用 ffprobe 检查分辨率、帧率和音画时长；抽查开头、采用帧对应的原曲时间和末尾。记录实际交付文件及命令。用户明确要求时才投稿。

例如 `review export SESSION video.hook --snapshot approved` 同时保存已采用模板源、歌曲 KRC/MIDI 和构建参数。稍后运行 `review rebuild approved video.hook`。迁到另一套运行环境时用 --python 指向装有模板依赖的解释器。
