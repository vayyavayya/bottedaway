# Scanning

What happens between the photo and the PDF, why each step is there, and how to
change it.

---

## The pipeline

`app/enhance.py`, one page at a time:

```
photo
  │  detect_page()        find the sheet of paper — three independent passes
  │  four_point_warp()    flatten the perspective at full resolution
  │  deskew()             straighten what is left, from the text baselines
  │  flatten_lighting()   divide by the blurred background: shadows vanish
  │  white_balance()      grey-world, so tungsten light stops tinting the paper
  │  stretch_contrast()   paper to white, ink to black
  │  denoise()            edge-preserving bilateral
  │  unsharp()            put the crispness back
  ▼
clean page  ──►  pdfbuild.build_pdf()  ──►  searchable A4 PDF
```

### Finding the page

Three detectors run, because no single one survives real kitchen tables:

1. **Gradient edges** (Canny) — the workhorse when the page contrasts with the
   surface.
2. **Bright-region mask** (Otsu) — a white page on a light desk, where the
   gradient is weak but the page is still the brightest large blob.
3. **Locally equalised gradient** (CLAHE → Canny) — a hand or window shadow
   across the page destroys the contrast along one edge, and detectors 1 and 2
   then lock onto the *shadow's* border instead of the paper's. Equalising first
   restores that edge.

Every candidate quadrilateral is then **scored**, not just measured: edge support
(does its outline actually sit on detected edges?), contrast against a ring of
surrounding pixels, and area as a mild tie-breaker. Area alone happily selects a
rectangle drawn across the whole desk — that is the bug the scoring exists to
prevent. Below `MIN_PAGE_SCORE` nothing is cropped and the full frame is kept: a
wrong crop loses content, an uncropped page only looks untidy.

### Getting the shape right

A tilted page's far edge is shorter than its near edge, so warping to the
measured edge lengths squeezes the result — typically 5–8% off. `estimate_aspect()`
instead solves for the camera's focal length from the quadrilateral and recovers
the page's true width-to-height ratio, then snaps to A4/Letter/Legal/ID-card when
it lands within 3.5%.

Measured against pages projected through a known pinhole camera
(`tests/test_enhance.py`):

| Tilt | Naive edge lengths | Projective estimate |
|---|---|---|
| 3° | 0.8% off | **0.00%** |
| 26° | 6.6% off | **0.00%** |
| 34° | 9.1% off | **0.00%** |

### Filters

| Mode | What it is for |
|---|---|
| `auto` | Looks at saturation and brightness, then picks `magic` for paper or `photo` for a photograph |
| `magic` | The one-tap default: white paper, black ink, stamps and signatures still in colour |
| `color` | Gentle — perspective and lighting only, true colours |
| `gray` | Magic in greyscale |
| `bw` | Adaptive-threshold bilevel. Smallest files by far (~80 KB/page vs ~1.2 MB) — best for plain text |
| `photo` | Perspective correction only |
| `none` | Nothing at all |

### Auto-rotation

Off by default. `DOCBOX_SCAN_AUTO_ORIENT=true` runs tesseract's orientation
detection on every page — it fixes sideways scans but costs about a second each.

---

## The PDF

`app/pdfbuild.py`:

- **Page geometry.** The DPI is derived from the pixel size so a page comes out
  actually A4 (or Letter), instead of "1536 pixels wide". Pages are written one
  at a time and merged, because Pillow applies a single resolution to every page
  of a multi-page save — which silently resizes any page that differs from the
  last one.
- **Searchable text.** With tesseract installed, each page is rendered to a
  one-page PDF carrying an invisible text layer, and those are merged. Spotlight,
  the iOS Files app and Preview can then find words *inside* your scans. Without
  tesseract you get a good image-only PDF and a warning saying so.
- **No upscaling, ever.** `DOCBOX_SCAN_DPI` (default 300) is a target, not a
  promise: quality is bounded by the capture. A 12 MP photo filling the frame
  gives roughly 260–290 dpi on A4, which is what the derived DPI will say.

---

## Speed

Measured on this repo's synthetic 12 MP page, one core per page:

| | Before tuning | Now |
|---|---|---|
| One 12 MP page, `magic` | 6.7 s | **2.2 s** |
| One 12 MP page, `bw` | 3.0 s | **1.5 s** |
| Five pages | 34 s | **5.2 s** |

Two changes got there. Non-local-means denoising cost 3.7 s of that single page
and measurably *softened* small text; a bilateral filter is ~30× faster and
scored sharper on the same page. And pages now run through a thread pool —
OpenCV releases the GIL, so a five-page scan costs about as much wall-clock as
its slowest page.

If scanning feels slow on your box, in order of effect: use `bw` for text-only
documents, leave `DOCBOX_SCAN_AUTO_ORIENT` off, and lower `DOCBOX_SCAN_QUALITY`.

---

## Capture

The in-app **Scan** button uses the system camera picker. It has no live
edge-detection viewfinder — the browser cannot draw one on iOS — but the server
does the same detection and dewarping after the fact, so the result is the same;
you just do not see the outline while shooting.

If you want the live viewfinder, use Apple's own scanner via a Shortcut
(`SHORTCUT.md`): **Scan Document** gives you VisionKit's edge detection and
multi-page capture, and posts the result to `/api/scan` where the same pipeline
picks it up.

---

## Tuning

| Setting | Default | Notes |
|---|---|---|
| `DOCBOX_SCAN_MODE` | `auto` | Default filter for shortcut and share-sheet uploads |
| `DOCBOX_SCAN_DPI` | `300` | Target only; the real DPI is derived per page |
| `DOCBOX_SCAN_QUALITY` | `92` | JPEG quality for non-bilevel pages |
| `DOCBOX_SCAN_PAGE_SIZE` | `a4` | `a4`, `letter`, `a5`, `legal` |
| `DOCBOX_SCAN_SEARCHABLE` | `true` | Needs tesseract |
| `DOCBOX_SCAN_AUTO_ORIENT` | `false` | ~1 s/page |

Thresholds worth knowing, in `app/enhance.py`: `MIN_PAGE_AREA` (how much of the
frame a page must fill), `MIN_PAGE_SCORE` (how page-like a quad must be),
`BLUR_WARN` (when a scan is called soft), `SNAP_TOLERANCE` (how close to a
standard page size counts as that size).

Without OpenCV installed, everything above degrades to a Pillow-only path:
autocontrast and sharpening, no edge detection or dewarping. `/api/health`
reports which one you are on.
