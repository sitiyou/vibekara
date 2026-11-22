# kara-previwer

在实际歌曲画面上评审外部 karaoke 模板。网页以音频驱动字幕，保留每轮方案、播放时间、截帧和制作人的决定。

## 启动

需要 Python 3.11+ 和 ffprobe。发布时会核对片段音频时长及画面比例。从源码构建前端需要 Node 和 npm。服务只监听本机。

```sh
npm ci
npm run build
python -m pip install .
review serve
```

若直接在源码目录运行，可用 `python -m kara_previwer.cli` 替代 `review`。默认端口 18673，状态保存在 `~/.local/state/kara-previwer`。用全局选项 `--root`、`--port` 覆盖。Ctrl+C 停止服务后可于同一端口恢复。

## For AI agents

无样式要求时，导出阶段直接使用 vibekara-export 的基础外部模板。有样式要求或制作者想自己挑选时，选择或编写外部模板，挑选能听见入唱、能看见注音及换行的片段。首轮在同一片段给出多个有明显差别的方向，接受用户混搭或自由描述。修订继承该次提交的选值，重点展示用户要求细调的字段。

```sh
review create '歌名'
review publish SESSION proposal.json --base 0
review wait SESSION --after 0 --timeout 30
review pending SESSION
review claim SESSION FEEDBACK_UUID
review revise SESSION patch.json --base 1 --feedback FEEDBACK_UUID
review state SESSION
review export SESSION approved.hook --snapshot song/approved
review rebuild song/approved rebuilt.hook
```

正式视频默认 1920×1080、60 fps。`review export` 默认按 60 fps 编译整曲 hook，可用 `--fps` 覆盖；视频尺寸由最终合成步骤设置。

把 create 返回的地址交给制作人。持续等待，按已读事件 ID 更新 `--after`。每次超时继续等待。Agent 重启先读 pending 和 state。claim 通知页面已经开始处理。根据反馈检查所附 PNG，更新模板或参数，在 summary 中写明具体变化。修订继承仍受支持的选值，manifest 的 values 显式覆盖。发布时服务核对 base，重试同一反馈和同一修订返回同一版本。采用事件绑定确切版本和参数。采用后，将该事件的完整 values 写回歌曲制作方案。按原任务交付范围重建整曲 hook 和约定的视频，抽查对应帧后再确认完成。投稿另行授权。从 Codex 发起 create 时会绑定当前线程。服务把反馈和采用事件通过本机 codex queue --resume 投递给该线程，服务重启后从持久化游标继续。CLI 成功入队与宿主成功唤醒分别判断，唤醒警告记录在服务日志。旧会话可在原线程运行 review connect-codex SESSION 补接。独立测试用 review create --no-notify。

## 方案文件

音频文件从片段起点剪出。start 是原曲秒数，必须对齐 fps。按该原曲区间导出 kara-templater 的单 MAIN pass hook。音频、图片与编译源的相对路径以 manifest 所在目录为基准。已编译的零参数模板可独立使用：

```json
{
  "template": "amber-verse",
  "summary": "保留原画的蓝色，用暖色突出已唱字。",
  "hook": "verse.hook",
  "clip": {
    "id": "verse", "start": 30, "duration": 9, "fps": 30,
    "width": 1280, "height": 720, "audio": "verse.ogg", "background": "cover.png"
  }
}
```

可编译方案在 compiler 中记录打轴交付的 `krc`、`midi`、`wavetone`、`offset_ms`。有显式声部角色或项目颜色时，通过 `track_style`（如 `{"1":"top"}`）和 `colors` 传入。模板读取同一套定时数据。编译时使用安装了 namioto 和 kara-templater 的 Python。模板注册时声明 `semantic=True`。本机 Agent 显式提供可信脚本。服务在发布时保存脚本、KRC 和 MIDI 的内容快照。模板应自包含，解释器、字体和依赖需要在同一环境中保持可用。

```json
{
  "compiler": {
    "python": "/path/to/venv/bin/python", "script": "verse.py",
    "krc": "lyrics.krc", "midi": "notes.mid", "offset_ms": -100
  },
  "values": {"size": 100}
}
```

模板可将只负责绘制且独占一个 RGB 默认色的字段列入 `palette_parameters`。浏览器可在字内渐变插值前直接更新该颜色；模板最终用所选 RGB 正常生成完整 hook。若其他效果共用该颜色或由它派生新颜色，使用普通 color 字段走编译路径。几何和时间变更按当前方案的预览范围编译、缓存。固定 hook 的会话采用后，可从 state 与接受事件取得资源及参数快照；整曲导出需要提供 compiler。

