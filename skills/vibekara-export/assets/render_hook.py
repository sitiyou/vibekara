"""Render a saved Namioto project with a kara-templater recipe."""

import argparse
from pathlib import Path

from import_nto import load_nto
from template import build


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="saved Namioto .nto project")
    parser.add_argument("output", type=Path, help="destination .hook file")
    parser.add_argument("--script", type=Path, help="trusted template script")
    parser.add_argument("--template", help="recipe ID for --script")
    parser.add_argument("--set", dest="parameters", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--offset-ms", type=int, default=-100)
    parser.add_argument("--harmony-tracks", default="", help="comma-separated MIDI channels for harmony")
    args = parser.parse_args()
    if not 1 <= args.fps <= 240:
        parser.error("--fps must be between 1 and 240")
    if bool(args.script) != bool(args.template):
        parser.error("--script and --template must be supplied together")
    if args.parameters and not args.script:
        parser.error("--set requires a template script with parameters")

    parameters = {}
    for item in args.parameters:
        key, separator, value = item.partition("=")
        if not key or not separator:
            parser.error("--set expects KEY=VALUE")
        parameters[key] = value

    script = args.script or Path(__file__).resolve().with_name("template.py")
    if args.output.resolve() in (args.project.resolve(), script.resolve()):
        parser.error("the output must be separate from the project and template")
    try:
        timing = {"offset_ms": args.offset_ms, "harmony_tracks": args.harmony_tracks}
        if args.script:
            from kara_previwer.templates import load_templates
            from kara_previwer.timing import load_project_song

            recipe = load_templates([script]).get(args.template)
            if not recipe.semantic or "hook" not in recipe.formats:
                raise ValueError("the template must accept structured lyrics and support Hook output")
            scene = recipe.build(load_project_song(args.project, **timing), recipe.resolve(parameters))
        else:
            scene = build(load_nto(args.project, **timing))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        scene.export(args.output, fps=args.fps)
    except (OSError, TypeError, ValueError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
