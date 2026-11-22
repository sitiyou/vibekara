# vibekara

vibekara 是一套给 AI agent 使用的卡拉 OK 制作指南。把歌曲和手头的素材交给 agent，它会核对录音版本、给歌词打轴，再生成逐字扫色的视频。想自己决定字幕长什么样，可以在浏览器里边听边选，直接截取需要修改的那一帧。

整曲默认交付 **可编辑工程、字幕 hook 和 1080p60 原唱导练视频**。有同版伴奏时，还可以导出共用同一条字幕画面的伴奏版。

[开始制作](#开始制作) · [安装](#安装) · [For AI agents](#for-ai-agents)

## 开始制作

安装指南后，打开支持 skills 的 agent，给它歌曲目录或素材链接，再说想要的成片。例如：

> 用这个目录里的专辑音源和 MV 做卡拉 OK，原唱和伴奏各一版。字幕想要圆一点的字体，给我几个方案，在副歌那段比较。

| 阶段 | 你会得到什么 |
| --- | --- |
| **1. 准备素材** | 确认使用哪一版录音，配上对应的歌词、MV 或专辑封面。MV 和专辑前奏长度不同时，先校准两者的起点。 |
| **2. 给歌词打轴** | 在 Namioto 中把歌词、读音和音符对齐，交付可编辑工程、KRC、MIDI 和供模板读取的 `song_input.py`。已有匹配的 KRC 和 MIDI，可以直接开始选样式。 |
| **3. 确定字幕样式** | 没有样式要求时直接使用[基础外部模板](skills/vibekara-export/assets/template.py)。想定制时，agent 会在 kara-previwer 里提供外部模板方案，你可以在同一段实唱中比较字体、排版、扫色和动效。 |
| **4. 导出整曲** | 使用最终选定的参数重建整曲 hook、合成视频，并检查入唱、换行和片尾。原唱版与伴奏版共用画面。 |

评审时可以暂停、逐帧查看，再截帧留言，例如「这一拍猫爪应该已经消失了」。agent 会收到带时间点和当前选值的反馈，更新方案供你复看。点击「采用这版」会保存该次提交的参数，供正式导出使用。喜欢的模板也可以收藏到下一首歌。[评审器使用说明](kara-previwer/README.md) · [偏好与模板收藏](docs/preferences.md)

继续旧工程时，把同一个歌曲目录交给 agent 即可。`production.md` 记录所用录音、打轴文件、评审进度和交付位置。

## 安装

在本仓库根目录执行以下命令，将四个 skill 链接到 agent 的发现目录。默认位置为 `~/.agents/skills`，其他宿主可设置 `AGENT_SKILLS_DIR`。

```sh
skills_dir="${AGENT_SKILLS_DIR:-$HOME/.agents/skills}"
mkdir -p "$skills_dir"
for skill in "$PWD"/skills/*; do
  target="$skills_dir/$(basename "$skill")"
  [ "$skill" -ef "$target" ] || ln -sT "$skill" "$target"
done
```

按需要安装制作工具：

- **打轴**需要 Namioto 编辑器和 CLI，并将上游的 `skills/namioto-nicokara` 链接到同一 skills 目录。[Namioto 安装说明](https://github.com/sitiyou/namioto)
- **字幕渲染**使用 kara-templater、目标字体和 Fontconfig。编写或调整模板时，将上游的 `skills/kara-templater` 链接到同一目录。浏览器评审器需要 Python 3.11+ 和 ffprobe；运行下方命令后，打开 agent 提供的会话链接。[kara-templater](https://github.com/sitiyou/python-kara-templater) · [评审器安装与前端构建](kara-previwer/README.md#启动)
- **导出视频**需要 FFmpeg、ffprobe，以及可用的 Vulkan 设备和 FFmpeg 的 `libplacebo` 滤镜。

```sh
uv tool install ./kara-previwer
review serve
```

## For AI agents

整曲制作和旧工程续作先读 [vibekara 总流程](skills/vibekara/SKILL.md)。用户只请求某个阶段时，直接进入相应指南。

| 任务 | Skill 入口 |
| --- | --- |
| 查找素材、核对录音版本和音画起点 | [vibekara-assets](skills/vibekara-assets/SKILL.md) |
| 对齐歌词、读音和音符 | [namioto-nicokara](https://github.com/sitiyou/namioto/tree/main/skills/namioto-nicokara) |
| 编写字体、排版和动效模板 | [kara-templater](https://github.com/sitiyou/python-kara-templater/tree/main/skills/kara-templater) |
| 发布候选方案、接收截帧反馈和采用参数 | [kara-previwer](skills/kara-previwer/SKILL.md) |
| 从打轴工程或采用快照重建整曲 | [vibekara-export](skills/vibekara-export/SKILL.md) |

评审事件支持宿主推送，也可以用 `review wait` 长轮询接收。续作时先核对歌曲目录的制作记录和会话状态；导出时使用采用事件提交的实际选值。[评审事件与 CLI](kara-previwer/README.md#for-ai-agents)
