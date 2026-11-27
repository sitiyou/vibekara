# kara-previwer

在实际歌曲画面上评审外部 karaoke 模板。网页以音频驱动字幕，保留每轮方案、播放时间、截帧和制作人的决定。

## 启动

需要 Python 3.11+ 和 ffprobe。发布时会核对片段音频时长及画面比例。服务只监听本机。[serve.py](scripts/serve.py)

```sh
python kara-previwer/scripts/serve.py
```

以上路径相对于 vibekara 仓库根目录。默认端口 18673，状态保存在 `~/.vibekara/review/`。设置 `VIBEKARA_HOME` 时用其 `review/` 子目录。也可以设置 `KARA_REVIEW_ROOT`，或使用 `--root` 和 `--port` 指定会话位置。Ctrl+C 停止服务后可于同一端口恢复。修改前端时，在 `kara-previwer/` 运行 `npm ci` 和 `npm run build` 重新生成网页。

## For AI agents

使用[评审 skill](../skills/kara-previwer/SKILL.md)制作候选、处理反馈并交接采用结果。按会话状态运行相应脚本，使用自定义状态目录时传相同的 `--root`。

```sh
python kara-previwer/scripts/create_session.py '歌名'
python kara-previwer/scripts/publish.py SESSION proposal.json --base 0
python kara-previwer/scripts/wait_for_events.py SESSION --after 0 --timeout 30
python kara-previwer/scripts/pending_events.py SESSION
python kara-previwer/scripts/claim_feedback.py SESSION FEEDBACK_UUID
python kara-previwer/scripts/revise.py SESSION patch.json --base 1 --feedback FEEDBACK_UUID
python kara-previwer/scripts/session_state.py SESSION
python kara-previwer/scripts/snapshot.py SESSION song/approved
python kara-previwer/scripts/rebuild_hook.py song/approved lyrics.hook
```

### 事件、恢复与构建

- `session_state.py` 返回的 `cursor` 是最新事件 ID。`wait_for_events.py --after ID` 返回 ID 之后的反馈、采用和内部状态事件。第一次从 0 开始。持续监听时，超时后用原游标继续等。修订发布或采用快照保存后再推进制作记录的用户事件游标。
- 续作先读会话状态。未采用时用 `pending_events.py` 查未处理的反馈，用 `wait_for_events.py --after ID --timeout 0` 查对应的事件 ID。已采用时用状态里的 `accepted` token 核对快照和实际交付文件。
- `create_session.py` 在 Codex 中会尝试绑定当前线程，服务通过本机 `codex queue --resume` 投递反馈。唤醒警告写入服务日志。旧会话可在原线程用 `connect_codex.py SESSION` 补接。隔离测试时给创建脚本传 `--no-notify`。
- `snapshot.py` 保存采用版本、完整选值、模板资源和打轴数据。默认交付帧率是 60，可用 `--fps` 覆盖。相同快照可以重试。不同构建使用不同目录。`rebuild_hook.py` 从快照重建整曲 Hook，可用 `--python` 指向新的编译环境。当前会话也可以用 `export_hook.py SESSION lyrics.hook` 直接生成整曲 Hook。

## 方案文件

媒体文件以片段开头为本地零点。`clip.start` 是该点在原曲中的秒数，必须对齐 `clip.fps`。`clip.duration` 与提供的媒体时长一致。音频、图片与编译源的相对路径都以 manifest 所在目录为基准。只评审片段时可以直接提交已有的单 MAIN pass Hook。

```json
{
  "template": "amber-verse",
  "summary": "保留原画的蓝色，用暖色突出扫色。",
  "hook": "verse.hook",
  "clip": {
    "id": "verse", "start": 30, "duration": 9, "fps": 30,
    "width": 1280, "height": 720, "audio": "verse.ogg", "background": "cover.png"
  }
}
```

整曲交付需要可编译方案。`compiler.project` 指向保存好的 `.nto`，`compiler.python` 填写[安装脚本](../INSTALL.md)返回的解释器路径，或复用已验证的编译环境。可选 `offset_ms` 设置预览与交付偏移，默认 `-100`（提前 100 ms 显示扫色，预览与导出保持一致，所见即所得）。`harmony_tracks` 可列出逗号分隔的和声 MIDI 渠道。服务在发布时复制可信模板、资源和工程。采用快照保留这些输入和构建规格。模板注册范例见[基础模板](../skills/vibekara-export/assets/template.py)。

```json
{
  "compiler": {
    "python": "/path/to/venv/bin/python", "script": "verse.py",
    "project": "song.nto"
  },
  "values": {"size": 100}
}
```

模板通过 `register(registry)` 注册，构建函数接收 `kara_previwer.timing.TemplateSong` 和参数值，再返回 Scene。评审和整曲构建共用这个入口。已有采用快照换用渲染环境时，可给 `rebuild_hook.py` 传 `--python`。

