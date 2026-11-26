# 安装 vibekara

先准备 [Git](https://git-scm.com/install)、[uv](https://docs.astral.sh/uv/getting-started/installation/) 和 C++17 工具链。uv 会在 `~/.vibekara/.venv` 创建共享 Python 环境。安装脚本按 Namioto 的 `pyproject.toml` 从 submodule 源码安装 CPU 版本，并从 PyPI 安装与 kara-templater submodule 对应的 wheel。两个 submodule 也提供对应版本的文档、示例和 Skill。

## Linux

安装发行版的 C++ 编译工具，例如 Debian 或 Ubuntu 的 `build-essential`。默认安装需要有适用于本机架构、Python 和 glibc 的 kara-templater wheel。[已发布的 wheel](https://pypi.org/project/kara-templater/#files)

```sh
git clone https://github.com/sitiyou/vibekara.git "$HOME/.vibekara/checkout"
cd "$HOME/.vibekara/checkout"
uv run --no-project --python '>=3.11' scripts/setup.py
```

## Windows

安装 [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio)，选择「使用 C++ 的桌面开发」，然后在 x64 Developer PowerShell 中运行下列命令。[Namioto 源码构建要求](https://github.com/sitiyou/namioto/blob/main/docs/development.md#source-setup)

```powershell
git clone https://github.com/sitiyou/vibekara.git "$HOME\.vibekara\checkout"
Set-Location "$HOME\.vibekara\checkout"
uv run --no-project --python '>=3.11' scripts/setup.py
```

安装脚本打印环境解释器和 Skill 目录。默认将六个 Skill 链接到 `~/.agents/skills`，Windows 使用目录联接。其他宿主可传 `--skills-dir 路径` 或设置 `AGENT_SKILLS_DIR`。重新打开 agent 会话后，可以让 agent 使用 `vibekara` 开始制作。

## 安装位置

| 路径 | 内容 |
| --- | --- |
| `~/.vibekara/checkout/` | vibekara 和两个 submodule |
| `~/.vibekara/.venv/` | 三个仓库共用的 Python 环境 |
| `~/.vibekara/preferences.md`、`templates/` | 偏好与模板收藏 |
| `~/.vibekara/review/` | 本地评审会话 |
| `~/.vibekara/projects/` | 未指定目录时新建的歌曲工程 |

用户指定的歌曲目录可以原地续作。Namioto 继续沿用已有设置和模型，uv 缓存也沿用原位置。需要换目录时，设置绝对路径 `VIBEKARA_HOME`，将上面命令里的 checkout 放到对应位置，并在运行 Skill 和评审服务时沿用同一变量。

## 制作时需要的工具

- 打轴使用共享环境中的 `namioto` 和 `namioto-cli`。Linux 命令在 `.venv/bin/`，Windows 在 `.venv\Scripts\`。
- 评审使用 `ffprobe`、适合歌词的字体和支持 WebGL 2 的浏览器。Linux 还需要 kara-templater wheel 所用的系统运行库，例如 FreeType、HarfBuzz、FriBidi 和 Fontconfig。发布方案时用安装脚本打印的 Python 路径填写 `compiler.python`。 [评审说明](kara-previwer/README.md#启动) · [kara-templater 运行库说明](https://github.com/sitiyou/python-kara-templater/blob/main/docs/contributing/setup.md)
- 合成视频使用带 `libplacebo` 滤镜的 FFmpeg 和可用的 Vulkan 驱动。 [Hook 渲染指南](https://github.com/sitiyou/python-kara-templater/blob/main/docs/output/hook.md)

## 没有可用的 wheel

先核对 uv 报出的平台、架构和 Python 版本。已准备好 kara-templater 所需的 C++、Rust 和原生库时，可以显式改用其固定的 submodule 源码安装。 [kara-templater 源码构建说明](https://github.com/sitiyou/python-kara-templater/blob/main/docs/contributing/setup.md)

```sh
uv run --no-project --python '>=3.11' scripts/setup.py --build-kara-templater
```

## 更新与迁移

在安装时使用的 checkout 中运行 `git pull --ff-only`，再执行同一条 setup 命令。需要更换 `.venv` 的 Python 时，可以先将 `.venv` 改名备份，再重跑 setup。若旧安装的同名 Skill 链接指向另一份 checkout，先核对这些链接的目标，再移走它们并重跑 setup。

旧安装的偏好和收藏通常在 `~/.config/vibekara/`，设置过 `XDG_CONFIG_HOME` 时在其 `vibekara/` 子目录。可以把 `preferences.md` 和 `templates/` 一并复制到新目录。若新目录已有偏好，先合并内容。旧评审可继续用 `--root ~/.local/state/kara-previwer` 打开。需要迁移时，停止旧评审服务，再把整个旧评审目录复制到 `~/.vibekara/review/`。换过解释器的采用快照可通过 `rebuild_hook.py --python` 指定新路径。 [评审恢复与构建](kara-previwer/README.md#事件恢复与构建)
