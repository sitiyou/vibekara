# 安装 vibekara

先准备 Git 和 uv。安装脚本通过 uv 创建共享的 CPython 3.14 环境，默认位于 `~/.vibekara/.venv`。它从 GitHub Release 下载 Namioto 的预编译 wheel，从 PyPI 下载 kara-templater 的预编译 wheel，并按本机显卡选择 Namioto 的分析后端。[安装 Git](https://git-scm.com/install) · [安装 uv](https://docs.astral.sh/uv/getting-started/installation/)

两个上游子模块都固定在发布 tag 对应的提交。默认安装用子模块记录的版本匹配发布包，并保留对应的 Skill、文档和源码供查阅。

## Linux

预编译安装支持 x86-64 和 glibc 2.34 或更新版本。

```sh
git clone https://github.com/sitiyou/vibekara.git "$HOME/.vibekara/checkout"
cd "$HOME/.vibekara/checkout"
uv run --no-project --python 3.14 scripts/setup.py
```

## Windows

在 x64 Windows 的 PowerShell 中运行下列命令。

```powershell
git clone https://github.com/sitiyou/vibekara.git "$HOME\.vibekara\checkout"
Set-Location "$HOME\.vibekara\checkout"
uv run --no-project --python 3.14 scripts/setup.py
```

安装脚本打印环境解释器和 Skill 目录。默认将六个 Skill 链接到 `~/.agents/skills`，Windows 使用目录联接。其他宿主可传 `--skills-dir 路径` 或设置 `AGENT_SKILLS_DIR`。重新打开 agent 会话后，可以让 agent 使用 `vibekara` 开始制作。

已有的共享环境如果使用其他 Python 版本，先把 `.venv` 改名保留，再重新运行安装命令。

## 安装人声分离工具

人声分离使用 pymss CLI。按上游 README 安装到 `~/.vibekara/pymss/`，使用该目录下独立的 `.venv`。设置了 `VIBEKARA_HOME` 时，用其 `pymss/` 子目录。已有可用安装时，可以把现有安装目录链接到这个位置。 [pymss 安装说明](https://github.com/pymss-project/pymss#install)

## 安装位置

| 路径 | 内容 |
| --- | --- |
| `~/.vibekara/checkout/` | vibekara 和两个 submodule |
| `~/.vibekara/.venv/` | 供 vibekara 使用的 CPython 3.14 共享环境 |
| `~/.vibekara/pymss/` | 人声分离工具及其独立的 Python 环境 |
| `~/.vibekara/preferences.md`、`templates/` | 偏好与模板收藏 |
| `~/.vibekara/review/` | 本地评审会话 |
| `~/.vibekara/projects/` | 未指定目录时新建的歌曲工程 |

用户指定的歌曲目录可以原地续作。Namioto 继续沿用已有设置和模型，uv 缓存也沿用原位置。需要换目录时，设置绝对路径 `VIBEKARA_HOME`，将上面命令里的 checkout 放到对应位置，并在运行 Skill 和评审服务时沿用同一变量。

## Namioto 的分析设备

vibekara 在安装时按显卡选择 Namioto 的推理后端，适用于自动扒谱、人声对齐等任务。有 NVIDIA 显卡就选 CUDA，有其他显卡就选 WebGPU，无 GPU 时选 CPU。安装脚本会打印选中的后端。

| 后端 | 适用情况 | Wheel extra |
| --- | --- | --- |
| CPU | 使用 CPU 推理 | `[cpu]` |
| CUDA | NVIDIA 显卡且已备齐与 `onnxruntime-gpu` 版本匹配的 CUDA 和 cuDNN | `[cuda]` |
| WebGPU | 希望用 AMD、Intel 或 NVIDIA 显卡加速，且系统有可用的图形驱动。Linux 需要 Vulkan | `[webgpu]` |

每个环境选择一种后端。CUDA 和其他两种后端使用的 ONNX Runtime 包不能在同一环境中叠装。安装 GPU 后端后，在 Namioto 的「设置 → 设备」中确认所选后端可用，再用同一段音频比较 GPU 和 CPU 的推理耗时。 [Namioto 设备说明](https://github.com/sitiyou/namioto/blob/main/docs/cli.md#devices-and-models) · [CUDA 版本要求](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html#requirements) · [WebGPU 平台支持](https://onnxruntime.ai/docs/execution-providers/WebGPU-ExecutionProvider.html)

### 用预编译 wheel 手动选择后端

独立安装 Namioto 时，从发布页下载适用于当前平台的 `.whl`。用 `uv venv --python 3.14` 创建环境，安装时在 wheel 路径后加上对应的 extra。将下例中的 `PYTHON_PATH` 和 `NAMIOTO_WHEEL.whl` 换成该环境的解释器路径和下载的文件路径。[Namioto GitHub Releases](https://github.com/sitiyou/namioto/releases)

```sh
uv pip install --python "PYTHON_PATH" "NAMIOTO_WHEEL.whl[webgpu]"
```

## 制作时需要的工具

- 原唱与 MV 或伴奏需要测量音频偏移时，复用已有的 `audio-offset-finder`，或用 `uv tool install --python 3.12 audio-offset-finder` 安装到独立环境。测量和校准还需要能从 `PATH` 调用的 `ffmpeg` 和 `ffprobe`。[音频对齐步骤](docs/media.md#对齐音频零点和时长)
- 打轴使用共享环境中的 `namioto` 和 `namioto-cli`。Linux 命令在 `.venv/bin/`，Windows 在 `.venv\Scripts\`。
- 评审使用 `ffprobe`、适合歌词的字体和支持 WebGL 2 的浏览器。Linux 还需要 kara-templater wheel 所用的系统运行库，例如 FreeType、HarfBuzz、FriBidi 和 Fontconfig。发布方案时用安装脚本打印的 Python 路径填写 `compiler.python`。 [评审说明](kara-previwer/README.md#启动) · [kara-templater 运行库说明](https://github.com/sitiyou/python-kara-templater/blob/main/docs/contributing/setup.md)
- 合成视频使用带 `libplacebo` 滤镜的 FFmpeg 和可用的 Vulkan 驱动。 [Hook 渲染指南](https://github.com/sitiyou/python-kara-templater/blob/main/docs/output/hook.md)

## 升级

在安装时使用的 checkout 中先用 `git rev-parse HEAD` 记下当前提交，再运行 `git pull --ff-only --no-recurse-submodules`。拉取成功后，用 `git diff --name-only 旧提交 HEAD -- deps/namioto deps/kara-templater scripts/setup.py` 检查 submodule 的固定提交和安装脚本，将 `旧提交` 换成之前记下的提交。

如果命令列出任一路径，沿用安装时的参数重跑 setup。安装脚本会将两个 submodule 检出到 vibekara 指定的提交，并同步共享 uv 环境。无输出时，`git pull` 即完成升级。升级中断或更换显卡后，可以重跑 setup 完成同步。

## 兜底构建 kara-templater

当所需版本没有适用的 kara-templater wheel 时，可按上游说明准备构建环境，再显式启用子模块源码构建。[kara-templater 源码构建说明](https://github.com/sitiyou/python-kara-templater/blob/main/docs/contributing/setup.md)

```sh
uv run --no-project --python 3.14 scripts/setup.py --build-kara-templater
```