模板可以用 kara-templater 的 `PaintInput` 将材质专用的颜色或数值绑定到同名字段。浏览器直接更新该参数，正式 Hook 在编译时使用完整选值。参与布局、覆盖、时序或跨字段校验的参数按预览范围重新编译。

桌面预览支持 WebGL 2。无法使用它时，服务调用含 Vulkan/libplacebo 和 libvpx-vp9 的 FFmpeg 渲染所选片段，或使用 clip.fallback 中已提供的原生短片。编辑工作区可以调整设计和填写意见。暂停后可逐帧、点选或圈出问题。历史意见提供原帧和新版同一时刻的对照。

`wait_for_events.py` 与 `pending_events.py` 返回的 `session_dir` 是本机绝对路径。把它与每条批注的 `image`、`annotated` 相连即可读取原图和标记图。多个完整候选可放在 manifest 的 `presets` 数组中，每项含 `title` 和对当前方案的 `values` 覆盖。比较旧版时仍可明确采用该版，后续整曲导出沿用当时的快照。

## 发布可编辑的组合

用同一份 `.nto`、对齐后的媒体和时间区间发布几套观感不同的候选。每份 manifest 可包含自己的 `composition`。让模板的 `build` 显式接收 `composition` 关键字参数，再通过 `compose_track()` 构建场景。编译器使用包含组件 API 的 kara-templater 环境。[可运行的组合模板](examples/composition_template.py)

```json
{
  "composition_height": 720,
  "composition_tracks": {"lead": "主唱", "harmony": "和声"},
  "composition": {
    "version": 1,
    "groups": [{
      "id": "front",
      "label": "扫色与轮廓",
      "track": "lead",
      "components": [{
        "id": "scan",
        "component": "highlight-scanline",
        "target": "track",
        "values": {"scanline_width": 19},
        "bindings": {"scanline_width": "scan_width"},
        "controls": {"scanline_width": {"bounds": [3, 42], "label": "扫描线宽度"}}
      }]
    }]
  }
}
```

用 `effect_components(script_height=720)` 查看本例的内置组件 ID、作用对象和参数。省略参数时使用组件默认值。可在节点的 `fields` 中列出公开参数。同一候选内，特效组和组件节点的 ID 必须唯一。需要联动的实时参数可共用绑定名称，类型、默认值和控件设置须一致，且名称须避开模板注册的顶层参数。给已绑定的参数添加 `controls`，可以缩小范围，并设置步长、标签、分组和顺序。单位和默认范围由组件提供。字体、排版等参数变更会触发片段重建。

`composition_tracks` 给模板轨道提供显示名称。通过 `build_lyric_scene()` 构建的候选只列出已发布时间范围内有歌词的声部。只有一个声部时，界面直接显示编辑控件。编辑当前未唱到的和声时，播放头留在原位，可点「跳到和声」定位。

- 「预览」用大画面播放。多候选时可展开同一处歌词的短片，切换候选会保留主画面的播放位置。
- 「编辑」铺满工作区，画面可在左右停靠、调宽或收起。两个布局共用播放器，整曲时间轴贴着画面移动。往返时会恢复编辑位置和同一候选的试放。属性和特效集中在编辑面板内，画面与播放控件一起停靠。
- 在「编辑」的「属性」里改文字样式、唱前唱后配色和歌词排版。候选可共用设置，也可按实际声部覆盖。点「恢复继承值」会撤销该项覆盖。
- 「特效库」分为「单选方案」和「可叠加」，搜索会查找两边的效果。每个声部中，入场、退场、走字等各自单选，可从库中选择或拖到「单选效果」更换同类设置。正文与注音可以分别设置支持这两个作用对象的效果。「叠加效果」支持重复添加动效和粒子，拖到两项之间插入，拖到某项中央替换。点已选项目可调参，也可先在本曲试放再加入草稿。

每个候选单独保存草稿，切换与刷新后可恢复。打开页面期间可撤销编辑，也可用「恢复候选原样」重置当前草稿。发布新版本后，可从版本菜单打开旧候选和草稿。

点击「以这套继续」会向 Agent 提交当时的候选、完整组合、参数值和当前时间。可在「本轮意见」里附说明。之后的编辑继续写入草稿。用 `pending_events.py` 或 `wait_for_events.py` 读取交接事件，再用 `claim_feedback.py` 标记处理中，最后用 `revise.py` 发布修订。修订沿用事件中的组合，也可在 patch 中提供完整的 `composition`。点击「采用这版」会确定正式交付的输入。快照中的 `accepted.json` 保留采用的选值和组合，`rebuild_hook.py` 用它及快照内保存的模板和打轴输入重建 Hook。

## 候选与差量修订

用 [catalog.py](scripts/catalog.py) 查询声明字段。同一模板的预设使用 presets。首轮需比较不同模板时，主 manifest 加入 `"alternatives": ["quiet.json", "particles.json"]`，各 manifest 提供自己的模板、参数、title 与 summary，以及相同音频、背景和时间区间。用 sample 提供本曲歌词，fonts 按字段列出候选字体的准确名称。渲染环境需有 Fontconfig 的 fc-match。

