from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    assets = root / "assets"
    assets.mkdir(exist_ok=True)

    scale = 4
    size = 256 * scale
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gradient = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gradient_draw = ImageDraw.Draw(gradient)
    for y in range(size):
        ratio = (y / scale - 14) / 228
        ratio = max(0.0, min(1.0, ratio))
        left = (124, 77, 255)
        right = (255, 64, 87)
        colour = tuple(round(a + (b - a) * ratio) for a, b in zip(left, right)) + (255,)
        gradient_draw.line((0, y, size, y), fill=colour)

    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(
        (14 * scale, 14 * scale, 242 * scale, 242 * scale),
        radius=58 * scale,
        fill=255,
    )
    image.paste(gradient, (0, 0), mask)
    draw = ImageDraw.Draw(image)

    bubble = [
        (34 * scale, 66 * scale),
        (222 * scale, 186 * scale),
    ]
    draw.rounded_rectangle(bubble, radius=22 * scale, fill=(17, 21, 33, 255))
    draw.polygon(
        [(100 * scale, 181 * scale), (139 * scale, 181 * scale), (102 * scale, 216 * scale)],
        fill=(17, 21, 33, 255),
    )
    for x, colour in (
        (77, (145, 70, 255, 255)),
        (128, (245, 247, 251, 255)),
        (179, (255, 64, 87, 255)),
    ):
        draw.ellipse(
            ((x - 12) * scale, 114 * scale, (x + 12) * scale, 138 * scale),
            fill=colour,
        )

    image = image.resize((256, 256), Image.Resampling.LANCZOS)
    image.save(assets / "icon.png", optimize=True)
    image.save(
        assets / "app.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Icones gerados em: {assets}")


if __name__ == "__main__":
    main()
