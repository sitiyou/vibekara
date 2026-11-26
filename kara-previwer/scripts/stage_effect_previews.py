"""Copy Kara Templater's rendered component cards into the review application."""

import argparse
import json
from pathlib import Path

ALIASES = {
    "band-brighten": "sweep-brighten",
    "band-follow-before": "sweep-follow-before",
    "band-follow-after": "sweep-follow-after",
    "band-gradient": "sweep-gradient",
    "transition-stagger": "entry-char-fade",
    "tween-scale": "tween",
    "echo": "lyric-echo",
}
EFFECT_GROUPS = {
    "entry", "exit", "highlight", "decoration",
}
EXTRA_CARDS = {
    "glow", "soft-front", "stroke-flash", "lyric-gradient", "extrusion",
    "bars-cue", "volume-cue", "signal-cue", "text-cue",
    "slide", "jump", "scale-pulse", "drift-out", "fade-in", "fade-out", "sparkle", "petal",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", type=Path, help="Kara Templater docs staging directory")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = root / "kara_previwer" / "effect-previews"
    output.mkdir(exist_ok=True)
    cards = {card["id"]: card for card in json.loads((args.stage / "components.json").read_text())}
    ids = {
        card["id"] for card in cards.values()
        if card["group"] in EFFECT_GROUPS or card["id"] in EXTRA_CARDS
    } | ALIASES.keys()
    resources = {}
    for component in sorted(ids):
        card = cards[ALIASES.get(component, component)]
        public = args.stage / "public"
        folder = public / "previews" / card["gallery"] if "gallery" in card else public / "component-previews" / card["id"]
        media: dict[str, str | float] = {}
        for field, extension in (("poster", "jpg"), ("src", "mp4")):
            source = folder / f"card.{extension}"
            if source.is_file():
                name = f"{card['id']}.{extension}"
                (output / name).write_bytes(source.read_bytes())
                media[field] = "effect-previews/" + name
        if media:
            if "src" in media and "gallery" not in card:
                media["startAt"] = round(max(0, card.get("still", 1.75) - card.get("start", 0)), 3)
            resources[component] = media
    keep = {Path(path).name for media in resources.values() for path in media.values() if isinstance(path, str)}
    for path in output.iterdir():
        if path.suffix in {".jpg", ".mp4"} and path.name not in keep:
            path.unlink()
    (root / "frontend" / "effect-preview-index.json").write_text(
        json.dumps(resources, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"{len(resources)} effect previews")


if __name__ == "__main__":
    main()
