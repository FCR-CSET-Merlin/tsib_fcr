# -*- coding: utf-8 -*-
"""Plot the regional effect of the exterior-temperature trigger threshold."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from examples.chile.analyze_wood_stove_regional_dispersion import REGION_NAMES


GEOGRAPHIC_REGION_ORDER = [
    15, 1, 2, 3, 4, 5, 13, 6, 7, 16, 8, 9, 14, 10, 11, 12
]


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trigger8-dir", type=Path, required=True)
    parser.add_argument("--trigger10-dir", type=Path, required=True)
    parser.add_argument("--trigger12-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _regional_weighted_mean(results):
    rows = []
    for codigo_region, group in results.groupby("codigo_region", sort=False):
        weights = group["n_inmuebles"].clip(lower=1)
        rows.append(
            {
                "codigo_region": int(codigo_region),
                "region": REGION_NAMES[int(codigo_region)],
                "wood_m3st": float(
                    np.average(group["wood_m3st"], weights=weights)
                ),
            }
        )
    return pd.DataFrame(rows)


def main():
    args = _parse_args()
    directories = {
        "8 °C": args.trigger8_dir,
        "10 °C": args.trigger10_dir,
        "12 °C": args.trigger12_dir,
    }
    regional = []
    for label, directory in directories.items():
        frame = _regional_weighted_mean(
            pd.read_csv(directory / "simulation_results.csv")
        ).rename(columns={"wood_m3st": label})
        regional.append(frame)

    comparison = regional[0]
    for frame in regional[1:]:
        comparison = comparison.merge(
            frame, on=["codigo_region", "region"], how="outer", validate="one_to_one"
        )
    redpe = pd.read_csv(
        args.trigger8_dir / "regional_consumption_comparison.csv"
    )[
        ["codigo_region", "redpe_low_m3st", "redpe_mid_m3st", "redpe_high_m3st"]
    ]
    comparison = comparison.merge(
        redpe, on="codigo_region", how="left", validate="one_to_one"
    )
    comparison["change_10_pct"] = (comparison["10 °C"] / comparison["8 °C"] - 1) * 100
    comparison["change_12_pct"] = (comparison["12 °C"] / comparison["8 °C"] - 1) * 100
    ordered = (
        comparison.set_index("codigo_region")
        .reindex(GEOGRAPHIC_REGION_ORDER)
        .dropna(subset=["region"])
        .reset_index()
    )

    x = np.arange(len(ordered))
    labels = ordered["region"].tolist()
    fig, (ax_consumption, ax_change) = plt.subplots(
        2,
        1,
        figsize=(18, 11),
        sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1]},
        constrained_layout=True,
    )
    width = 0.25
    styles = [
        ("8 °C", "#277da1", -width),
        ("10 °C", "#f8961e", 0),
        ("12 °C", "#90be6d", width),
    ]
    for label, color, shift in styles:
        ax_consumption.bar(
            x + shift,
            ordered[label],
            width,
            color=color,
            alpha=0.88,
            label=f"Disparador {label}",
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
        "Efecto del umbral exterior de encendido de la estufa\n"
        "Offset de setpoint 0 °C · 500 edificios · año 2024 · paso 30 min"
    )
    ax_consumption.grid(axis="y", alpha=0.25)
    ax_consumption.legend(
        handles=[
            Line2D([0], [0], color="#277da1", marker="s", markersize=10, linewidth=8, label="Disparador 8 °C"),
            Line2D([0], [0], color="#f8961e", marker="s", markersize=10, linewidth=8, label="Disparador 10 °C"),
            Line2D([0], [0], color="#90be6d", marker="s", markersize=10, linewidth=8, label="Disparador 12 °C"),
            Line2D([0], [0], color="#d62828", linewidth=5, label="REDPE: rango bajo–alto"),
            Line2D([0], [0], color="#8b0000", marker="D", linestyle="None", label="REDPE: punto medio"),
        ],
        loc="upper left",
        frameon=True,
    )

    ax_change.bar(x - width / 2, ordered["change_10_pct"], width, color="#f8961e", label="10 °C vs 8 °C")
    ax_change.bar(x + width / 2, ordered["change_12_pct"], width, color="#90be6d", label="12 °C vs 8 °C")
    ax_change.axhline(0, color="#222222", linewidth=1)
    ax_change.set_ylabel("Cambio del consumo [%]")
    ax_change.set_xlabel("Región")
    ax_change.set_xticks(x, labels, rotation=45, ha="right")
    ax_change.grid(axis="y", alpha=0.25)
    ax_change.legend(loc="lower left")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    main()
