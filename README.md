# vibekara

vibekara 是给 AI agent 制作卡拉 OK 用的 skill。把歌曲和手头的素材交给 agent，它会核对录音版本、给歌词打轴，并提供浏览器评审。你可以边听边调整字幕，也可以直接截取需要修改的那一帧。

整曲默认交付 **可编辑工程、字幕 hook 和 1080p60 原唱导练视频**。有同版伴奏时，还可以导出共用同一条字幕画面的伴奏版。

[开始制作](#开始制作) · [安装](#安装) · [For AI agents](#for-ai-agents)

## 开始制作

在启用了 vibekara 的 agent 中，最少给 **一项能找到目标录音的线索**，例如歌曲目录、原唱音频、具体的歌曲或 MV 链接，或者歌名、歌手和版本。再说明要整曲视频、只要打轴工程，还是只要 Hook。已有的歌词、封面、伴奏和打轴文件可以一并提供，agent 按本次交付补齐缺项。[输入格式和缺项处理](docs/media.md#可以提供什么)

> 用这个 MV 做一版原唱卡拉 OK。歌词帮我找，画面就用 MV。

| 阶段 | 你会得到什么 |
| --- | --- |
| **1. 准备素材** | 确认使用哪一版录音，配上对应的歌词、MV 或专辑封面。MV 和专辑前奏长度不同时，先校准两者的起点。 |
| **2. 给歌词打轴** | 用参考录音和歌词在 Namioto 打轴，或打开已有 `.nto` 续修。保存后的 `.nto` 供评审和导出直接读取。 |
| **3. 审核字幕样式** | 首次制作或调整样式时，agent 发来 kara-previwer 链接。方向开放时，首轮比较几套差异明显的完整设计。选定方向后，再调整入场、唱读提示、离场等细节。需要直接导出时可以明确说明。 |
| **4. 导出整曲** | 使用已采用的方案重建整曲 Hook、合成视频，并检查入唱、换行和片尾。原唱版与伴奏版共用画面。 |

评审时可以暂停、逐帧查看，再截帧留言，例如「这一拍猫爪应该已经消失了」。agent 会收到带时间点和当前选值的反馈，更新方案供你复看。点击「采用这版」会保存该次提交的参数，供正式导出使用。喜欢的模板也可以收藏到下一首歌。[评审器使用说明](kara-previwer/README.md) · [偏好与模板收藏](docs/preferences.md)

[制作第一版评审](docs/first-review.md)介绍如何从曲目出发选择能直接比较的设计方向，以及发布前如何核对实际画面。

继续旧工程时，把同一个歌曲目录交给 agent 即可。`production.md` 记录所用录音、打轴文件、评审进度和交付位置。

本机媒体库和账号惯例可写入[本地偏好](docs/preferences.md)。[媒体准备](docs/media.md)和[投稿指南](docs/publishing.md)按需使用。

## 安装

把下面这段话复制给你的 AI agent，或者按 [INSTALL.md](INSTALL.md) 手动安装。

```text
请从 https://github.com/sitiyou/vibekara 安装 vibekara。先阅读仓库的 INSTALL.md，
复用本机已有工具，按默认路径配置 uv 环境并为当前 agent 注册 Skill。
如果缺少需要管理员权限的系统依赖，请告诉我具体缺项和安装入口。
环境和 Skill 配好后，告诉我 checkout、Python 解释器和 Skill 的位置。
```

## 从 Python 导入 Namioto 工程

在 vibekara 仓库根目录用 [安装教程](INSTALL.md) 输出的解释器运行[渲染脚本](skills/vibekara-export/assets/render_hook.py)。

```sh
~/.vibekara/.venv/bin/python skills/vibekara-export/assets/render_hook.py song.nto lyrics.hook
```

自定义导出时，将本仓库的 `skills/vibekara-export/assets` 加入 Python 的模块搜索路径，再导入 [import_nto.py](skills/vibekara-export/assets/import_nto.py)。`load_nto()` 直接把保存的 `.nto` 读成内存里的 `Document`，包含歌词、分段读音、章节、声部和 BPM。导出脚本决定使用哪些字体、轨道、特效和输出格式。

```python
from kara_templater import KaraokeEffects, Style, Track, build_lyric_scene
from import_nto import load_nto

document = load_nto(
    "song.nto",
    styles=(Style(name="default", fontname="sans-serif", fontsize=96),),
)
scene = build_lyric_scene(
    document,
    tracks=(Track(id="lyrics", effects=(KaraokeEffects(),)),),
)
scene.export("lyrics.hook")
```

`document.lyric_sources` 提供逐行歌词，`source.actor` 是 MIDI 渠道编号的字符串。需要提前 100 ms 时传 `offset_ms=-100`。如果用 `harmony_tracks="1"` 将渠道 1 标为 `top`，自定义样式里也可定义同名样式供和声轨选择。

## For AI agents

整曲制作和旧工程续作先读 [vibekara 总流程](skills/vibekara/SKILL.md)。用户只请求某个阶段时，直接进入相应指南。

| 任务 | Skill 入口 |
| --- | --- |
| 查找素材、核对录音版本和音画起点 | [vibekara-assets](skills/vibekara-assets/SKILL.md) |
| 对齐歌词、读音和音符 | `deps/namioto/skills/namioto-nicokara/SKILL.md` |
| 编写字体、排版和动效模板 | `deps/kara-templater/skills/kara-templater/SKILL.md` |
| 发布候选方案、接收截帧反馈和采用参数 | [kara-previwer](skills/kara-previwer/SKILL.md) |
| 从打轴工程或采用快照重建整曲 | [vibekara-export](skills/vibekara-export/SKILL.md) |

评审采用后保存可重建快照。续作时可从快照补建 Hook 或继续合成缺失的视频。[评审脚本与事件](kara-previwer/README.md#for-ai-agents)
