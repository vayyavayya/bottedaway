"""Sharpen — the scan enhancement pipeline (our answer to CamScanner's Omnifix).

One tap, one photo in, one clean page out. The stages, in order:

    detect page edges -> perspective-correct -> deskew -> flatten lighting
    -> white-balance -> denoise -> sharpen -> pick a rendering mode

Every stage is defensive: if the page detector can't find four corners it keeps
the whole frame, if OpenCV isn't installed it falls back to a Pillow-only path
that still fixes contrast and sharpness. A bad photo comes out worse-looking
than a good one — it never comes out empty.

Modes:
    auto    inspect the image and choose magic / colour / photo
    magic   flatten lighting, whiten the paper, keep ink and stamps in colour
    color   gentle: perspective + lighting only, true colours
    gray    magic in greyscale
    bw      binarised, smallest files, best for plain text and faxes
    photo   perspective correction only — for photographs and artwork
    none    no processing at all
"""

from __future__ import annotations

import io
import logging
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("docbox.enhance")

MODES = ("auto", "magic", "color", "gray", "bw", "photo", "none")

# Below this variance-of-Laplacian a scan is soft enough to be worth a warning.
BLUR_WARN = 90.0
# A detected page must cover at least this share of the frame to be trusted.
MIN_PAGE_AREA = 0.12


@dataclass
class ScanReport:
    mode: str = "auto"
    applied: str = "none"
    cropped: bool = False
    corners: list[tuple[int, int]] | None = None
    deskew_deg: float = 0.0
    rotated_deg: int = 0
    blur_score: float = 0.0
    width: int = 0
    height: int = 0
    engine: str = "none"
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "applied": self.applied,
            "cropped": self.cropped,
            "deskew_deg": round(self.deskew_deg, 2),
            "rotated_deg": self.rotated_deg,
            "blur_score": round(self.blur_score, 1),
            "size": [self.width, self.height],
            "engine": self.engine,
            "warnings": self.warnings,
        }


def _cv2():
    try:
        import cv2  # type: ignore

        return cv2
    except ImportError:
        return None


def _np():
    try:
        import numpy as np  # type: ignore

        return np
    except ImportError:
        return None


def available() -> dict:
    return {"opencv": _cv2() is not None, "numpy": _np() is not None}


# ------------------------------------------------------------------ decoding


def _open_pil(data: bytes):
    from PIL import Image, ImageOps

    try:  # iPhone photos
        import pillow_heif  # type: ignore

        pillow_heif.register_heif_opener()
    except Exception:
        pass

    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)  # honour the phone's orientation flag
    return img.convert("RGB")


def _to_cv(pil_img):
    cv2, np = _cv2(), _np()
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def _to_pil(cv_img):
    from PIL import Image

    cv2, np = _cv2(), _np()
    if cv_img.ndim == 2:
        return Image.fromarray(cv_img)
    return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))


# ------------------------------------------------------- page edge detection


def _order_corners(pts):
    """Clockwise from top-left, which is what the warp expects."""
    np = _np()
    pts = pts.reshape(4, 2).astype("float32")
    ordered = np.zeros((4, 2), dtype="float32")
    total = pts.sum(axis=1)
    ordered[0] = pts[np.argmin(total)]        # top-left  = smallest x+y
    ordered[2] = pts[np.argmax(total)]        # bottom-right
    diff = np.diff(pts, axis=1)
    ordered[1] = pts[np.argmin(diff)]         # top-right = smallest y-x
    ordered[3] = pts[np.argmax(diff)]
    return ordered


