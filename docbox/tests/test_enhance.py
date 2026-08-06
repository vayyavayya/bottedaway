"""Scan enhancement.

The synthetic pages here are projected through a real pinhole camera, so the
page's true corner positions and its true 1:sqrt(2) aspect are known exactly and
the pipeline can be measured against them instead of eyeballed.
"""

from __future__ import annotations

import io
import math

import pytest

from app import enhance

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

A4_ASPECT = 0.2100 / 0.2970  # 0.7071
CANVAS = (1600, 2200)  # width, height


def _rotation(ax: float, ay: float, az: float):
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return rz @ ry @ rx


def project_page(rx=0.30, ry=-0.20, rz=0.05, dist=0.30, focal=1400.0):
    """Corners of an A4 sheet as a real camera would see it (tl, tr, br, bl)."""
    width, height = CANVAS
    w_m, h_m = 0.210, 0.297
    corners = np.array([
        [-w_m / 2, -h_m / 2, 0], [w_m / 2, -h_m / 2, 0],
        [w_m / 2, h_m / 2, 0], [-w_m / 2, h_m / 2, 0],
    ])
    camera = (_rotation(rx, ry, rz) @ corners.T).T + np.array([0, 0, dist])
    return np.stack([
        focal * camera[:, 0] / camera[:, 2] + width / 2,
        focal * camera[:, 1] / camera[:, 2] + height / 2,
    ], axis=1).astype("float32")


def make_page_image(width=1240, height=1754):
    from PIL import Image, ImageDraw

    page = Image.new("RGB", (width, height), (252, 251, 248))
    draw = ImageDraw.Draw(page)
    y = 150
    for line in [
        "Stadtwerke Muenchen GmbH", "", "Rechnung Nr. 88213-2024",
        "Rechnungsdatum: 17.03.2024", "", "Stromabschlag Maerz 2024   84,20 EUR",
        "Grundpreis                 12,90 EUR", "Gesamtbetrag              115,55 EUR",
    ]:
        draw.text((90, y), line, fill=(25, 25, 25))
        y += 60
    return np.array(page)[:, :, ::-1].copy()


def photograph(quad=None, shadow=True, blur=True):
    """Render a page onto a desk under uneven light. Returns JPEG bytes."""
    width, height = CANVAS
    quad = project_page() if quad is None else quad
    page = make_page_image()
    page_h, page_w = page.shape[:2]

    matrix = cv2.getPerspectiveTransform(
        np.float32([[0, 0], [page_w, 0], [page_w, page_h], [0, page_h]]), quad
    )
    desk = np.full((height, width, 3), 118, np.uint8)
    desk[:, :, 0] = 96
    desk[:, :, 2] = 138
    warped = cv2.warpPerspective(page, matrix, (width, height))
    mask = cv2.warpPerspective(np.full((page_h, page_w), 255, np.uint8), matrix, (width, height))
    photo = np.where(mask[:, :, None] > 0, warped, desk)

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    light = 1.20 - 0.55 * (xx / width) - 0.22 * (yy / height)
    if shadow:  # a hand across the right-hand side of the page
        light = light * np.where(xx > width * 0.72, 0.62, 1.0)
    photo = np.clip(photo.astype(np.float32) * np.clip(light, 0.25, 1.35)[:, :, None], 0, 255)
    photo = photo.astype(np.uint8)
    if blur:
        photo = cv2.GaussianBlur(photo, (3, 3), 0)
    return cv2.imencode(".jpg", photo, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes()


# ------------------------------------------------------------------ aspect


@pytest.mark.parametrize("angles", [
    (0.05, 0.03, 0.01), (0.30, 0.20, 0.05), (0.45, -0.35, 0.10), (0.60, 0.50, 0.20),
])
def test_aspect_estimate_recovers_a4(angles):
    """Edge lengths lie under perspective; the projective estimate does not."""
    quad = project_page(*angles)
    estimated = enhance.estimate_aspect(quad, *CANVAS)
    assert estimated is not None
    assert abs(estimated - A4_ASPECT) / A4_ASPECT < 0.02


def test_aspect_estimate_beats_edge_lengths_on_a_tilted_page():
    quad = project_page(0.45, -0.35, 0.10)
    tl, tr, br, bl = quad
    naive = max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)) / max(
        np.linalg.norm(tr - br), np.linalg.norm(tl - bl)
    )
    estimated = enhance.estimate_aspect(quad, *CANVAS)
    assert abs(estimated - A4_ASPECT) < abs(naive - A4_ASPECT)


def test_snap_aspect_only_moves_near_misses():
    assert enhance.snap_aspect(0.70) == pytest.approx(0.7071, abs=1e-4)
    assert enhance.snap_aspect(1.20) == 1.20  # nothing standard nearby


def test_aspect_estimate_declines_on_a_degenerate_quad():
    flat = np.float32([[0, 0], [100, 0], [100, 0], [0, 0]])
    assert enhance.estimate_aspect(flat, *CANVAS) is None


# ---------------------------------------------------------------- detection


@pytest.mark.parametrize("shadow", [False, True])
def test_detects_the_page_corners(shadow):
    quad = project_page()
    data = photograph(quad, shadow=shadow)
    found = enhance.detect_page(cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR))
    assert found is not None, "page not detected"
    error = np.linalg.norm(found - quad, axis=1).mean()
    assert error < 15, f"corners off by {error:.1f}px"


def test_rejects_a_frame_with_no_page():
    """A photo of nothing must not produce a confident crop."""
    noise = np.random.default_rng(0).integers(90, 140, (800, 600, 3), dtype=np.uint8)
    data = cv2.imencode(".jpg", noise)[1].tobytes()
    assert enhance.detect_page(cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)) is None


# ----------------------------------------------------------------- pipeline


def test_magic_mode_crops_deskews_and_flattens():
    out, report = enhance.enhance(photograph(), mode="magic")
    assert report.engine == "opencv"
    assert report.applied == "magic"
    assert report.cropped is True
    assert abs(report.width / report.height - A4_ASPECT) / A4_ASPECT < 0.03

    from PIL import Image

    image = np.array(Image.open(io.BytesIO(out)).convert("L"))
    left = float(image[:, : image.shape[1] // 3].mean())
    right = float(image[:, -image.shape[1] // 3 :].mean())
    # The shadow made the right side much darker; after flattening the paper
    # should be uniformly bright across the page.
    assert left > 190 and right > 190
    assert abs(left - right) < 25


def test_auto_mode_picks_magic_for_paper():
    _, report = enhance.enhance(photograph(), mode="auto")
    assert report.applied == "magic"


def test_bw_mode_is_bilevel_and_small():
    bw, report = enhance.enhance(photograph(), mode="bw")
    colour, _ = enhance.enhance(photograph(), mode="color")
    assert report.applied == "bw"
    assert bw[:4] == b"\x89PNG"          # lossless, and tiny for text
    assert len(bw) < len(colour)


def test_none_mode_leaves_the_image_alone():
    raw = photograph()
    out, report = enhance.enhance(raw, mode="none")
    assert report.applied == "none"
    assert not report.cropped


def test_unreadable_input_is_returned_untouched():
    out, report = enhance.enhance(b"this is not an image", mode="auto")
    assert out == b"this is not an image"
    assert report.warnings


def test_report_serialises_for_the_api():
    _, report = enhance.enhance(photograph(), mode="magic")
    payload = report.as_dict()
    assert set(payload) >= {"mode", "applied", "cropped", "size", "engine", "warnings"}
    import json

    json.dumps(payload)  # must survive the X-Scan-Report header
