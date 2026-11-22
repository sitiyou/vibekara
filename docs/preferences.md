# 偏好与模板收藏

在评审页的「我的模板」中保存当前模板和选值。制作下一首歌时，从收藏中选取模板，在新歌的歌词和音轨上预览。收藏需要可重建的模板源码；只有渲染后的 hook 时，请先找回对应模板。

长期偏好保存在 `$XDG_CONFIG_HOME/vibekara/preferences.md`，默认位于 `~/.config/vibekara/preferences.md`。用简短的 Markdown 条目记录适用条件和选择，例如「合唱段优先让两条声部使用不同的扫色」。只对当前歌曲生效的要求写入该曲的制作记录。

`preferences.md` 上限为 **4096 个 UTF-8 字节**，包括标题、换行和收藏索引。收藏的模板源码、资源和选值另存于配置目录的 `templates/` 中。通过评审页管理收藏时，网页会维护对应的 Markdown 链接。

在命令行运行 `review preferences` 可以查看偏好和当前内容摘要。要保存编辑后的文件，运行 `review preferences --write FILE --digest DIGEST`，其中 `DIGEST` 为读取时返回的摘要。遇到并发修改时重新读取并合并；遇到超限时先精简重复或已撤销的条目。