def detect_page(image):
    """Find the sheet of paper. Returns 4 corners in original coordinates, or None."""
    cv2, np = _cv2(), _np()
    if cv2 is None:
        return None

    height, width = image.shape[:2]
    scale = 900.0 / max(height, width)
    small = cv2.resize(image, None, fx=scale, fy=scale) if scale < 1 else image.copy()
    inv = (1 / scale) if scale < 1 else 1.0

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 60, 60)  # smooth paper, keep the edge

    candidates = []

    # Pass 1: gradient edges. Works when the page sits on a contrasting surface.
    median = float(np.median(gray))
    low = int(max(0, 0.66 * median))
    high = int(min(255, 1.33 * median))
    edges = cv2.Canny(gray, low, high)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=1)
    candidates.append(edges)

    # Pass 2: bright-region mask. Works for a white page on a light desk, where
    # the gradient is weak but the page is still the brightest large blob.
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    candidates.append(mask)

    # Pass 3: the same gradient hunt on a locally equalised image. A hand or
    # window shadow falling across the page kills the contrast along one edge,
    # and passes 1 and 2 then lock onto the shadow's border instead of the
    # paper's. CLAHE restores that edge before we look for it.
    equalized = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)
    equalized = cv2.bilateralFilter(equalized, 9, 60, 60)
    shadow_safe = cv2.Canny(equalized, 30, 90)
    shadow_safe = cv2.morphologyEx(
        shadow_safe, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2
    )
    candidates.append(shadow_safe)

    frame_area = small.shape[0] * small.shape[1]
    support_map = cv2.dilate(
        cv2.bitwise_or(edges, shadow_safe), np.ones((5, 5), np.uint8), iterations=1
    )

    best, best_score = None, 0.0
    for candidate in candidates:
        contours, _ = cv2.findContours(candidate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:6]:
            area = cv2.contourArea(contour)
            if area < frame_area * MIN_PAGE_AREA or area > frame_area * 0.985:
                continue
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            if len(approx) != 4 or not cv2.isContourConvex(approx):
                continue
            quad = approx.reshape(4, 2)
            if _too_skewed(quad):
                continue
            score = _score_quad(gray, support_map, quad, area, frame_area)
            if score > best_score:
                best, best_score = quad, score

    # A weak best guess is worse than no crop at all: a wrong crop loses content.
    if best is None or best_score < MIN_PAGE_SCORE:
        return None
    return (_order_corners(best) * inv).astype("float32")


# A quad has to look like a page, not just be large.
MIN_PAGE_SCORE = 0.42


def _score_quad(gray, support_map, quad, area: float, frame_area: float) -> float:
    """How page-like is this quadrilateral?

    Three signals, because area alone happily picks a rectangle drawn across the
    whole desk:
      * edge support — does the outline actually sit on detected edges?
      * contrast     — is the inside a different tone from the surrounding ring?
      * size         — bigger is mildly better, as a tie-breaker only.
    """
    cv2, np = _cv2(), _np()
    polygon = quad.astype(np.int32).reshape(-1, 1, 2)

    inside = np.zeros(gray.shape, np.uint8)
    cv2.fillPoly(inside, [polygon], 255)
    ring = cv2.subtract(cv2.dilate(inside, np.ones((25, 25), np.uint8)), inside)

    inside_pixels = gray[inside > 0]
    ring_pixels = gray[ring > 0]
    if inside_pixels.size < 50:
        return 0.0
    contrast = 0.0
    if ring_pixels.size >= 50:
        contrast = abs(float(inside_pixels.mean()) - float(ring_pixels.mean())) / 255.0

    outline = np.zeros(gray.shape, np.uint8)
    cv2.polylines(outline, [polygon], True, 255, 3)
    outline_pixels = outline > 0
    support = 0.0
    if outline_pixels.sum():
        support = float((support_map[outline_pixels] > 0).mean())

    return (
        0.55 * support
        + 0.30 * min(contrast * 3.0, 1.0)
        + 0.15 * (area / frame_area)
    )


def _too_skewed(pts) -> bool:
    """Reject quadrilaterals whose corners aren't roughly right angles."""
    np = _np()
    for i in range(4):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % 4]
        v1, v2 = a - b, c - b
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 == 0 or n2 == 0:
            return True
        cosine = float(np.dot(v1, v2) / (n1 * n2))
        angle = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        if not 55 <= angle <= 125:
            return True
    return False


# Page shapes we snap to when the estimate lands close enough (width/height).
STANDARD_ASPECTS = (
    0.7071,   # A-series portrait (A4, A5)
    0.7727,   # US Letter portrait
    0.6071,   # US Legal portrait
    1.5859,   # ID-1 card (bank card, driving licence)
)
SNAP_TOLERANCE = 0.035


