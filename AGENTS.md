# vibekara

vibekara is an agent skill for producing karaoke. The workflow lives in `skills/` and agents select the relevant stage based on the requested deliverable.

Keep integration instructions here. Use Namioto for recording-based timing and revisions, and use kara-templater to author and render templates. The handoff from timing to review and export is the saved `.nto`. Keep matched MIDI/KRC interchange in Namioto's standalone documentation.

Implement executable tasks as standalone Python scripts that run directly from the checkout. Give each script a focused task and a clear input and output. Share implementation through ordinary Python modules where useful. Do not package vibekara or its helpers as a Python distribution, expose installed commands, or route tasks through a shared command-line dispatcher.

The browser review interface is a skill helper. Start its local server from the checkout and expose session operations through individual scripts. Document these script paths in the skills and guides.

related development repo: ~/dev/kara-templater ~/dev/namioto
