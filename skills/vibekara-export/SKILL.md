---
name: vibekara-export
description: 从 Namioto 工程和模板或评审采用快照构建整曲 Hook，并按请求合成原唱、伴奏或可视化视频。
---

# 构建整曲 Hook 与视频

按请求决定只交付 Hook 还是继续合成视频。默认视频规格为 **1920×1080、60 fps**。用户指定时采用目标规格。交付帧率用于生成 Hook 和视频，设计画布的比例应与 Hook 所叠加的画面一致。

样式评审采用后，从快照重建整曲 Hook。快照保留模板、打轴输入、选值，以及可编辑方案采用时的完整组合。预览与交付可以按各自的帧率编译。[整曲工作流](../vibekara/SKILL.md#从素材到交付)

复用工程或采用快照指定的编译环境。首次缺少环境时，按[安装教程](../../INSTALL.md)配置共享 uv 环境。评审与导出都应加载同一份 Namioto 和 kara-templater。[验证编译环境](../../docs/preferences.md#验证字幕编译环境)

| 已有输入 | 构建方式 |
| --- | --- |
| `.nto`，使用基础样式 | 用装有 Namioto 和 kara-templater 的 Python 运行 [`render_hook.py`](assets/render_hook.py) `SONG.nto lyrics.hook`。 |
| `.nto` 和指定设计 | 在导出脚本中调用 [`load_nto()`](assets/import_nto.py)，将返回的 `Document` 交给模板。脚本定义样式、轨道、特效和输出格式。已为评审注册的模板可用 `--script TEMPLATE.py --template ID` 构建整曲。 |
| 已采用快照 | 用 Python 运行 [rebuild_hook.py](../../kara-previwer/scripts/rebuild_hook.py) `APPROVED lyrics.hook`。重建沿用快照帧率，换解释器时加 `--python`。有采用事件但缺快照时，由评审阶段补齐。 |

直接构建用 `--fps` 覆盖默认帧率，默认使用与预览一致的 `--offset-ms -100`（提前 100 ms 显示扫色，保证所见即所得），按需覆盖 `--offset-ms` 和 `--harmony-tracks`。采用方案改变交付帧率时，从同一采用事件保存对应帧率的新快照，然后重建。回放抽查首次入唱、声部交接、换行和实际字体覆盖。

自定义导出见 README 的「进阶：从 Python 直接导出」。[工作流与组件](../../README.md#工作流与组件)

## 合成与续作

用现有歌曲构建入口，或按 kara-templater 的 [Hook 播放指南](https://github.com/sitiyou/python-kara-templater/blob/main/docs/output/hook.md) 使用 FFmpeg 的 Vulkan/libplacebo 叠加。视频沿用原曲零点，先生成目标帧率和画幅的画面，再叠加同帧率的 Hook。只有音频时，优先用已确认的封面。用户未指定画面且无可用封面时，可用匹配画布比例的中性底色。

伴奏版使用对齐后的同版官方伴奏。只有缺少同版官方伴奏时，才采用经素材阶段验收的分离伴奏。时钟一致时，复用原唱版的视频流并换入所选伴奏。

续作时逐项检查本次要求的产物。采用快照可以重建 Hook，成片仍需核验。只为缺失或失效的产物继续构建。用 ffprobe 核对视频实际帧率、分辨率、音画时长，抽查采用帧对应的原曲时间和结尾。把验收后的文件、规格和构建命令写入 `production.md` 的交付段。

需要超分或音高可视化时，见[媒体准备](../../docs/media.md#可选的视频处理)。
