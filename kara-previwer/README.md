# kara-previwer

在实际歌曲画面上评审外部 karaoke 模板。网页以音频驱动字幕，保留每轮方案、播放时间、截帧和制作人的决定。

## 启动

需要 Python 3.11+ 和 ffprobe。发布时会核对片段音频时长及画面比例。服务只监听本机。[serve.py](scripts/serve.py)

```sh
python kara-previwer/scripts/serve.py
```

以上路径相对于 vibekara 仓库根目录。默认端口 18673，状态保存在 `~/.local/state/kara-previwer`。启动脚本接受 `--root` 和 `--port`。Ctrl+C 停止服务后可于同一端口恢复。修改前端时，在 `kara-previwer/` 运行 `npm ci` 和 `npm run build` 重新生成网页。

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

整曲交付需要可编译方案。`compiler.project` 指向保存好的 `.nto`，`compiler.python` 指向符合[字幕渲染依赖](../README.md#安装)的 Python 3.14 环境。可选 `offset_ms` 设置交付偏移，默认 0。`harmony_tracks` 可列出逗号分隔的和声 MIDI 渠道。服务在发布时复制可信模板、资源和工程。采用快照保留这些输入和构建规格。模板注册范例见[基础模板](../skills/vibekara-export/assets/template.py)。

```json
{
  "compiler": {
    "python": "/path/to/venv/bin/python", "script": "verse.py",
    "project": "song.nto"
  },
  "values": {"size": 100}
}
```

模板可以用 kara-templater 的 `PaintInput` 将材质专用的颜色或数值绑定到同名字段。浏览器直接更新该参数，正式 Hook 在编译时使用完整选值。参与布局、覆盖、时序或跨字段校验的参数按预览范围重新编译。

桌面预览支持 WebGL 2。无法使用它时，服务调用含 Vulkan/libplacebo 和 libvpx-vp9 的 FFmpeg 渲染所选片段，或使用 clip.fallback 中已提供的原生短片。画面右侧可调设计、填写自由意见，暂停后可逐帧、点选或圈出问题。历史意见提供原帧和新版同一时刻的对照。

`wait_for_events.py` 与 `pending_events.py` 返回的 `session_dir` 是本机绝对路径。把它与每条批注的 `image`、`annotated` 相连即可读取原图和标记图。多个完整候选可放在 manifest 的 `presets` 数组中，每项含 `title` 和对当前方案的 `values` 覆盖。比较旧版时仍可明确采用该版，后续整曲导出沿用当时的快照。

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

单击画面或按空格播放、暂停。左右方向键或暂停画面上的滚轮逐帧定位，S 截帧，点选或拖框后可附上意见。窄屏可收起「设计与意见」。WebGL 与原生回退共用控制栏和音频时钟。

在「收藏」保存正在预览的完整模板和选值。下一首歌发布可编译提案后即可选「在本曲使用」。收藏中也能改名、更新或另存。[偏好与收藏存储](../docs/preferences.md)

用收藏发起首轮时，读取 [preferences.py](scripts/preferences.py) 返回的 `templates`，把目标 ID 填到 manifest 的 `favorite`，同时提供本曲的 `clip`、`compiler.python` 和 `compiler.project`。模板脚本、资源和选值取自收藏。

### 整曲时间线

从整曲零点开始时使用 `clip.start: 0`。将已对齐的整曲媒体提供给 `clip.audio`，填写其 `duration` 和预览 `fps`。对含原唱音轨的无字幕同画幅 MP4 设置 `motion: true`，让视频驱动播放器和画面，字幕由评审器叠加。静态画面使用 `background` 和音频。`entry_frame` 是片段内从零计数的起播帧，可定位在第一次有代表性的入唱前。交付时可从同一个采用快照按目标帧率重建。[验证编译环境](../docs/preferences.md#验证字幕编译环境)

省略 `segment_frames` 会在发布时编译整个预览范围。浏览器加载一次着色器与纹理，播放与拖动直接使用媒体时间。字体、排版等几何修改会触发重新编译。

若采用按需分段，例如 30 fps 时，`segment_frames: 240` 每段覆盖 8 秒，`entry_frame: 420` 打开在媒体第 14 秒。使用可重建的外部模板，保留背景图作为初始画面。网页按播放位置请求字幕、预取下一段，并以原曲时间记录截帧。导出采用版本时会重新编译整曲。旧的固定片段仍可使用原格式。

整曲预览用同一份 Hook 定位任意时间。字号等数值滑块在拖动时同步显示数值，松手后先请求播放位置附近的字幕，再预取下一段。播放期间并行加载下一段。时间线跳到未缓存的位置时，服务按目标区间编译。WebGL 调色参数可以复用原有几何。

基础模板用 `build_lyric_scene(document, ..., preview_interval=song.preview_interval)` 准备当前窗口。严格轮转布局会保留目标行、相邻交接和影响行高的歌词。需要按完整歌词表计算章节倒数时可读取 `document.lyric_sources`。需要跨区间访问其他歌词对象的模板可以构建整曲 Scene。
