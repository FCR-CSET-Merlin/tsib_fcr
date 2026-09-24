# -*- coding: utf-8 -*-
"""Compare the regional wood-stove runs with and without HDD envelope scaling."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from examples.chile.analyze_wood_stove_regional_dispersion import REGION_NAMES


GEOGRAPHIC_REGION_ORDER = [15, 1, 2, 3, 4, 5, 13, 6, 7, 16, 8, 9, 14, 10, 11, 12]


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--weather-dir", type=Path, required=True)
    parser.add_argument("--hdd-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _regional_weighted_mean(path):
    frame = pd.read_csv(path / "simulation_results.csv")
    rows = []
    for code, group in frame.groupby("codigo_region", sort=False):
        rows.append(
            {
                "codigo_region": int(code),
                "region": REGION_NAMES[int(code)],
                "consumo": float(
                    np.average(group["wood_m3st"], weights=group["n_inmuebles"])
                ),
            }
        )
    return pd.DataFrame(rows)


def main():
    args = _parse_args()
    base = _regional_weighted_mean(args.base_dir).rename(
        columns={"consumo": "base"}
    )
    weather = _regional_weighted_mean(args.weather_dir).rename(
        columns={"consumo": "viento_humedad"}
    )
    hdd = _regional_weighted_mean(args.hdd_dir).rename(
        columns={"consumo": "hdd_viento_humedad"}
    )
    redpe = pd.read_csv(args.hdd_dir / "regional_consumption_comparison.csv")
    redpe = redpe[
        ["codigo_region", "redpe_low_m3st", "redpe_mid_m3st", "redpe_high_m3st"]
    ]
    comparison = base.merge(weather, on=["codigo_region", "region"], how="outer")
    comparison = comparison.merge(hdd, on=["codigo_region", "region"], how="outer")
    comparison = comparison.merge(redpe, on="codigo_region", how="left")
    comparison["hdd_change_pct"] = (
        comparison["hdd_viento_humedad"] / comparison["viento_humedad"] - 1.0
    ) * 100.0
    ordered = (
        comparison.set_index("codigo_region")
        .reindex(GEOGRAPHIC_REGION_ORDER)
        .dropna(subset=["region"])
        .reset_index()
    )

    x = np.arange(len(ordered))
    width = 0.25
    labels = ordered["region"].tolist()
    fig, (ax_consumption, ax_change) = plt.subplots(
        2,
        1,
        figsize=(18, 11),
        sharex=True,
        gridspec_kw={"height_ratios": [2.1, 1]},
        constrained_layout=True,
    )
    ax_consumption.bar(
        x - width,
        ordered["base"],
        width,
        color="#277da1",
        alpha=0.88,
        label="Base: offset 0 / disparador 10",
    )
    ax_consumption.bar(
        x,
        ordered["viento_humedad"],
        width,
        color="#f8961e",
        alpha=0.88,
        label="Viento/humedad en infiltración",
    )
    ax_consumption.bar(
        x + width,
        ordered["hdd_viento_humedad"],
        width,
        color="#8338ec",
        alpha=0.88,
        label="HDD14 en envolvente + viento/humedad",
    )
    for xpos, row in zip(x, ordered.itertuples(index=False)):
        if np.isfinite(row.redpe_low_m3st):
            ax_consumption.vlines(
                xpos,
                row.redpe_low_m3st,
                row.redpe_high_m3st,
                color="#d62828",
                linewidth=5,
                alpha=0.85,
                zorder=5,
            )
            ax_consumption.scatter(
                xpos,
                row.redpe_mid_m3st,
                color="#8b0000",
                marker="D",
                s=42,
                zorder=6,
            )
    ax_consumption.set_ylabel("Consumo anual [m³ estéreo/año]")
    ax_consumption.set_title(
        "Efecto de incorporar HDD14 en la envolvente térmica\n"
        "500 edificios · timestep 30 min · cargas cada 1 h · 220 leños = 1 m³ estéreo"
    )
    ax_consumption.grid(axis="y", alpha=0.25)
    ax_consumption.legend(
        handles=[
            Line2D([0], [0], color="#277da1", marker="s", markersize=10, linewidth=8, label="Base"),
            Line2D([0], [0], color="#f8961e", marker="s", markersize=10, linewidth=8, label="Viento/humedad"),
            Line2D([0], [0], color="#8338ec", marker="s", markersize=10, linewidth=8, label="HDD14 + viento/humedad"),
            Line2D([0], [0], color="#d62828", linewidth=5, label="REDPE: rango bajo–alto"),
            Line2D([0], [0], color="#8b0000", marker="D", linestyle="None", label="REDPE: punto medio"),
        ],
        loc="upper left",
        frameon=True,
    )

    ax_change.bar(
        x,
        ordered["hdd_change_pct"],
        color=np.where(ordered["hdd_change_pct"] >= 0, "#8338ec", "#43aa8b"),
        alpha=0.9,
    )
    ax_change.axhline(0, color="#222222", linewidth=1)
    ax_change.set_ylabel("HDD vs. viento/humedad [%]")
    ax_change.set_xlabel("Región")
    ax_change.set_xticks(x, labels, rotation=45, ha="right")
    ax_change.grid(axis="y", alpha=0.25)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=170)
    plt.close(fig)
    comparison.to_csv(args.output.with_suffix(".csv"), index=False)


if __name__ == "__main__":
    main()
