# -*- coding: utf-8 -*-
"""Plot the regional effect of changing the wood-stove setpoint offset."""

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
    parser.add_argument("--plus3-dir", type=Path, required=True)
    parser.add_argument("--zero-dir", type=Path, required=True)
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
                "wood_m3st_weighted_mean": float(
                    np.average(group["wood_m3st"], weights=weights)
                ),
            }
        )
    return pd.DataFrame(rows)


def main():
    args = _parse_args()
    plus3 = pd.read_csv(args.plus3_dir / "simulation_results.csv")
    zero = pd.read_csv(args.zero_dir / "simulation_results.csv")
    redpe = pd.read_csv(args.plus3_dir / "regional_consumption_comparison.csv")

    comparison = _regional_weighted_mean(plus3).rename(
        columns={"wood_m3st_weighted_mean": "offset_plus3_m3st"}
    ).merge(
        _regional_weighted_mean(zero).rename(
            columns={"wood_m3st_weighted_mean": "offset_zero_m3st"}
        ),
        on=["codigo_region", "region"],
        how="outer",
        validate="one_to_one",
    )
    comparison = comparison.merge(
        redpe[
            [
                "codigo_region",
                "redpe_low_m3st",
                "redpe_mid_m3st",
                "redpe_high_m3st",
            ]
        ],
        on="codigo_region",
        how="left",
        validate="one_to_one",
    )
    comparison["change_pct"] = (
        comparison["offset_zero_m3st"] / comparison["offset_plus3_m3st"] - 1.0
    ) * 100.0
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

    width = 0.36
    ax_consumption.bar(
        x - width / 2,
        ordered["offset_plus3_m3st"],
        width,
        color="#277da1",
        alpha=0.85,
        label="Setpoint +3 °C",
    )
    ax_consumption.bar(
        x + width / 2,
        ordered["offset_zero_m3st"],
        width,
        color="#90be6d",
        alpha=0.9,
        label="Setpoint de referencia (offset 0 °C)",
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
        "Efecto del offset del setpoint en el consumo regional de leña\n"
        "500 edificios · año 2024 · paso 30 min · intervalo entre cargas 1 h"
    )
    ax_consumption.grid(axis="y", alpha=0.25)
    ax_consumption.legend(
        handles=[
            Line2D([0], [0], color="#277da1", marker="s", markersize=10, linewidth=8, label="Setpoint +3 °C"),
            Line2D([0], [0], color="#90be6d", marker="s", markersize=10, linewidth=8, label="Setpoint offset 0 °C"),
            Line2D([0], [0], color="#d62828", linewidth=5, label="REDPE: rango bajo–alto"),
            Line2D([0], [0], color="#8b0000", marker="D", linestyle="None", label="REDPE: punto medio"),
        ],
        loc="upper left",
        frameon=True,
    )

    colors = np.where(ordered["change_pct"] < 0, "#43aa8b", "#d62828")
    ax_change.bar(x, ordered["change_pct"], color=colors, alpha=0.9)
    ax_change.axhline(0, color="#222222", linewidth=1)
    ax_change.set_ylabel("Cambio del consumo [%]")
    ax_change.set_xlabel("Región")
    ax_change.set_xticks(x, labels, rotation=45, ha="right")
    ax_change.grid(axis="y", alpha=0.25)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    main()
