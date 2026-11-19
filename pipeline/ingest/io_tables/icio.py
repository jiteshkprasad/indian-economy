"""OECD Inter-Country Input-Output tables, 2025 edition, small version (50 ISIC Rev.4 industries),
2016-2022: India's slice, as a labelled international prior for the optional import matrix (P6a).

Dataset io_tables_icio_india (US$ million, current prices), per year:
- origin=domestic (official): rows IND_<ind> x columns IND_<ind> (intermediate use at basic prices)
  and IND_HFCE/NPISH/GGFC/GFCF/INVNT/DPABR (final demand), plus the OUT column of the IND rows;
- origin=imports (derived): for every column IND_*, the sum over the 80 foreign economies (incl.
  ROW) of the rows <CTRY>_<ind>. This is India's use of imported <ind> products by user, i.e. the
  import-use prior. Only the origin country is summed away; nothing else is changed;
- exports (derived): each IND_<ind> row summed over every non-India column (foreign intermediate
  and final use), i.e. India's exports of <ind> products at basic prices;
- the TLS (taxes less subsidies on products), VA (value added at basic prices) and OUT rows of the
  IND columns (official).
'NA' cells (not available) produce no row; a sum that meets an NA is not computed (build fails).

Conventions and caveats (registry `oecd_icio_2025`): ICIO year '2022' is India's FY 2022-23; India
is on the OLD 2011-12 national-accounts base, with official SUTs only to 2019 (2020-2022 are OECD
estimates). International prior only; it never fills a SAM cell by itself.
Access: the zip was served without a challenge on 29 Sep 2026 (Phase 0 saw a Cloudflare challenge;
docs/phase1/issues/io_tables.md).
"""

from __future__ import annotations

import io
import warnings
import zipfile
from typing import Any

import openpyxl
import polars as pl

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import clean_label

SRC = "oecd_icio_2025"
ZIP = "icio2025_2016_2022_sml.zip"
README = "icio2025_readme_small.xlsx"
YEARS = [str(y) for y in range(2016, 2023)]
# The zip's HTTP Last-Modified (18 May 2026: all 2025-edition files re-uploaded after the second
# revision of mid-January 2026, registry latest_release).
VINTAGE = "2026-05-18"
RELEASE = "OECD Inter-Country Input-Output Tables, 2025 edition (second revision Jan 2026; files re-uploaded 18 May 2026)"
INDUSTRIES = (
    "A01", "A02", "A03", "B05", "B06", "B07", "B08", "B09", "C10T12", "C13T15", "C16", "C17_18", "C19", "C20",
    "C21", "C22", "C23", "C24A", "C24B", "C25", "C26", "C27", "C28", "C29", "C301", "C302T309", "C31T33", "D", "E",
    "F", "G", "H49", "H50", "H51", "H52", "H53", "I", "J58T60", "J61", "J62_63", "K", "L", "M", "N", "O", "P", "Q",
    "R", "S", "T",
)
FINAL_DEMAND = {
    "HFCE": "Household Final Consumption Expenditure",
    "NPISH": "Non-Profit Institutions Serving Households",
    "GGFC": "General Government Final Consumption",
    "GFCF": "Gross Fixed Capital Formation",
    "INVNT": "Changes in Inventories and Valuables",
    "DPABR": "Direct purchases abroad by residents",
}
VALUE_ROWS = {
    "TLS": ("tls", "Taxes less subsidies on intermediate and final products"),
    "VA": ("va", "Value added at basic prices"),
    "OUT": ("out_row", "Output at basic prices"),
}
N_ECONOMIES = 81  # 80 economies + ROW


def _names(ctx: BuildContext) -> dict[str, str]:
    """ISIC activity names from the ReadMe (sheet Area_Activities, cols I:K)."""
    raw = ctx.raw(SRC, README)
    with warnings.catch_warnings():  # the ReadMe defines print areas openpyxl cannot parse (harmless)
        warnings.simplefilter("ignore", UserWarning)
        wb = openpyxl.load_workbook(raw.path, data_only=True, read_only=True)
    ws = wb["Area_Activities"]
    names: dict[str, str] = {}
    for r in ws.iter_rows(min_row=4, max_row=60, values_only=True):
        if isinstance(r[8], int) and isinstance(r[9], str):
            names[r[9]] = clean_label(str(r[10]))
    wb.close()
    if tuple(names) != INDUSTRIES:
        raise ValueError(f"ICIO ReadMe: activity codes {list(names)} differ from the expected 50")
    return names


