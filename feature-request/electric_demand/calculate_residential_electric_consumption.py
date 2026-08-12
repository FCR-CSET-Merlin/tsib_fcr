"""Calcula indicadores regionales de consumo eléctrico residencial, Chile 2024.

Fuentes:
* BNE 2024: consumo de ELECTRICIDAD / CPR / RESIDENCIAL (teracalorías).
* Censo 2024: viviendas conectadas a red pública (p9_fuente_elect == 1).
"""

from pathlib import Path
import unicodedata

import pandas as pd


OUTPUT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = OUTPUT_DIR.parents[1]
RUNTIME_CSV_PATH = (
    REPOSITORY_ROOT
    / "tsib"
    / "data"
    / "chile"
    / "consumo_electrico_residencial_regional_2024.csv"
)
BNE_FILE = REPOSITORY_ROOT / "shared" / "bne" / "ConsumosRegionales_BNE2024.xlsx"
CENSUS_FILE = (
    REPOSITORY_ROOT
    / "shared"
    / "census2024"
    / "viv_hog_per_censo2024"
    / "viviendas_censo2024.parquet"
)

# El orden regional de las columnas de la BNE no sigue el código regional para
# las regiones 13--16; se explicita para evitar una asignación por posición ambigua.
BNE_REGION_COLUMNS = {
    1: "Tarapacá",
    2: "Antofagasta",
    3: "Atacama",
    4: "Coquimbo",
    5: "Valparaíso",
    6: "O´Higgins",
    7: "Del Maule",
    8: "Biobío",
    9: "Araucanía",
    10: "Los Lagos",
    11: "Aysén",
    12: "Magallanes",
    13: "Metropolitana",
    14: "Los Ríos",
    15: "Arica y Parinacota",
    16: "Ñuble",
}
REGION_NAMES = {
    1: "Tarapacá", 2: "Antofagasta", 3: "Atacama", 4: "Coquimbo",
    5: "Valparaíso", 6: "Libertador General Bernardo O'Higgins",
    7: "Maule", 8: "Biobío", 9: "La Araucanía", 10: "Los Lagos",
    11: "Aysén", 12: "Magallanes y de la Antártica Chilena",
    13: "Metropolitana de Santiago", 14: "Los Ríos",
    15: "Arica y Parinacota", 16: "Ñuble",
}
TCAL_TO_KWH = 1_162_222.2222222222


def normalise(value: object) -> str:
    """Compara etiquetas BNE sin depender de tildes o mayúsculas."""
    text = unicodedata.normalize("NFKD", str(value))
    return "".join(char for char in text if not unicodedata.combining(char)).strip().upper()


def read_bne_consumption() -> pd.DataFrame:
    bne = pd.read_excel(BNE_FILE, sheet_name="data", header=2)
    label_columns = list(bne.columns[:3])
    selected = bne.loc[
        (bne[label_columns[0]].map(normalise) == "ELECTRICIDAD")
        & (bne[label_columns[1]].map(normalise) == "CPR")
        & (bne[label_columns[2]].map(normalise) == "RESIDENCIAL")
    ]
    if len(selected) != 1:
        raise ValueError(f"Se esperaba una fila BNE y se encontraron {len(selected)}.")

    row = selected.iloc[0]
    return pd.DataFrame(
        {
            "region": list(BNE_REGION_COLUMNS),
            "nombre_region": [REGION_NAMES[region] for region in BNE_REGION_COLUMNS],
            "consumo_electrico_residencial_tcal": [
                float(row[column]) for column in BNE_REGION_COLUMNS.values()
            ],
        }
    )


def read_census_denominators() -> pd.DataFrame:
    columns = ["region", "p9_fuente_elect", "p11a_num_personas", "cant_per"]
    homes = pd.read_parquet(CENSUS_FILE, columns=columns)
    grid_homes = homes.loc[homes["p9_fuente_elect"].eq(1)].copy()
    result = (
        grid_homes.groupby("region", as_index=False)
        .agg(
            viviendas_conectadas_red_publica=("p9_fuente_elect", "size"),
            personas_residentes_p11a=("p11a_num_personas", "sum"),
            personas_censadas_cant_per=("cant_per", "sum"),
        )
        .astype({"region": "int64", "viviendas_conectadas_red_publica": "int64"})
    )
    return result


