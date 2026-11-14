"""Print the 12-month feature table for a point, save a chart, store it in TigerData, and time
a cold fetch (empty cache) against a cached one.

Usage:  make features                       (Philippines test point)
        .venv/bin/python scripts/feature_table.py --lat 41.9 --lon -93.6
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.data.cache import FileCache  # noqa: E402
from app.features.harmonize import (  # noqa: E402
    MONTH_NAMES,
    FieldFeatures,
    build_field_features,
    store_features,
)

CHART_DIR = ROOT / "data" / "cache" / "charts"


def fmt(v: float | None) -> str:
    if v is None:
        return "     —"
    return f"{v:6.2f}" if abs(v) < 100 else f"{v:6.0f}"


def print_table(ff: FieldFeatures) -> None:
    print(f"\nField {ff.geom_hash} at lat {ff.lat}, lon {ff.lon} | data through {ff.end_month}")
    header = " " * 9 + " ".join(f"{m:>6}" for m in MONTH_NAMES)
    for f in ff.features.values():
        print(f"\n{f.label} [{f.unit}] · {f.native_resolution} · {f.spatial_detail}")
        print(header)
        print(f"{'normal':9}" + " ".join(fmt(v) for v in f.normal) + f"   ({f.normal_period})")
        span = f"{min(m for m in f.recent_months)} to {max(m for m in f.recent_months)}"
        print(f"{'recent':9}" + " ".join(fmt(v) for v in f.recent) + f"   ({span})")
        print(f"{'anomaly':9}" + " ".join(fmt(v) for v in f.anomaly))
        if "record_30y" in f.extra:
            print(f"{'record':9}" + " ".join(fmt(v) for v in f.extra["record_30y"])
                  + f"   (most extreme hour, {f.extra['years']})")
            label, counts = next((k, v) for k, v in f.extra.items() if k.endswith("_years"))
            print(f"{label:9}" + " ".join(f"{c:6d}" for c in counts) + "   (of 30 years)")
    soil, terrain = ff.static.get("soil", {}), ff.static.get("terrain", {})
    grace = ff.static.get("water_storage", {})
    print(f"\nTerrain: {terrain.get('elevation_m')} m, slope {terrain.get('slope_deg')}°")
    print(f"Soil (0-30 cm): {soil.get('texture')}, clay {soil.get('clay_pct')}%, "
          f"pH {soil.get('ph')}, organic carbon {soil.get('soc_g_kg')} g/kg")
    print(f"Regional water storage trend: {grace.get('trend_cm_per_year')} cm/year "
          f"({grace.get('period')})")
    print(f"Information gaps: {ff.gaps or 'none'}")


def save_chart(ff: FieldFeatures) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = list(range(12))
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    panels = [
        ("rain", "Rainfall (mm/day), NASA POWER", "bar"),
        ("ndvi", "Greenness (NDVI), MODIS", "line"),
        ("soil_moisture_root", "Root-zone soil moisture (m³/m³), SMAP", "line"),
        ("t_mean", "Air temperature (°C), NASA POWER", "line"),
    ]
    for ax, (key, title, kind) in zip(axes.flat, panels, strict=True):
        f = ff.features.get(key)
        ax.set_title(title, fontsize=10)
        ax.set_xticks(x, MONTH_NAMES, fontsize=8)
        if f is None:
            ax.text(0.5, 0.5, "no data", ha="center", transform=ax.transAxes)
            continue
        normal = [v if v is not None else float("nan") for v in f.normal]
        recent = [v if v is not None else float("nan") for v in f.recent]
        if kind == "bar":
            ax.bar([i - 0.2 for i in x], normal, 0.4, label=f"normal {f.normal_period}",
                   color="#9bbbd4")
            ax.bar([i + 0.2 for i in x], recent, 0.4, label="last 12 months", color="#2a6f97")
        else:
            ax.plot(x, normal, "--", color="#7a7a7a", label=f"normal {f.normal_period}")
            ax.plot(x, recent, "o-", color="#2a6f97", label="last 12 months")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    fig.suptitle(f"Field {ff.geom_hash}: lat {ff.lat}, lon {ff.lon} (data through {ff.end_month})")
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    path = CHART_DIR / f"features_{ff.geom_hash}.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lat", type=float, default=15.6)
    parser.add_argument("--lon", type=float, default=120.9)
    parser.add_argument("--skip-cold", action="store_true", help="skip the empty-cache timing run")
    args = parser.parse_args()
    point = {"type": "Point", "coordinates": [args.lon, args.lat]}

    if not args.skip_cold:
        t = time.perf_counter()
        build_field_features(point, cache=FileCache(tempfile.mkdtemp()))
        print(f"Cold (empty cache): {time.perf_counter() - t:.1f} s")
    build_field_features(point)  # make sure the shared cache is warm
    t = time.perf_counter()
    ff, daily = build_field_features(point)
    print(f"Cached (TigerData data_cache): {(time.perf_counter() - t) * 1000:.0f} ms")

    print_table(ff)
    stored = store_features(ff, daily)
    print(f"\nStored in TigerData: {stored or 'not stored (see log)'}")
    print(f"Chart: {save_chart(ff)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