def estimate_aspect(corners, width: int, height: int) -> float | None:
    """Recover the page's true width/height from its projected quadrilateral.

    Edge lengths alone are wrong under perspective: the far edge of a tilted
    page is shorter, so a naive warp squeezes the result. This solves for the
    camera's focal length from the quad and returns the real ratio.

    Standard result from projective geometry; degenerate (near-parallel) cases
    return None and the caller falls back to edge lengths.
    """
    np = _np()
    try:
        tl, tr, br, bl = (np.array([c[0], c[1], 1.0], dtype="float64") for c in corners)
        u0, v0 = width / 2.0, height / 2.0

        denom2 = np.dot(np.cross(tr, br), bl)
        denom3 = np.dot(np.cross(bl, br), tr)
        if abs(denom2) < 1e-9 or abs(denom3) < 1e-9:
            return None
        k2 = np.dot(np.cross(tl, br), bl) / denom2
        k3 = np.dot(np.cross(tl, br), tr) / denom3

        n2 = k2 * tr - tl
        n3 = k3 * bl - tl
        n21, n22, n23 = n2
        n31, n32, n33 = n3
        if abs(n23) < 1e-9 or abs(n33) < 1e-9:
            # Both vanishing points at infinity: the shot is essentially
            # straight-on, so edge lengths are already correct.
            return None

        f_squared = -(1.0 / (n23 * n33)) * (
            (n21 * n31 - (n21 * n33 + n23 * n31) * u0 + n23 * n33 * u0 * u0)
            + (n22 * n32 - (n22 * n33 + n23 * n32) * v0 + n23 * n33 * v0 * v0)
        )
        if f_squared <= 0:
            return None
        focal = math.sqrt(f_squared)

        camera = np.array([[focal, 0, u0], [0, focal, v0], [0, 0, 1.0]])
        inverse = np.linalg.inv(camera)
        metric = inverse.T @ inverse
        num = float(n2 @ metric @ n2)
        den = float(n3 @ metric @ n3)
        if den <= 0 or num <= 0:
            return None
        aspect = math.sqrt(num / den)
        return aspect if 0.15 < aspect < 6.0 else None
    except Exception:
        return None


def snap_aspect(aspect: float) -> float:
    """Nudge a near-standard ratio onto the real page size."""
    for standard in STANDARD_ASPECTS:
        for candidate in (standard, 1 / standard):
            if abs(aspect - candidate) / candidate <= SNAP_TOLERANCE:
                return candidate
    return aspect


def four_point_warp(image, corners):
    """Flatten the quadrilateral into a proper rectangle at full resolution."""
    cv2, np = _cv2(), _np()
    tl, tr, br, bl = corners
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    width, height = max(width, 16), max(height, 16)

    aspect = estimate_aspect(corners, image.shape[1], image.shape[0])
    if aspect:
        aspect = snap_aspect(aspect)
        # Keep the larger dimension's resolution and derive the other one, so
        # the page stops being squeezed without inventing detail.
        if aspect >= 1:
            width = max(int(round(height * aspect)), 16)
        else:
            height = max(int(round(width / aspect)), 16)
    target = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32"
    )
    matrix = cv2.getPerspectiveTransform(corners, target)
    return cv2.warpPerspective(image, matrix, (width, height), flags=cv2.INTER_CUBIC)


# ------------------------------------------------------------------- deskew


def deskew(image, limit: float = 12.0) -> tuple:
    """Straighten residual rotation using the dominant text angle."""
    cv2, np = _cv2(), _np()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    inverted = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    # Smear characters into lines so the angle is the text baseline, not a letter.
    smeared = cv2.morphologyEx(inverted, cv2.MORPH_CLOSE, np.ones((3, 25), np.uint8))
    coords = cv2.findNonZero(smeared)
    if coords is None or len(coords) < 200:
        return image, 0.0

    angle = cv2.minAreaRect(coords)[-1]
    if angle > 45:
        angle -= 90
    if abs(angle) < 0.25 or abs(angle) > limit:
        return image, 0.0

    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    rotated = cv2.warpAffine(
        image, matrix, (width, height),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated, float(angle)


def auto_orient(image) -> tuple:
    """Use tesseract's orientation detection to fix a sideways page."""
    cv2 = _cv2()
    if not shutil.which("tesseract"):
        return image, 0
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "osd.png"
        cv2.imwrite(str(path), image)
        try:
            out = subprocess.run(
                ["tesseract", str(path), "stdout", "--psm", "0"],
                capture_output=True, timeout=40, check=False,
            ).stdout.decode("utf-8", "replace")
        except (subprocess.TimeoutExpired, OSError):
            return image, 0

    degrees = 0
    for line in out.splitlines():
        if line.startswith("Rotate:"):
            try:
                degrees = int(line.split(":")[1].strip())
            except ValueError:
                degrees = 0
    if degrees == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE), 90
    if degrees == 180:
        return cv2.rotate(image, cv2.ROTATE_180), 180
    if degrees == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE), 270
    return image, 0


