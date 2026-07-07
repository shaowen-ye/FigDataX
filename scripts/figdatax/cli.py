"""FigDataX command-line interface — subcommands over the extraction engine.

The only place in the package allowed to print and call sys.exit. pandas is
imported here (not at package import) so core stays lightweight.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

from . import __version__
from .core import (FigDataXError, auto_detect_plot_area, generate_grid_overlay,
                   pick_color, split_panels)
from .calibrate import calibrate_axes_multipoint, calibrate_axes
from .extract import (auto_extract_bars, detect_data_colors, extract_by_color_adaptive,
                      trace_curve)


def _default_out(image, suffix):
    base, _ = os.path.splitext(image)
    return f"{base}_{suffix}"


def _load_calibration(path):
    with open(path) as fh:
        spec = json.load(fh)
    xs = spec["x"]
    ys = spec["y"]
    return calibrate_axes_multipoint(
        pixel_points_x=[p[0] for p in xs], data_values_x=[p[1] for p in xs],
        pixel_points_y=[p[0] for p in ys], data_values_y=[p[1] for p in ys],
        x_log=spec.get("x_log", False), y_log=spec.get("y_log", False),
        x_transform=spec.get("x_transform"), y_transform=spec.get("y_transform"))


# ───────────────────────────────────────────────────────────────────
#  Self-test (fast, cv2-only)
# ───────────────────────────────────────────────────────────────────

def run_self_test() -> int:
    """Synthesize a scatter chart with cv2, extract it, assert < 1% error."""
    import cv2
    print("FigDataX self-test")
    print(f"  version: {__version__}")
    for name in ("cv2", "numpy", "pandas", "scipy", "matplotlib"):
        try:
            mod = __import__(name)
            print(f"  dep {name:11s} OK {getattr(mod, '__version__', '')}")
        except Exception:  # noqa: BLE001
            print(f"  dep {name:11s} MISSING")
    try:
        mod = __import__("pypdfium2")
        print(f"  dep pypdfium2   OK {getattr(mod, '__version__', '')} (optional, PDF figures)")
    except Exception:  # noqa: BLE001
        print("  dep pypdfium2   MISSING (optional — needed only to pull figures from PDFs)")

    W, H = 600, 400
    img = np.full((H, W, 3), 255, np.uint8)
    left, right, top, bottom = 80, 560, 40, 360
    cv2.rectangle(img, (left, top), (right, bottom), (0, 0, 0), 2)
    # Data: y = 2x, x in [0,10] over pixel x[left..right], y in [0,25] over [bottom..top].
    truth, x_tick_px = [], []
    for x in range(0, 11, 2):
        y = 2.0 * x
        px = int(left + x / 10.0 * (right - left))
        py = int(bottom - y / 25.0 * (bottom - top))
        cv2.circle(img, (px, py), 6, (0, 0, 255), -1)  # red (BGR)
        cv2.line(img, (px, bottom + 1), (px, bottom + 7), (0, 0, 0), 1)  # x tick
        truth.append((x, y))
        x_tick_px.append(px)

    cal = calibrate_axes_multipoint([left, right], [0, 10], [bottom, top], [0, 25])
    det = extract_by_color_adaptive(img, (0, 255, 255), color_distance=30, subpixel=True)
    got = sorted(cal.pixel_to_data(cx, cy) for cx, cy, _, _ in det)

    ok = len(got) == len(truth)
    max_err = 0.0
    if ok:
        for (gx, gy), (tx, ty) in zip(got, truth):
            max_err = max(max_err, abs(gy - ty))
        ok = max_err < 0.25  # 1% of the 25-unit y range
    print(f"  detected {len(det)}/{len(truth)} points; max y error {max_err:.3f} "
          f"(tol 0.25 = 1% of range)")
    print(f"  calibration RMSE: x={cal.x_rmse:.4g}, y={cal.y_rmse:.4g}")

    # Tick auto-detection: recover the drawn x ticks within ±1.5 px.
    from .core import detect_ticks
    xt = detect_ticks(img, (left, top, right, bottom), axis="x")["x"]
    tick_ok = xt is not None and sum(
        any(abs(p - t) <= 1.5 for p in xt["positions"]) for t in x_tick_px) >= 4
    print(f"  tick detection: {'OK' if tick_ok else 'FAIL'} "
          f"({0 if xt is None else len(xt['positions'])} x-ticks found)")

    ok = ok and tick_ok
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ───────────────────────────────────────────────────────────────────
#  Subcommand handlers
# ───────────────────────────────────────────────────────────────────

def _cmd_extract(args):
    import cv2  # noqa: F401
    import pandas as pd

    if args.calibration_points:
        cal = _load_calibration(args.calibration_points)
    elif args.x_range and args.y_range:
        bbox = tuple(args.bbox) if args.bbox else auto_detect_plot_area(args.image)
        if bbox is None:
            raise FigDataXError("No --bbox and auto-detect failed; supply --bbox or --calibration-points.")
        cal = calibrate_axes(bbox, tuple(args.x_range), tuple(args.y_range),
                             args.x_log, args.y_log)
    else:
        raise FigDataXError("Provide --calibration-points FILE or both --x-range and --y-range.")

    if args.mode in ("semi", "trace") and not args.color_target:
        raise FigDataXError(f"--color-target H S V is required for --mode {args.mode}.")

    if args.mode == "trace":
        pts = trace_curve(args.image, tuple(args.bbox), tuple(args.color_target),
                          converter=cal, n_samples=args.n_samples,
                          color_distance=args.color_distance, subpixel=args.subpixel)
        df = pd.DataFrame(pts, columns=["X", "Y"])
    else:  # semi
        det = extract_by_color_adaptive(args.image, tuple(args.color_target),
                                        color_distance=args.color_distance,
                                        subpixel=args.subpixel, auto_widen=args.auto_widen)
        rows = [(*cal.pixel_to_data(cx, cy), area, conf) for cx, cy, area, conf in det]
        df = pd.DataFrame(rows, columns=["X", "Y", "Area", "Confidence"])

    out = args.output or _default_out(args.image, "extracted.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"=== FigDataX extract ({args.mode}) ===")
    print(f"calibration RMSE: x={cal.x_rmse:.4g} ({cal.x_rmse_pct:.2f}%), "
          f"y={cal.y_rmse:.4g} ({cal.y_rmse_pct:.2f}%)")
    print(df.to_string(index=False, float_format=lambda v: f"{v:.6g}"))
    print(f"saved: {out}")
    if args.validate:
        from .validate import create_validation_plot
        vpath = create_validation_plot(args.image, list(zip(df.X, df.Y)),
                                       _default_out(args.image, "validation.png"))
        print(f"validation: {vpath}")


def _cmd_calibrate(args):
    cal = _load_calibration(args.calibration_points)
    print("=== FigDataX calibrate ===")
    print(f"x: slope={cal.x_coeffs[0]:.6g} intercept={cal.x_coeffs[1]:.6g} "
          f"RMSE={cal.x_rmse:.4g} ({cal.x_rmse_pct:.2f}% of range)")
    print(f"y: slope={cal.y_coeffs[0]:.6g} intercept={cal.y_coeffs[1]:.6g} "
          f"RMSE={cal.y_rmse:.4g} ({cal.y_rmse_pct:.2f}% of range)")


def _cmd_overlay(args):
    out = args.output or _default_out(args.image, "grid.png")
    bbox = tuple(args.bbox) if args.bbox else None
    generate_grid_overlay(args.image, out, plot_bbox=bbox)
    print(f"grid overlay saved: {out}")


def _cmd_panels(args):
    import cv2
    panels = split_panels(args.image, layout=args.layout)
    base, ext = os.path.splitext(args.image)
    for label, panel in panels.items():
        p = f"{base}_panel_{label}{ext or '.png'}"
        cv2.imwrite(p, panel)
        print(f"panel {label}: {p}  {panel.shape[1]}x{panel.shape[0]}")


def _cmd_colors(args):
    if args.at:
        info = pick_color(args.image, args.at[0], args.at[1])
        print(f"color at ({args.at[0]}, {args.at[1]}): HSV {info['hsv']} "
              f"BGR {info['bgr']} {info['hex']}")
        return
    bbox = tuple(args.bbox) if args.bbox else auto_detect_plot_area(args.image)
    if bbox is None:
        raise FigDataXError("Provide --bbox or --at X Y; auto-detect failed.")
    for name, hsv in detect_data_colors(args.image, bbox, n_clusters=args.n):
        print(f"  {name:8s} HSV {hsv}")


def _cmd_geometry(args):
    import json as _json
    from .core import auto_detect_plot_area, detect_ticks, draw_geometry_overlay
    from .extract import suggest_series

    bbox = tuple(args.bbox) if args.bbox else auto_detect_plot_area(args.image)
    if bbox is None:
        raise FigDataXError("No --bbox and auto-detect failed; supply --bbox L T R B.")
    ticks = detect_ticks(args.image, bbox)
    series = suggest_series(args.image, bbox)

    import cv2
    img = cv2.imread(args.image)
    result = {"image_size": [img.shape[1], img.shape[0]],
              "plot_bbox": list(bbox), "ticks": ticks, "series": series}

    annotate = args.annotate or _default_out(args.image, "geometry.png")
    draw_geometry_overlay(args.image, bbox, ticks=ticks, series=series,
                          output_path=annotate)
    result["annotated"] = annotate

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            _json.dump(result, fh, ensure_ascii=False, indent=1)
    print(_json.dumps(result, ensure_ascii=False, indent=1))
    print(f"\nAnnotated overlay: {annotate}"
          + (f"\nGeometry JSON: {args.json}" if args.json else ""))
    for ax in ("x", "y"):
        t = ticks.get(ax)
        if t and t["spacing_cv"] > 0.15:
            print(f"WARNING: {ax}-axis tick spacing is uneven (cv={t['spacing_cv']}); "
                  f"positions may be unreliable — verify against the overlay or use "
                  f"the grid overlay instead.")


def _cmd_pdf_figures(args):
    from .pdf import scan_figures
    out_dir = args.out_dir or os.path.splitext(args.pdf)[0] + "_figures"
    man = scan_figures(args.pdf, out_dir, scale=args.scale, crop_scale=args.crop_scale)

    print(f"Scanned {man['source_pdf']}")
    print(f"Manifest: {os.path.join(out_dir, 'manifest.json')}\n")
    print(f"Figures ({man['n_figures']} bitmap):")
    for f in man["figures"]:
        label = f" [{f['label']}]" if f.get("label") else ""
        print(f"  {f['id']}{label} p.{f['page']}  {f['png']}")
    for u in man["vector_pages"]:
        print(f"  (vector?) p.{u['page']} [{u['label']}] → view {u['page_png']} and crop")
    if not man["figures"] and not man["vector_pages"]:
        print("  (none found)")


def _cmd_pdf_page(args):
    from .pdf import PdfDocument
    import cv2
    out = args.output or f"{os.path.splitext(args.pdf)[0]}_page{args.page}.png"
    with PdfDocument(args.pdf) as doc:
        if not 1 <= args.page <= doc.n_pages:
            raise FigDataXError(f"--page {args.page} out of range 1..{doc.n_pages}")
        bgr = doc.render_page(args.page - 1, scale=args.scale)
    cv2.imwrite(out, bgr)
    print(f"page {args.page} rendered: {out}  {bgr.shape[1]}x{bgr.shape[0]}")


def _cmd_xlsx(args):
    import json as _json
    from .export import export_figures
    with open(args.spec, "r", encoding="utf-8") as fh:
        spec = _json.load(fh)
    out = export_figures(spec["out"], figures=spec.get("figures", []),
                         source_name=spec.get("source", ""))
    print(f"workbook saved: {out}")


# ───────────────────────────────────────────────────────────────────
#  Parser
# ───────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(prog="figdatax",
                                description="FigDataX — scientific figure data extraction")
    p.add_argument("--version", action="version", version=f"FigDataX {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp):
        sp.add_argument("image")
        sp.add_argument("--bbox", type=int, nargs=4,
                        metavar=("L", "T", "R", "B"))
        sp.add_argument("--output")

    ex = sub.add_parser("extract", help="extract data points from a chart")
    add_common(ex)
    ex.add_argument("--mode", choices=["semi", "trace"], default="semi")
    ex.add_argument("--calibration-points", help="JSON: {x:[[px,val]...], y:[[py,val]...], x_log, y_log}")
    ex.add_argument("--x-range", type=float, nargs=2)
    ex.add_argument("--y-range", type=float, nargs=2)
    ex.add_argument("--x-log", action="store_true")
    ex.add_argument("--y-log", action="store_true")
    ex.add_argument("--color-target", type=int, nargs=3, metavar=("H", "S", "V"))
    ex.add_argument("--color-distance", type=float, default=30)
    ex.add_argument("--subpixel", action="store_true")
    ex.add_argument("--auto-widen", action="store_true")
    ex.add_argument("--n-samples", type=int, default=200)
    ex.add_argument("--validate", action="store_true")
    ex.set_defaults(func=_cmd_extract)

    ca = sub.add_parser("calibrate", help="fit and report a calibration from a JSON file")
    ca.add_argument("calibration_points")
    ca.set_defaults(func=_cmd_calibrate)

    ov = sub.add_parser("overlay", help="draw a coordinate grid overlay for manual reading")
    add_common(ov)
    ov.set_defaults(func=_cmd_overlay)

    pa = sub.add_parser("panels", help="split a multi-panel figure")
    pa.add_argument("image")
    pa.add_argument("--layout", default="auto")
    pa.set_defaults(func=_cmd_panels)

    co = sub.add_parser("colors", help="list dominant colors or pick one at a pixel")
    add_common(co)
    co.add_argument("--at", type=int, nargs=2, metavar=("X", "Y"))
    co.add_argument("--n", type=int, default=4)
    co.set_defaults(func=_cmd_colors)

    ge = sub.add_parser("geometry",
                        help="engine geometry pass: plot bbox + tick positions + "
                             "series colors, as JSON + an annotated PNG to eyeball")
    ge.add_argument("image")
    ge.add_argument("--bbox", type=int, nargs=4, metavar=("L", "T", "R", "B"))
    ge.add_argument("--json", help="also write the geometry JSON to this path")
    ge.add_argument("--annotate", help="annotated overlay PNG (default: <img>_geometry.png)")
    ge.set_defaults(func=_cmd_geometry)

    ps = sub.add_parser("pdf-figures",
                        help="crop every figure in a PDF to PNG + write manifest.json")
    ps.add_argument("pdf")
    ps.add_argument("--out-dir", help="default: <pdf-stem>_figures next to the PDF")
    ps.add_argument("--scale", type=float, default=2.0, help="page render zoom")
    ps.add_argument("--crop-scale", type=float, default=4.0, help="figure crop zoom")
    ps.set_defaults(func=_cmd_pdf_figures)

    pp = sub.add_parser("pdf-page", help="render one PDF page to PNG (1-based --page)")
    pp.add_argument("pdf")
    pp.add_argument("--page", type=int, required=True)
    pp.add_argument("--scale", type=float, default=3.0)
    pp.add_argument("--output")
    pp.set_defaults(func=_cmd_pdf_page)

    wk = sub.add_parser("xlsx",
                        help="gather extracted figure CSVs into one Excel workbook")
    wk.add_argument("spec", help='JSON: {"out", "source", "figures": '
                                 '[{"name","csv","provenance"}]}')
    wk.set_defaults(func=_cmd_xlsx)

    st = sub.add_parser("self-test", help="run a fast synthetic extraction self-check")
    st.set_defaults(func=lambda a: sys.exit(run_self_test()))

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except FigDataXError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