桌面预览支持 WebGL 2。无法使用它时，服务调用含 Vulkan/libplacebo 和 libvpx-vp9 的 FFmpeg 渲染所选片段，或使用 clip.fallback 中已提供的原生短片。画面右侧可调设计、填写自由意见，暂停后可逐帧、点选或圈出问题。历史意见提供原帧和新版同一时刻的对照。

`wait` 与 `pending` 返回的 `session_dir` 是本机绝对路径。把它与每条批注的 `image`、`annotated` 相连即可读取原图和标记图。多个完整候选可放在 manifest 的 `presets` 数组中，每项含 `title` 和对当前方案的 `values` 覆盖。比较旧版时仍可明确采用该版，后续整曲导出沿用当时的快照。

## 候选与差量修订

`review catalog` 可查询声明字段。同一模板的预设使用 presets。首轮需比较不同模板时，主 manifest 加入 `"alternatives": ["quiet.json", "particles.json"]`，各 manifest 提供自己的模板、参数、title 与 summary，以及相同音频、背景和时间区间。用 sample 提供本曲歌词，fonts 按字段列出候选字体的准确名称。渲染环境需有 Fontconfig 的 fc-match。

```json
{
  "sample": "気まぐれで青い海を",
  "fonts": {"font": ["FOT-TsukuMin Pro B", "Noto Serif CJK JP"]},
  "groups": {"文字": ["font", "size"], "动效": ["singing", "stars"]}
}
```

收到反馈后，以下 patch 用于 `review revise`。values 只写本轮改动，focus 控制首屏细调字段。用户随时可展开其他参数或回看旧版。需要替换模板时传 manifest 路径，需要增添候选时传 alternatives 路径数组。无法继承的字段列在 not_inherited。模板附带的数据文件用 compiler.resources 指定，例如 `{"textures/star.png": "art/star.png"}`，脚本以自身所在目录为基准读取。发布、收藏和导出都会复制这些资源。

```json
{"values":{"border":7,"rate":0.5},"focus":["border","rate"],"summary":"加厚描边，减少星屑"}
```

## 播放与收藏

单击画面或按空格播放、暂停。左右方向键或暂停画面上的滚轮逐帧定位，S 截帧，点选或拖框后可附上意见。窄屏可收起「设计与意见」。WebGL 与原生回退共用控制栏和音频时钟。

在「收藏」保存正在预览的完整模板和选值。下一首歌发布含 KRC/MIDI 的基础提案后即可选「在本曲使用」，也可在此改名、更新或另存。个人偏好位于 XDG_CONFIG_HOME 下的 vibekara/preferences.md，支持 `review preferences` 读取及按摘要校验写入。

Agent 也可以直接用收藏发起首轮。读取 `review preferences` 返回的 templates，取目标 id，在首轮 manifest 中写入 favorite、目标歌曲的 clip，以及 compiler 的 python、krc、midi 和本曲偏移。发布时从收藏读取模板脚本、资源与选值，使用目标录音的歌词和时序编译。采用记录仍归本曲会话。

### 整曲时间线

将整曲媒体提供给 `clip.audio`，设置原曲 `start`、整个媒体的 `duration` 和 `fps`。对含专辑音轨的同画幅 MP4 设置 `motion: true`，浏览器用该视频同时驱动播放时钟和 MV 画面。用静图时沿用 `background` 和音频。先在媒体文件里校准 MV 与专辑的偏移。

省略 `segment_frames` 会在发布时编译整个预览范围。浏览器加载一次着色器与纹理，播放与拖动直接使用媒体时间。字体、排版等几何修改会触发重新编译。

若采用按需分段，例如 30 fps 时，`segment_frames: 240` 每段覆盖 8 秒，`entry_frame: 420` 打开在媒体第 14 秒。使用可重建的外部模板，保留背景图作为初始画面。网页按播放位置请求字幕、预取下一段，并以原曲时间记录截帧。导出采用版本时会重新编译整曲。旧的固定片段仍可使用原格式。

分段模式先交付当前时间位置的字幕。预取时，编译器会在后台为当前模板、歌词、MIDI 和选值构建整曲场景，后续区间直接从该场景导出。网页优先准备下一段，空闲时逐段补齐其余 hook；浏览器只把附近的场景留在显存。更换字体或几何参数后会使用对应的缓存，WebGL 的调色参数可以复用原有几何。