def to_markdown_table(frame: pd.DataFrame) -> str:
    """Genera una tabla Markdown sin requerir dependencias opcionales."""
    headers = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for values in frame.itertuples(index=False, name=None):
        cells = [str(value).replace("|", "\\|") for value in values]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    consumption = read_bne_consumption()
    census = read_census_denominators()
    result = consumption.merge(census, on="region", how="left", validate="one_to_one")
    if result.isna().any().any():
        raise ValueError("Faltan datos censales para al menos una región.")

    result["consumo_electrico_residencial_gwh"] = (
        result["consumo_electrico_residencial_tcal"] * TCAL_TO_KWH / 1_000_000
    )
    result["kwh_por_vivienda_conectada"] = (
        result["consumo_electrico_residencial_tcal"] * TCAL_TO_KWH
        / result["viviendas_conectadas_red_publica"]
    )
    result["kwh_por_persona_p11a"] = (
        result["consumo_electrico_residencial_tcal"] * TCAL_TO_KWH
        / result["personas_residentes_p11a"]
    )
    result["kwh_por_persona_cant_per"] = (
        result["consumo_electrico_residencial_tcal"] * TCAL_TO_KWH
        / result["personas_censadas_cant_per"]
    )
    result = result[
        [
            "region", "nombre_region", "consumo_electrico_residencial_tcal",
            "consumo_electrico_residencial_gwh", "viviendas_conectadas_red_publica",
            "personas_residentes_p11a", "personas_censadas_cant_per",
            "kwh_por_vivienda_conectada", "kwh_por_persona_p11a",
            "kwh_por_persona_cant_per",
        ]
    ]

    csv_path = OUTPUT_DIR / "consumo_electrico_residencial_regional_2024.csv"
    result.to_csv(csv_path, index=False, encoding="utf-8-sig", float_format="%.2f")
    result.to_csv(RUNTIME_CSV_PATH, index=False, encoding="utf-8", float_format="%.2f")

    display = result.copy()
    for column in display.columns[2:]:
        display[column] = display[column].map(lambda value: f"{value:,.2f}")
    report = """# Consumo eléctrico residencial regional, 2024

La tabla atribuye el consumo BNE de electricidad residencial a las viviendas que
declaran conexión a red pública (`p9_fuente_elect = 1`) y a las personas que
residen o fueron censadas en dichas viviendas.

Unidades: consumo BNE en teracalorías (Tcal); conversión de referencia:
1 Tcal = 1.162222 GWh = 1,162,222.22 kWh. Los indicadores son anuales.

""" + to_markdown_table(display) + """

## Fuentes y criterios

- `shared/bne/ConsumosRegionales_BNE2024.xlsx`, hoja `data`, fila
  `ELECTRICIDAD` / `CPR` / `RESIDENCIAL`. La planilla indica valores en Tcal.
- `shared/census2024/viv_hog_per_censo2024/viviendas_censo2024.parquet`.
  Se consideraron solo registros con `p9_fuente_elect = 1`.
- `personas_residentes_p11a` es la suma de `p11a_num_personas` y
  `personas_censadas_cant_per` la suma de `cant_per`, ambas dentro de las
  viviendas conectadas a la red pública.

## Integración en tsib-fcr

La librería usa `kwh_por_persona_p11a` cuando `BuildingConfiguration` recibe
`country="CL"` y `region`. El script de cálculo también actualiza la copia de
runtime en `tsib/data/chile/consumo_electrico_residencial_regional_2024.csv`.
El valor regional se multiplica por `n_persons` y `n_apartments`; la forma
horaria existente no cambia.

Esta cifra representa electricidad residencial total observada y puede incluir
calefacción, refrigeración y ACS eléctricos. En el flujo previsto, esos usos se
simulan por separado y luego se reconcilian con el balance energético; no deben
sumarse directamente a esta línea base sin ese ajuste posterior.
"""
    (OUTPUT_DIR / "README.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
