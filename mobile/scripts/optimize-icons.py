from pathlib import Path

from PIL import Image


ASSET_DIR = Path("/home/ubuntu/aether-mobile-offline/assets/images")
TARGETS = [
    "icon.png",
    "splash-icon.png",
    "favicon.png",
    "android-icon-foreground.png",
]


def optimize(path: Path) -> None:
    with Image.open(path) as source:
        image = source.convert("RGBA")
        image.thumbnail((512, 512), Image.Resampling.LANCZOS)
        palette = image.quantize(colors=192, method=Image.Quantize.FASTOCTREE)
        palette.save(path, "PNG", optimize=True, compress_level=9)


for filename in TARGETS:
    optimize(ASSET_DIR / filename)
