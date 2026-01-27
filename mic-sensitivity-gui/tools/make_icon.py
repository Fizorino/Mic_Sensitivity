from __future__ import annotations

from pathlib import Path


def main() -> int:
    """Generate a simple .ico for the Windows executable.

    This avoids committing a binary icon. Requires Pillow (PIL), which is
    typically installed as a Matplotlib dependency.
    """
    try:
        from PIL import Image, ImageDraw
    except Exception as e:
        print(f"Pillow (PIL) not available; skipping icon generation: {e}")
        return 0

    out_path = Path(__file__).resolve().parents[1] / "assets" / "app.ico"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    margin = int(size * 0.06)
    draw.ellipse(
        (margin, margin, size - margin, size - margin),
        fill=(28, 104, 192, 255),
        outline=(255, 255, 255, 220),
        width=int(size * 0.03),
    )

    # Simple "mic" glyph: capsule + stem
    glyph_w = int(size * 0.30)
    glyph_h = int(size * 0.42)
    gx0 = (size - glyph_w) // 2
    gy0 = int(size * 0.23)
    gx1 = gx0 + glyph_w
    gy1 = gy0 + glyph_h

    draw.rounded_rectangle(
        (gx0, gy0, gx1, gy1),
        radius=int(glyph_w * 0.5),
        fill=(255, 255, 255, 240),
    )

    stem_h = int(size * 0.12)
    stem_w = int(size * 0.08)
    sx0 = (size - stem_w) // 2
    sy0 = gy1 - int(size * 0.01)
    sx1 = sx0 + stem_w
    sy1 = sy0 + stem_h
    draw.rectangle((sx0, sy0, sx1, sy1), fill=(255, 255, 255, 240))

    base_w = int(size * 0.22)
    base_h = int(size * 0.04)
    bx0 = (size - base_w) // 2
    by0 = sy1
    bx1 = bx0 + base_w
    by1 = by0 + base_h
    draw.rounded_rectangle(
        (bx0, by0, bx1, by1),
        radius=int(base_h * 0.6),
        fill=(255, 255, 255, 240),
    )

    # Save multi-size ICO
    img.save(out_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Wrote icon: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
