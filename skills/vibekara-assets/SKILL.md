---
name: vibekara-assets
description: 确认歌曲录音版本，定位或补齐制作 karaoke 所需的音源、歌词、画面与伴奏。
---

先检查用户给的文件或链接。若安装 nicokara-local-media，按其约定检查个人素材库。记录曲名、歌手、专辑/现场/剪辑版本、时长。整轨 CUE 核对 FILE、TRACK 和 INDEX 01，按 CD 每秒 75 帧换算本轨起点及下一轨起点，用 FFmpeg 切出无损音源。最后一轨取至镜像结尾。用 ffprobe 查时长并听首尾。

缺项再检索。用 karaoke-studio 的歌词搜索选择 QQ 音乐、酷狗、网易云、LRCLIB 候选，日语读音可借 UtaTen 核对。也可用 LRCLIB 的 /api/search 按 track_name 和 artist_name 检索 plainLyrics/syncedLyrics。文本、LRC 或歌词本须核对实际录音的段落、反复和读音。用 YouTube、Bilibili 定位用户指定的视频版本，核对前奏与剪辑点。一图流优先专辑 cover。伴奏核对速度、段落、起止与原唱；需要人声分离时说明来源让用户决定。

明确匹配的材料直接补齐。多个候选影响成片时列出具体差异请用户选。缺文件时说清需要哪一项、可提供的格式和原因。把选定文件、来源、时间零点和任何补偿写入歌曲 production.md，交给打轴阶段。