def build_icio(ctx: BuildContext) -> Dataset:
    names = _names(ctx)
    raw = ctx.raw(SRC, ZIP)
    zf = zipfile.ZipFile(raw.path)
    members = sorted(i.filename for i in zf.infolist())
    if members != [f"{y}_SML.csv" for y in YEARS]:
        raise ValueError(f"ICIO zip members {members}, expected {YEARS}")
    ind_cols = [f"IND_{c}" for c in INDUSTRIES] + [f"IND_{c}" for c in FINAL_DEMAND]
    col_label = {f"IND_{c}": names[c] for c in INDUSTRIES} | {f"IND_{c}": n for c, n in FINAL_DEMAND.items()}
    rows: list[dict[str, Any]] = []
    for year in YEARS:
        data = zf.read(f"{year}_SML.csv")
        header = data[: data.index(b"\n")].decode("utf-8").strip().split(",")
        if header[0] != "V1" or header[-1] != "OUT" or not set(ind_cols) <= set(header):
            raise ValueError(f"ICIO {year}: unexpected header")
        df = pl.read_csv(
            io.BytesIO(data), schema_overrides={c: pl.Float64 for c in header[1:]}, null_values=["NA"]
        )
        labels = df["V1"].to_list()
        countries = sorted({lab.split("_", 1)[0] for lab in labels if "_" in lab})
        if len(countries) != N_ECONOMIES or "IND" not in countries or labels[-3:] != ["TLS", "VA", "OUT"]:
            raise ValueError(f"ICIO {year}: unexpected row structure ({len(countries)} economies, tail {labels[-3:]})")
        if len(labels) != N_ECONOMIES * len(INDUSTRIES) + 3:
            raise ValueError(f"ICIO {year}: {len(labels)} rows, expected {N_ECONOMIES * len(INDUSTRIES) + 3}")
        period = f"{year}-{(int(year) + 1) % 100:02d}"
        common = dict(
            raw=raw, price_basis="current", vintage=VINTAGE, release=RELEASE, unit_as_published="US$ million"
        )
        note = (
            f"ICIO year {year} read as India FY {period} (registry oecd_icio_2025). India on the old 2011-12 NAS base; "
            "2020-2022 are OECD estimates. International prior only."
        )
        p_off = ctx.prov(
            table_id=f"ICIO 2025 {year}_SML.csv",
            locator=f"{ZIP} member {year}_SML.csv: rows IND_A01..IND_T, TLS, VA, OUT x columns IND_A01..IND_T, "
            "IND_HFCE..IND_DPABR, and column OUT of the IND rows",
            notes=note,
            **common,
        )
        p_imp = ctx.prov(
            table_id=f"ICIO 2025 {year}_SML.csv",
            locator=f"{ZIP} member {year}_SML.csv: rows <CTRY>_<ind> for the 80 non-India economies (incl. ROW) x "
            "columns IND_*",
            status="derived",
            method="For each ISIC industry <ind> and each India column, sum the rows <CTRY>_<ind> over all "
            "economies other than IND (80 incl. ROW). Result: imports of <ind> products used by that Indian user, "
            "US$ million at basic prices.",
            notes=note,
            **common,
        )
        p_exp = ctx.prov(
            table_id=f"ICIO 2025 {year}_SML.csv",
            locator=f"{ZIP} member {year}_SML.csv: rows IND_<ind> x every column not starting with IND_ (excl. OUT)",
            status="derived",
            method="For each ISIC industry <ind>, sum row IND_<ind> over every non-India column (80 foreign economies' "
            "intermediate and final use, incl. ROW). Result: India's exports of <ind> products, US$ million at basic "
            "prices.",
            notes=note,
            **common,
        )
        foreign_cols = [c for c in header[1:-1] if not c.startswith("IND_")]
        is_ind = pl.col("V1").str.starts_with("IND_")
        is_value_row = pl.col("V1").is_in(list(VALUE_ROWS))
        dom = df.filter(is_ind)
        if dom["V1"].to_list() != [f"IND_{c}" for c in INDUSTRIES]:
            raise ValueError(f"ICIO {year}: India rows out of the expected order")
        foreign = df.filter(~is_ind & ~is_value_row).with_columns(pl.col("V1").str.slice(4).alias("_ind"))  # 'CHN_C10T12' -> 'C10T12'
        if foreign.select(pl.col(ind_cols).is_null().any()).row(0) != tuple([False] * len(ind_cols)):
            raise ValueError(f"ICIO {year}: NA in a foreign row of an India column; the import sum would be partial")
        imp = foreign.group_by("_ind", maintain_order=True).agg([pl.col(c).sum() for c in ind_cols])
        imp_map = {r["_ind"]: r for r in imp.iter_rows(named=True)}
        if sorted(imp_map) != sorted(INDUSTRIES):
            raise ValueError(f"ICIO {year}: foreign industry codes {sorted(imp_map)} unexpected")
        if dom.select(pl.col(foreign_cols).is_null().any()).to_series(0).any():
            raise ValueError(f"ICIO {year}: NA in an India row of a foreign column; exports sum would be partial")
        exports = dom.select(pl.sum_horizontal(foreign_cols).alias("x"))["x"].to_list()

        def add(sid: str, item: str, label: str, product: str | None, industry: str | None, origin: str | None,
                v: float | None, pid: str, status: str) -> None:
            if v is None:
                return
            rows.append(
                {
                    "series_id": sid,
                    "source_id": SRC,
                    "table_id": f"ICIO 2025 {year}_SML.csv",
                    "item_code": item,
                    "item_label": label,
                    "product": product,
                    "industry": industry,
                    "geography": "IN",
                    "dim_other": f"origin={origin}" if origin else None,
                    "stock_flow": "flow",
                    "period": period,
                    "period_type": "fy",
                    "value": float(v),
                    "unit": "USD_million",
                    "price_basis": "current",
                    "vintage": VINTAGE,
                    "estimate_stage": "n.a.",
                    "status": status,
                    "prov_id": pid,
                }
            )

        dom_rows = {r["V1"][4:]: r for r in dom.iter_rows(named=True)}
        for i, code in enumerate(INDUSTRIES):
            p = f"icio_{code}"
            for col in ind_cols:
                cc = col[4:]
                use = f"icio_{cc}"
                add(f"icio.dom.{code.lower()}.{cc.lower()}.current", "domestic_use",
                    f"{names[code]} (India) | {col_label[col]}", p, use, "domestic", dom_rows[code][col], p_off,
                    "official")
                add(f"icio.imp.{code.lower()}.{cc.lower()}.current", "imported_use",
                    f"{names[code]} (imported, all origins) | {col_label[col]}", p, use, "imports", imp_map[code][col],
                    p_imp, "derived")
            add(f"icio.out.{code.lower()}.current", "output", f"{names[code]} (India) | Output at basic prices", p,
                None, None, dom_rows[code]["OUT"], p_off, "official")
            add(f"icio.exports.{code.lower()}.current", "exports",
                f"{names[code]} (India) | Exports (sum over foreign users)", p, None, None, exports[i], p_exp, "derived")
        vrows = {r["V1"]: r for r in df.filter(is_value_row).iter_rows(named=True)}
        for rcode, (item, label) in VALUE_ROWS.items():
            for col in ind_cols:
                cc = col[4:]
                add(f"icio.{item}.{cc.lower()}.current", item, f"{label} | {col_label[col]} (India)", None,
                    f"icio_{cc}", None, vrows[rcode][col], p_off, "official")
    zf.close()
    return Dataset(
        "io_tables_icio_india",
        pl.DataFrame(rows),
        "OECD ICIO 2025 India slice 2016-2022 (50 ISIC industries): domestic and imported use, TLS, VA, output, US$ mn",
    )