# ------------------------------------------------------------ tone and colour


def flatten_lighting(image):
    """Remove shadows and the camera's uneven illumination.

    Estimate the background (what the paper would look like with no ink) by
    heavily blurring, then divide the image by it. Gradients vanish, ink stays.
    """
    cv2, np = _cv2(), _np()
    planes = cv2.split(image)
    out = []
    for plane in planes:
        dilated = cv2.dilate(plane, np.ones((7, 7), np.uint8))
        background = cv2.medianBlur(dilated, 21)
        normalized = cv2.divide(plane, background, scale=255)
        out.append(normalized)
    return cv2.merge(out)


def white_balance(image):
    """Grey-world balance, so yellow indoor light stops tinting the paper."""
    cv2, np = _cv2(), _np()
    result = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
    for channel in (1, 2):  # a and b
        result[:, :, channel] -= (result[:, :, channel].mean() - 128) * (
            result[:, :, 0].mean() / 255.0
        ) * 1.1
    return cv2.cvtColor(np.clip(result, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def stretch_contrast(image, low_pct: float = 1.0, high_pct: float = 99.5):
    """Push the paper to true white and the ink to true black."""
    np = _np()
    # Percentiles over 12M pixels are slow and every 16th pixel gives the same
    # answer to well under one grey level.
    sample = image[::4, ::4]
    gray = sample if sample.ndim == 2 else sample.mean(axis=2)
    lo = float(np.percentile(gray, low_pct))
    hi = float(np.percentile(gray, high_pct))
    if hi - lo < 20:
        return image
    scaled = (image.astype(np.float32) - lo) * (255.0 / (hi - lo))
    return np.clip(scaled, 0, 255).astype(np.uint8)


def denoise(image):
    """Edge-preserving denoise.

    Non-local means gives a slightly cleaner background but costs ~3.7s on a
    12MP photo and visibly softens small text; a bilateral filter is ~30x
    faster and measured *sharper* on the same page. For a document scanner
    that is the right trade.
    """
    cv2 = _cv2()
    return cv2.bilateralFilter(image, 7, 50, 50)


def unsharp(image, amount: float = 0.7, radius: int = 3):
    cv2 = _cv2()
    blurred = cv2.GaussianBlur(image, (0, 0), radius)
    return cv2.addWeighted(image, 1 + amount, blurred, -amount, 0)


def binarize(image):
    """Adaptive threshold — beats a global cut on unevenly lit paper."""
    cv2 = _cv2()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    gray = denoise(gray)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12
    )
    # Drop salt noise that survives thresholding.
    return cv2.medianBlur(binary, 3)


# ----------------------------------------------------------------- analysis


def blur_score(image) -> float:
    cv2 = _cv2()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def looks_like_paper(image) -> bool:
    """Document or photograph? Paper is bright, low-saturation and bimodal."""
    cv2, np = _cv2(), _np()
    small = cv2.resize(image, (240, 240))
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    saturation = float(hsv[:, :, 1].mean())
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    bright_share = float((gray > 170).mean())
    return saturation < 60 and bright_share > 0.35


# --------------------------------------------------------------- main entry


def enhance(data: bytes, mode: str = "auto", crop: bool = True,
            orient: bool = False, corners: list | None = None) -> tuple[bytes, ScanReport]:
    """Return (JPEG/PNG bytes, report). Never raises on a decodable image."""
    mode = mode if mode in MODES else "auto"
    report = ScanReport(mode=mode)

    cv2, np = _cv2(), _np()
    if cv2 is None or np is None:
        return _enhance_pillow(data, mode, report)

    try:
        pil = _open_pil(data)
    except Exception as exc:
        report.warnings.append(f"could not read image: {exc}")
        return data, report

    image = _to_cv(pil)
    report.engine = "opencv"

    if mode == "none":
        report.applied = "none"
        report.height, report.width = image.shape[:2]
        report.blur_score = blur_score(image)
        return _encode(image, "none"), report

    # 1. crop to the page
    if crop:
        found = None
        if corners:
            found = np.array(corners, dtype="float32")
        else:
            try:
                found = detect_page(image)
            except Exception as exc:
                log.debug("page detection failed: %s", exc)
        if found is not None and len(found) == 4:
            try:
                image = four_point_warp(image, found)
                report.cropped = True
                report.corners = [(int(x), int(y)) for x, y in found]
            except Exception as exc:
                log.debug("warp failed: %s", exc)
                report.warnings.append("edge detection found a page but the warp failed")
        else:
            report.warnings.append("no page edges found — kept the full frame")

    # 2. straighten
    if mode != "photo":
        try:
            image, angle = deskew(image)
            report.deskew_deg = angle
        except Exception as exc:
            log.debug("deskew failed: %s", exc)

    if orient:
        try:
            image, degrees = auto_orient(image)
            report.rotated_deg = degrees
        except Exception as exc:
            log.debug("orientation failed: %s", exc)

    # 3. decide what this actually is
    effective = mode
    if mode == "auto":
        effective = "magic" if looks_like_paper(image) else "photo"

    # 4. render
    try:
        image = _render(image, effective)
    except Exception as exc:
        log.warning("enhancement failed, keeping the corrected image: %s", exc)
        report.warnings.append(f"enhancement skipped: {exc}")
        effective = "photo"

    report.applied = effective
    report.blur_score = blur_score(image)
    if report.blur_score < BLUR_WARN:
        report.warnings.append("looks soft — hold still or move closer for the next one")
    report.height, report.width = image.shape[:2]
    return _encode(image, effective), report


def _render(image, effective: str):
    cv2 = _cv2()
    if effective == "photo":
        return image
    if effective == "bw":
        return binarize(flatten_lighting(image))
    if effective == "gray":
        flat = stretch_contrast(flatten_lighting(image))
        gray = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)
        return unsharp(gray, amount=0.6)
    if effective == "color":
        return unsharp(white_balance(flatten_lighting(image)), amount=0.4)
    # magic: the default one-tap look — white paper, crisp dark ink, colour kept
    flat = flatten_lighting(image)
    flat = white_balance(flat)
    flat = stretch_contrast(flat, 2.0, 99.0)
    flat = denoise(flat)
    return unsharp(flat, amount=0.8)