```json
{
  "sample": "気まぐれで青い海を",
  "fonts": {"font": ["FOT-TsukuMin Pro B", "Noto Serif CJK JP"]},
  "groups": {"文字": ["font", "size"], "动效": ["highlight", "stars"]}
}
```

用 `"percent_of": {"ruby_percent": "size"}` 为一个整数比例字段显示换算后的字号。示例中的 `ruby_percent` 和 `size` 都由模板声明，分别用 `%` 和 ` px` 作为字段后缀。浏览器拖动时显示四舍五入的字号，模板按相同规则应用。

收到反馈后，将 patch 交给 `revise.py`。values 只写本轮改动，focus 控制首屏细调字段。用户随时可展开其他参数或回看旧版。需要替换模板时传 manifest 路径，需要增添候选时传 alternatives 路径数组。无法继承的字段列在 not_inherited。模板附带的数据文件用 compiler.resources 指定，例如 `{"textures/star.png": "art/star.png"}`，脚本以自身所在目录为基准读取。发布、收藏和导出都会复制这些资源。

```json
{"values":{"border":7,"rate":0.5},"focus":["border","rate"],"summary":"加厚描边，减少星屑"}
```

## 播放与收藏

单击画面或按空格播放、暂停。左右方向键或暂停画面上的滚轮逐帧定位，S 截帧，点选或拖框后可附上意见。有可编辑组合的会话可在「编辑」和「预览」间切换。编辑时可收起画面腾出空间，桌面停靠位置和宽度保存在当前浏览器。窄屏用紧凑画面。特效区同时展示已选效果与「特效库」，点已选项目即可进入参数页，返回时保留原分类和搜索词。WebGL 与原生回退共用控制栏和音频时钟。

跨曲收藏适用于传统模板。可以在「收藏」保存当前模板和选值。下一首歌发布可编译候选后，即可将收藏「在本曲使用」。已有收藏可以改名、更新或另存。特效组合在本曲会话中保存草稿。[偏好与收藏存储](../docs/preferences.md)

用收藏发起首轮时，读取 [preferences.py](scripts/preferences.py) 返回的 `templates`，把目标 ID 填到 manifest 的 `favorite`，同时提供本曲的 `clip`、`compiler.python` 和 `compiler.project`。模板脚本、资源和选值取自收藏。

### 整曲时间轴

从整曲零点开始时使用 `clip.start: 0`。将已对齐的整曲媒体提供给 `clip.audio`，填写其 `duration` 和预览 `fps`。对含原唱音轨的无字幕同画幅 MP4 设置 `motion: true`，让视频驱动播放器和画面，字幕由评审器叠加。静态画面使用 `background` 和音频。`entry_frame` 是片段内从零计数的起播帧，可定位在第一次有代表性的入唱前。交付时可从同一个采用快照按目标帧率重建。[验证编译环境](../docs/preferences.md#验证字幕编译环境)

省略 `segment_frames` 会在发布时编译整个预览范围。浏览器加载一次着色器与纹理，播放与拖动直接使用媒体时间。字体、排版等几何修改会触发重新编译。

若采用按需分段，例如 30 fps 时，`segment_frames: 240` 每段覆盖 8 秒，`entry_frame: 420` 打开在媒体第 14 秒。使用可重建的外部模板，保留背景图作为初始画面。网页按播放位置请求字幕、预取下一段，并以原曲时间记录截帧。导出采用版本时会重新编译整曲。

整曲时间轴始终对应原曲媒体。字号等数值滑块在拖动时同步显示数值，松手后先请求播放位置附近的字幕，再预取下一段。播放期间并行加载下一段。时间轴跳到未缓存的位置时，服务按目标区间编译。WebGL 调色参数可以复用原有几何。

基础模板用 `build_lyric_scene(document, ..., preview_interval=song.preview_interval)` 准备当前窗口。严格轮转布局会保留目标行、相邻交接和影响行高的歌词。需要按完整歌词表计算章节倒数时可读取 `document.lyric_sources`。需要跨区间访问其他歌词对象的模板可以构建整曲 Scene。

## 读取内置特效卡片

发布可编辑方案时，评审器从 `compiler.python` 对应的 kara-templater 读取组件目录和已生成的卡片，将封面和短片保存到会话。源码安装尚无生成的卡片时，评审器使用本仓库随附的预览。各版本的卡片可在离线状态下回看。

开发时，在 kara-templater 仓库运行 `uv run --no-sync python -m tools.build_component_library`。可传 `--card CARD_ID` 只生成指定卡片。发布新方案时，将环境变量 `KARA_TEMPLATER_COMPONENT_PREVIEWS` 指向上游的 `build/component-catalog/previews/`。已有会话保留各版发布时的卡片。
