"""
Create MedBridge logo variants: black text (for light backgrounds) and white text (for dark backgrounds).
Removes white background so container color shows through.
"""
import urllib.request
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("Install: pip install Pillow numpy")
    raise

URL = "https://www.medbridge.com/files/img/brand/medbridge-logo.png"
OUT_DIR = Path(__file__).resolve().parent.parent / "assets"
OUT_DIR.mkdir(exist_ok=True)


def download_logo() -> Image.Image:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"})
    with urllib.request.urlopen(req) as resp:
        return Image.open(resp).convert("RGBA")


def remove_white_background(im: Image.Image, threshold: int = 250) -> Image.Image:
    """Make white/near-white pixels transparent."""
    arr = np.array(im)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    # Pixels that are white or near-white (high RGB)
    white_mask = (r > threshold) & (g > threshold) & (b > threshold)
    arr[white_mask, 3] = 0  # Set alpha to 0
    return Image.fromarray(arr)


def create_black_version(im: Image.Image) -> Image.Image:
    """Transparent background, keep original colors (black text, yellow arches)."""
    return remove_white_background(im.copy())


def create_white_version(im: Image.Image) -> Image.Image:
    """Transparent background, black and dark pixels become white (for dark backgrounds)."""
    arr = np.array(remove_white_background(im.copy()))
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    # Non-transparent pixels: replace black/dark with white; keep lighter colors (yellow) as white too
    visible = a > 0
    # Any colored pixel becomes white
    arr[visible, 0] = 255
    arr[visible, 1] = 255
    arr[visible, 2] = 255
    return Image.fromarray(arr)


def main():
    print("Downloading logo from MedBridge CDN...")
    im = download_logo()
    print("Creating logo-black.png (for light backgrounds)...")
    create_black_version(im).save(OUT_DIR / "logo-black.png")
    print("Creating logo-white.png (for dark backgrounds)...")
    create_white_version(im).save(OUT_DIR / "logo-white.png")
    print(f"Saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