def _encode(image, effective: str) -> bytes:
    """PNG for bilevel (tiny and lossless), JPEG otherwise."""
    cv2 = _cv2()
    if effective == "bw":
        ok, buf = cv2.imencode(".png", image)
    else:
        ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 94])
    if not ok:
        raise RuntimeError("could not encode the enhanced image")
    return buf.tobytes()


# ------------------------------------------------------- Pillow-only fallback


def _enhance_pillow(data: bytes, mode: str, report: ScanReport) -> tuple[bytes, ScanReport]:
    """No OpenCV: no dewarping, but contrast and sharpness still improve a lot."""
    from PIL import ImageEnhance, ImageFilter, ImageOps

    report.engine = "pillow"
    report.warnings.append("OpenCV not installed — no edge detection or dewarping")
    try:
        img = _open_pil(data)
    except Exception as exc:
        report.warnings.append(f"could not read image: {exc}")
        return data, report

    if mode == "none":
        report.applied = "none"
    else:
        img = ImageOps.autocontrast(img, cutoff=(1, 2))
        if mode in {"gray", "bw"}:
            img = ImageOps.grayscale(img)
            if mode == "bw":
                img = img.point(lambda p: 255 if p > 150 else 0, mode="1")
        if mode != "bw":
            img = ImageEnhance.Sharpness(img).enhance(1.6)
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=110, threshold=3))
        report.applied = mode if mode != "auto" else "magic"

    report.width, report.height = img.size
    buffer = io.BytesIO()
    if img.mode == "1":
        img.save(buffer, "PNG")
    else:
        img.convert("RGB").save(buffer, "JPEG", quality=94)
    return buffer.getvalue(), report
