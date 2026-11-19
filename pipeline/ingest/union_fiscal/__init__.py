"""Union government accounts and taxes (CGA Finance Accounts, Union Budget documents, PPAC, NSI).

This unit is the audited/official anchor for the Union government block of the SAM and the
substitute for GSTN and CBDT, which are not automated (DECISIONS D1-1c).

Datasets (all Rs crore, current prices; `institution` G_CEN = Union government):
- union_fiscal_fa_receipts: Union Finance Accounts 2023-24 (CGA, certified by the C&AG on
  10 Dec 2024), Statement No. 8 "Detailed account of revenue receipts and capital receipts by
  minor heads": every minor head, sub-major and major head total and section total, 2023-24
  (Audited). Includes MH 0005/0007/0008/0009 GST with the IGST apportionment minor heads,
  MH 0020/0021 direct taxes, MH 0037/0038 customs and excise, MH 0049 interest, MH 0050
  dividends by payer (106 = RBI surplus 87,416.22), and minor head 901 "Share of net proceeds
  assigned to States" (the devolution, netted inside each tax head).
- union_fiscal_fa_expenditure: the same accounts, Statement No. 9 "Detailed account of revenue
  expenditure by minor heads and capital expenditure by major heads", column 3 (Total =
  voted + charged), 2023-24 (Audited). The 'voted' column and the charged amounts printed in
  italics are not ingested (the total is).
- union_fiscal_rb_receipts: Receipt Budget, Tax Revenue (tr) and Non Tax Revenue (ntr) tables,
  ACTUALS column only, from three Budgets: 2024-25 (July 2024; Actuals 2022-23, xlsx),
  2025-26 (Actuals 2023-24, PDF: the budget2025-26 archive's tr.xls/ntr.xls are the stale Interim
  2024-25 vintage and its .xlsx names return 404) and 2026-27 (Actuals 2024-25, xlsx).
- union_fiscal_afs: Annual Financial Statement (allafs.xlsx), Statement I (Consolidated Fund,
  revenue and capital, receipts and disbursements) and Statement III (Public Account), by major
  head, ACTUALS column, Budgets 2024-25 (Actuals 2022-23) and 2025-26 (Actuals 2023-24). The
  current /doc/AFS/allafs.xlsx is not used: it is byte-identical to the July 2024 file.
- union_fiscal_exp_profile: Expenditure Profile Statements 1 (summary of expenditure), 7
  (subsidies), 18 (transfers to States and UTs with legislature, excluding devolution), 20
  (grants and loans to foreign governments) and 21 (contributions to international bodies),
  ACTUALS column, Budgets 2024-25, 2025-26 and 2026-27 (Actuals 2022-23, 2023-24, 2024-25).
  dim_other 'level': heading (top groups), department (Statement 21's numbered departments under
  each ministry heading; series 'stat21.dept.<name>'), item, subitem ('4.01' under item 4). Each
  of heading, department and item adds up to the Grand Total on its own; never sum two levels.
- union_fiscal_nssf: Receipt Budget Annex 8 "Sources and application of National Small Savings
  Fund", Actual column, Budgets 2025-26 (2023-24) and 2026-27 (2024-25).
- union_fiscal_ppac_exchequer: PPAC "Contribution of Petroleum Sector to Exchequer" (table
  posted 17.07.2026), Centre and State taxes, duties, royalties and dividends, 2014-15 to
  2025-26 (P).
- union_fiscal_nsi_collections: NSI "Collection under National Savings Schemes", gross,
  withdrawals and net, 2002-03 to 2025-26.
- union_fiscal_gcca: Expenditure Profile Statement 6 "Allocation under the object head Grants for
  creation of capital assets", ACTUALS column, Budgets 2024-25, 2025-26 and 2026-27 (Actuals
  2022-23 to 2024-25), by ministry, demand and item (dim_other 'level'; each level adds up to the
  Grand Total on its own). All grantees; the statement has no grantee split.
- union_fiscal_fa_gia: Finance Accounts 2023-24, Appendix to Statement 9 (IGAS-2 disclosure):
  grants-in-aid released by category of grantee (State Governments, UTs, local bodies, PSUs,
  autonomous bodies, ...) and the part for creation of capital assets, cash and in kind, Rs lakh
  converted to crore (Audited).
- union_fiscal_fa_provident_funds: Finance Accounts 2023-24, Statement 14, MH 8009 State Provident
  Funds (GPF), 8011 Insurance and Pension Funds, 8014 Postal Life Insurance: balances on 31 Mar 2023
  and 2024 and gross additions/discharges 2023-24, by minor head (Audited).
- union_fiscal_pib_gst: PIB (Ministry of Finance) monthly GST releases for April and May 2023:
  headline split (gross, CGST, SGST, IGST and cess incl. imports, IGST settled, post-settlement
  CGST/SGST) and the State-wise domestic GST table. Located through PIB's archive form (D1-7); PIB
  served a bot challenge before the other ten months of FY 2023-24 were pinned (union_fiscal-1).

One source id per file (ACCESS_PLAN s.6 flagged double claims): Statement 18 files belong to
`union_budget_transfers_to_states`; every other Budget file, including Annex 8, to
`mof_union_budget_2026_27` (the registry entry for the Budget document set; the 2024-25 and
2025-26 files are its archive vintages); Finance Accounts to `cga_finance_accounts_aag`.

Access: the PPAC landing page carries a site-wide sign-in form, which the fetch layer refuses
(D1-1b), so the XLS is fetched from the registry's data URL (issues union_fiscal-2). Finance
Accounts Statement 9 needs six text-layer fix-ups, listed in FA9_FIXUPS and checked by the
statement's own totals (union_fiscal-5).

Skipped (see docs/phase1/issues/union_fiscal.md): PIB GST releases for June 2023 to March 2024
(bot challenge, D1-1b), GSTN and CBDT (D1-1c), Finance Accounts Statements 1, 11, 13, 14A, 16 and
the debt parts of 14 (not parsed), Receipt Budget Annex 7 (tax expenditure) and Demand 42 SBE,
the DEA economic-functional classification (latest actuals year 2015-16).
"""

from __future__ import annotations

import calendar
import re
from collections import Counter
from typing import Any

import polars as pl

from pipeline.core.fetch import AccessBlocked, OfflineMissing
from pipeline.core.geo import state_code
from pipeline.core.unit import BuildContext, Dataset, FetchContext
from pipeline.core.units import clean_label, conversion_note, slug

from . import budget as B
from . import fa as FA
from . import fa_other as FO
from . import other as O
from . import pib as P

UNIT = "union_fiscal"
SOURCES = [
    "cga_finance_accounts_aag",
    "mof_union_budget_2026_27",
    "union_budget_transfers_to_states",
    "ppac_petroleum_exchequer",
    "nsi_small_savings_collections",
    "pib_gst_monthly_releases",
]

CGA = "cga_finance_accounts_aag"
MOF = "mof_union_budget_2026_27"
TRF = "union_budget_transfers_to_states"
PPAC = "ppac_petroleum_exchequer"
NSI = "nsi_small_savings_collections"
PIB = "pib_gst_monthly_releases"  # registry addition (data/registry_additions/union_fiscal.yaml)

# ---------------------------------------------------------------------------------------------
# What is fetched
# ---------------------------------------------------------------------------------------------

FA_LISTING = "https://cga.nic.in/FinanceReport/Published/2023-2024.aspx"
FA_BASE = "https://cga.gov.in//writereaddata/file/Fin20232024"
# Vintage: the C&AG certificate date ('Dated: 10th December, 2024', Fin20232024CAGCert.pdf), used as a
# proxy for the release date. The statements print no publication date; the server Last-Modified
# dates (fetch .meta.json) are 16 Dec 2024 (St 8) and 18 Dec 2024 (St 9, certificate), i.e. uploads
# of individual files, not one release date. See issues file, verify-4.
FA_VINTAGE = "2024-12-10"
FA_VINTAGE_NOTE = (
    "Vintage 2024-12-10 is the C&AG certificate date, used as a proxy for the release date: the statements print "
    "no publication date; the files' server Last-Modified dates are 16-18 Dec 2024 (per-file uploads)."
)
FA_RELEASE = "Finance Accounts of the Union Government 2023-24 (CGA; C&AG certificate dated 10 Dec 2024)"
FA_YEAR = "2023-24"

BUDGET_HOME = "https://www.indiabudget.gov.in/"


# Budget vintages: (tag, URL prefix, presentation date, actuals year, release text)
BUDGETS = {
    "b2425": ("https://www.indiabudget.gov.in/budget2024-25/doc/", "2024-07-23", "2022-23",
              "Union Budget 2024-25 (presented 23 Jul 2024), Actuals 2022-23"),
    "b2526": ("https://www.indiabudget.gov.in/budget2025-26/doc/", "2025-02-01", "2023-24",
              "Union Budget 2025-26 (presented 1 Feb 2025), Actuals 2023-24"),
    "b2627": ("https://www.indiabudget.gov.in/doc/", "2026-02-01", "2024-25",
              "Union Budget 2026-27 (presented 1 Feb 2026), Actuals 2024-25"),
}
# Receipt Budget tax / non-tax tables: xlsx where the archive has the right vintage, else PDF.
RB_FILES = {"b2425": "xlsx", "b2526": "pdf", "b2627": "xlsx"}
AFS_BUDGETS = ("b2425", "b2526")
EP_STATS = {
    "stat1": ("SUMMARY OF EXPENDITURE", MOF, "Statement 1"),
    "stat7": ("STATEMENT ON SUBSIDIES AND SUBSIDY RELATED SCHEMES", MOF, "Statement 7"),
    "stat18": ("TOTAL TRANSFER OF RESOURCES TO STATES", TRF, "Statement 18"),
    "stat20": ("GRANTS AND LOANS TO FOREIGN GOVERNMENTS", MOF, "Statement 20"),
    "stat21": ("CONTRIBUTIONS TO INTERNATIONAL BODIES", MOF, "Statement 21"),
}
ANNEX8_BUDGETS = ("b2526", "b2627")

PPAC_PAGE = "https://ppac.gov.in/prices/contribution-to-central-and-state-exchequer"
PPAC_XLS = "https://ppac.gov.in/uploads/page-images/1790331603_PP_4_ContributionToExchequer%281%29.xls"
NSI_PAGE = "https://www.nsiindia.gov.in/InternalPage.aspx?Id_Pk=152"
NSI_VINTAGE = "2026"  # the page shows no date; its last row is 2025-26 (see issues file)

# Finance Accounts St 9: corrections of the PDF text layer, each checked against the printed page.
# {(pdf page, English text as extracted): corrected text, or None to drop stray glyphs}
FA9_FIXUPS: dict[tuple[int, str], str | None] = {
    # p160: minor head 101 printed as '1a 01' (glyph split)
    (20, "1a 01 Pensions in lieu of resumed"): "101 Pensions in lieu of resumed",
    # p155: '114 Wireless and Computers' extracted as '11 4Wireless and Computers'
    (15, "11 4Wireless and Computers"): "114 Wireless and Computers",
    # p224: '911 Deduct-Recoveries of Overpayments' extracted as '9a 11 ...'
    (84, "9a 11 Deduct—Recoveries of Overpayments"): "911 Deduct—Recoveries of Overpayments",
    # p234: the TOTAL-GRANTS-IN-AID amounts are printed on the 'GRAND TOTAL–' line and the grand
    # total's label wraps over three lines
    (94, "GRAND TOTAL–"): "",
    (94, "EXPENDITURE HEADS"): "GRAND TOTAL– EXPENDITURE HEADS",
    # p228: stray glyphs '0' / '3' at the foot of the page, below the last TOTAL
    (88, "0"): None,
    # p236: the words 'TOTAL (a) - CAPITAL' are missing from the text layer
    (96, "ACCOUNT OF EDUCATION,"): "TOTAL (a) - CAPITAL ACCOUNT OF EDUCATION,",
}
FA9_STRAY_PAGES = (88,)  # p228 carries stray glyphs '0 0 3' below the last TOTAL


# PIB monthly GST press releases for the collections of FY 2023-24 (April 2023 .. March 2024), each
# issued on the 1st of the following month by the Ministry of Finance. Located through PIB's public
# release archive (allRel.aspx), an ASP.NET form posted back with its own hidden fields (D1-7).
PIB_ARCHIVE = "https://www.pib.gov.in/allRel.aspx?reg=3&lang=1"
PIB_RELEASE = "https://www.pib.gov.in/PressReleasePage.aspx?PRID={prid}&reg=3&lang=1"
PIB_MOF = "15"  # 'Ministry of Finance' in the archive's ministry list (asserted in fetch)
GST_MONTHS = [(2023, m) for m in range(4, 13)] + [(2024, m) for m in range(1, 4)]  # collection months


def _release_date(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def fetch(ctx: FetchContext) -> None:
    for st in ("8", "9"):
        ctx.fetch(CGA, f"{FA_BASE}Statement{st}.pdf", name=f"fa2324_statement{st}.pdf", referer=FA_LISTING)
    ctx.fetch(CGA, f"{FA_BASE}CAGCert.pdf", name="fa2324_cag_certificate.pdf", referer=FA_LISTING)
    # Statement 14 (debt and other interest-bearing obligations: provident funds) and the IGAS-2
    # appendix to Statement 9 (grants-in-aid by grantee, of which for capital assets)
    ctx.fetch(CGA, f"{FA_BASE}Statement14.pdf", name="fa2324_statement14.pdf", referer=FA_LISTING)
    ctx.fetch(CGA, f"{FA_BASE}Statement9Appendix.pdf", name="fa2324_statement9_appendix.pdf", referer=FA_LISTING)
    for tag, (base, _d, _y, _r) in BUDGETS.items():
        for tab in ("tr", "ntr"):
            ext = RB_FILES[tag]
            ctx.fetch(MOF, f"{base}rec/{tab}.{ext}", name=f"{tag}_{tab}.{ext}", referer=BUDGET_HOME)
        if tag in AFS_BUDGETS:
            ctx.fetch(MOF, f"{base}AFS/allafs.xlsx", name=f"{tag}_allafs.xlsx", referer=BUDGET_HOME)
        for st, (_t, src, _n) in EP_STATS.items():
            ctx.fetch(src, f"{base}eb/{st}.xlsx", name=f"{tag}_{st}.xlsx", referer=BUDGET_HOME)
        ctx.fetch(MOF, f"{base}eb/stat6.xlsx", name=f"{tag}_stat6.xlsx", referer=BUDGET_HOME)
        if tag in ANNEX8_BUDGETS:
            ctx.fetch(MOF, f"{base}rec/annex8.pdf", name=f"{tag}_annex8.pdf", referer=BUDGET_HOME)
    # The XLS is fetched from the registry's data URL. The landing page is not fetched: it carries
    # a site-wide sign-in form, which the fetch layer treats as a login page (see issues file,
    # union_fiscal-2). The file itself needs no login. PPAC renames the file on each upload, so a
    # new upload makes this fetch fail loudly (404) and the URL must be updated by hand.
    ctx.fetch(PPAC, PPAC_XLS, name="ppac_contribution_to_exchequer.xls", referer=PPAC_PAGE, expect="xls")
    ctx.fetch(NSI, NSI_PAGE, name="nsi_collections_id152.html", expect="html")
    _fetch_pib_gst(ctx)


def _fetch_pib_gst(ctx: FetchContext) -> None:
    """GET the archive page once (pinned), then for each release date post the archive form back
    with its hidden fields and the date/ministry filters (D1-7), pick the one GST-collection release
    listed for that day, and fetch it. Everything is pinned, so a re-run reads the same PRIDs."""
    try:
        _fetch_pib_gst_months(ctx)
    except AccessBlocked as e:
        # www.pib.gov.in served an F5 bot challenge on 2026-09-29 after the first releases were
        # pinned (union_fiscal-1). Not worked around (D1-1b): the build ingests only the pinned
        # releases (PIB_MONTHS_PINNED) and the rest are logged.
        ctx.warn(f"PIB blocked; remaining GST releases not fetched (D1-1b, union_fiscal-1): {str(e)[:200]}")
    except OfflineMissing as e:
        ctx.log(f"PIB GST releases not pinned beyond this point (blocked on the last online run): {str(e)[:200]}")


def _fetch_pib_gst_months(ctx: FetchContext) -> None:
    form_page = ctx.fetch(PIB, PIB_ARCHIVE, name="pib_allrel_form.html", expect="html")
    hidden, ministries = P.archive_form(form_page.path)
    if ministries.get(PIB_MOF) != "Ministry of Finance":
        raise ValueError(f"PIB archive: ministry option {PIB_MOF} is {ministries.get(PIB_MOF)!r}")
    for y, m in GST_MONTHS:
        ry, rm = _release_date(y, m)
        form = {
            "script_HiddenField": "",
            "__EVENTTARGET": "ctl00$ContentPlaceHolder1$ddlYear",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            "__VIEWSTATE": hidden["__VIEWSTATE"],
            "__VIEWSTATEGENERATOR": hidden["__VIEWSTATEGENERATOR"],
            "__VIEWSTATEENCRYPTED": "",
            "__EVENTVALIDATION": hidden["__EVENTVALIDATION"],
            "ctl00$Bar1$ddlregion": "3",
            "ctl00$Bar1$ddlLang": "1",
            "ctl00$ContentPlaceHolder1$ddlMinistry": PIB_MOF,
            "ctl00$ContentPlaceHolder1$ddlday": "1",
            "ctl00$ContentPlaceHolder1$ddlMonth": str(rm),
            "ctl00$ContentPlaceHolder1$ddlYear": str(ry),
            "ctl00$ContentPlaceHolder1$hydregionid": "3",
            "ctl00$ContentPlaceHolder1$hydLangid": "1",
        }
        listing = ctx.fetch(PIB, PIB_ARCHIVE, name=f"pib_allrel_mof_{ry}-{rm:02d}-01.html", method="POST",
                            form_body=form, referer=PIB_ARCHIVE, expect="html")
        prid = P.gst_prid(listing.path, year=y, month=m)
        ctx.fetch(PIB, PIB_RELEASE.format(prid=prid), name=f"pib_gst_{y}-{m:02d}.html",
                  referer=PIB_ARCHIVE, expect="html")


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------


def _row(**kw: Any) -> dict[str, Any]:
    base = {
        "geography": "IN",
        "stock_flow": "flow",
        "period_type": "fy",
        "unit": "INR_crore",
        "price_basis": "current",
        "status": "official",
    }
    base.update(kw)
    return base


def _slug(text: str) -> str:
    """slug() that returns '' for text with no letters or digits (slug() raises)."""
    return slug(text) if re.search(r"[A-Za-z0-9]", text or "") else ""


def _dim_other(**kv: str) -> str | None:
    items = sorted((k, v) for k, v in kv.items() if v)
    return ";".join(f"{k}={v}" for k, v in items) or None


def _check_unique(rows: list[dict[str, Any]], what: str) -> None:
    c = Counter((r["series_id"], r["vintage"], r["period"]) for r in rows)
    dup = [k for k, n in c.items() if n > 1]
    if dup:
        raise ValueError(f"{what}: duplicate series keys {dup[:10]}")


# ---------------------------------------------------------------------------------------------
# Finance Accounts
# ---------------------------------------------------------------------------------------------


def _fa_dataset(ctx: BuildContext, st: str) -> Dataset:
    raw = ctx.raw(CGA, f"fa2324_statement{st}.pdf")
    if st == "8":
        lines = FA.read_lines(raw.path, eng_min=232, eng_max=470, amount_min_x1=500)
        hp = FA.HeadParser("Statement 8")
        side, title = "receipts", "Statement No. 8 (receipts by minor heads)"
        col = "column 'Actuals for 2023-24'"
    else:
        lines = FA.read_lines(raw.path, eng_min=205, eng_max=430, amount_min_x1=500, ignore_amount_x1=(430, 495))
        hp = FA.HeadParser("Statement 9", fixups=FA9_FIXUPS, stray_pages=FA9_STRAY_PAGES)
        side, title = "payments", "Statement No. 9 (revenue expenditure by minor heads, capital by major heads)"
        col = "column 3 'Total' (voted + charged)"
    heads = hp.run(lines)
    for ln in hp.dropped:
        ctx.log(f"Statement {st} p{ln.page}: ignored non-table line {ln.text[:60]!r} {ln.amounts}")
    table_id = f"Finance Accounts 2023-24, Statement No. {st}"
    prov: dict[tuple[int, str], str] = {}
    rows: list[dict[str, Any]] = []
    sections: Counter[str] = Counter()
    for h in heads:
        key = (h.page, h.printed_page)
        if key not in prov:
            prov[key] = ctx.prov(
                raw=raw,
                table_id=table_id,
                locator=f"{title}, printed page {h.printed_page} (PDF page {h.page}), English head of account and "
                f"{col}; rows matched by head-of-account codes",
                unit_as_published="Rs thousand ('In thousands of rupees')",
                conversion=conversion_note("INR_thousand"),
                price_basis="current",
                vintage=FA_VINTAGE,
                release=FA_RELEASE,
                notes=FA_VINTAGE_NOTE,
            )
        if h.kind == "minor":
            sid = f"fa{st}.{h.major}.{h.sub_major}.{h.minor}"
            code = f"mh{h.major}.{h.sub_major}.{h.minor}"
            dims = _dim_other(major_head=h.major, sub_major_head=h.sub_major, minor_head=h.minor)
            label = h.label
        elif h.kind == "sm_total":
            sid = f"fa{st}.{h.major}.{h.sub_major}.total"
            code = f"mh{h.major}.{h.sub_major}.total"
            dims = _dim_other(major_head=h.major, sub_major_head=h.sub_major)
            label = h.label
        elif h.kind in ("mh_total", "major"):
            sid = f"fa{st}.{h.major}.total"
            code = f"mh{h.major}.total"
            dims = _dim_other(major_head=h.major)
            label = h.label if h.kind == "mh_total" else f"Total {h.label}"
        else:  # section_total
            s = slug(re.sub(r"^[–—\-\s]+", "", h.label))
            sections[s] += 1
            if sections[s] > 1:
                s = f"{s}.after_mh{h.major}"
            sid = f"fa{st}.section.{s}"
            code = f"section.{s}"
            dims = None
            label = f"TOTAL {h.label}"
        rows.append(
            _row(
                series_id=sid,
                source_id=CGA,
                table_id=table_id,
                item_code=code,
                item_label=clean_label(label) or code,
                institution="G_CEN",
                side=side,
                dim_other=dims,
                period=FA_YEAR,
                value=round(h.value * 1e-4, 4),
                vintage=FA_VINTAGE,
                estimate_stage="Audited",
                prov_id=prov[key],
            )
        )
    _check_unique(rows, f"FA Statement {st}")
    name = "union_fiscal_fa_receipts" if st == "8" else "union_fiscal_fa_expenditure"
    desc = (
        "Union Finance Accounts 2023-24 St 8: receipts by minor/sub-major/major head (audited)"
        if st == "8"
        else "Union Finance Accounts 2023-24 St 9: revenue expenditure by minor head, capital by major head (audited)"
    )
    return Dataset(name, pl.DataFrame(rows, infer_schema_length=None), desc)


# ---------------------------------------------------------------------------------------------
# Receipt Budget tax / non-tax
# ---------------------------------------------------------------------------------------------


_GLUED = re.compile(r"(?<=[a-z])(?=[A-Z])")


def _unglue(label: str) -> str:
    """Repair words the PDF text layer glues together ('OtherRural Development Programme', 'Oil
    andOil Seeds', 'SpecialAdditional Excise Duties'). No Receipt Budget label has a lower-case
    letter followed by a capital as printed (checked on all three vintages)."""
    return _GLUED.sub(" ", label)


def _rb_key_label(label: str) -> str:
    lab = _unglue(label)
    return LABEL_ALIASES.get(lab, lab)


def _rb_section_total_aliases(parsed: dict[tuple[str, str], list[B.RBRow]]) -> dict[tuple[str, str, str], str]:
    """Section totals printed 'Net-X' in one vintage and 'Total-X' in another are one series.

    The Budget 2025-26 PDF closes the non-tax sections Transport, Energy, Social Services and
    Agriculture and Allied Activities with 'Net-X'; the 2024-25 and 2026-27 xlsx close them with
    'Total-X', with the same figures in the overlapping BE columns (issues file, verify-2).
    'Net-X' is keyed as 'Total-X' only when its own file prints no 'Total-X' and another vintage of
    the same table prints 'Total-X' and no 'Net-X'. Where a file prints both (General Services,
    Economic Services) they stay two series as published."""
    labels = {k: {r.label for r in rb if r.kind == "total"} for k, rb in parsed.items()}
    out: dict[tuple[str, str, str], str] = {}
    for (tag, tab), labs in labels.items():
        for lab in sorted(labs):
            m = re.fullmatch(r"Net-(.+)", lab)
            if not m or f"Total-{m.group(1)}" in labs:
                continue
            tot = f"Total-{m.group(1)}"
            if any(t2 != tag and tb2 == tab and tot in l2 and lab not in l2 for (t2, tb2), l2 in labels.items()):
                out[(tag, tab, lab)] = tot
    return out


def _rb_dataset(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    parsed: dict[tuple[str, str], list[B.RBRow]] = {}
    for tag, (_base, _vintage, year, _release) in BUDGETS.items():
        ext = RB_FILES[tag]
        for tab, table_name in (("tr", "Tax Revenue"), ("ntr", "Non Tax Revenue")):
            raw = ctx.raw(MOF, f"{tag}_{tab}.{ext}")
            parse = B.rb_rows_pdf if ext == "pdf" else B.rb_rows_xlsx
            rb = parse(raw.path, table=table_name, actual_year=year)
            if ext == "pdf":
                for r in rb:
                    r.label = _unglue(r.label)
            parsed[(tag, tab)] = rb
    total_alias = _rb_section_total_aliases(parsed)
    for (tag, tab, lab), tot in sorted(total_alias.items()):
        ctx.log(f"Receipt Budget {tag} {tab}: section total {lab!r} keyed as {tot!r} (same line in the other vintages)")
    for tag, (_base, vintage, year, release) in BUDGETS.items():
        ext = RB_FILES[tag]
        for tab, table_name in (("tr", "Tax Revenue"), ("ntr", "Non Tax Revenue")):
            raw = ctx.raw(MOF, f"{tag}_{tab}.{ext}")
            rb = parsed[(tag, tab)]
            addends, _aggregates = B.rb_leaves(rb)
            grand = [r for r in rb if r.kind == "total" and r.label == "Grand Total"]
            if len(grand) != 1 or grand[0].value is None:
                raise ValueError(f"{tag} {tab}: expected one Grand Total, found {grand}")
            s = sum(r.value or 0.0 for r in addends)
            if abs(s - grand[0].value) > 0.05:
                raise ValueError(f"{tag} {tab}: items sum to {s:.2f}, Grand Total is {grand[0].value:.2f}")
            loc = (
                f"{raw.path.name}: pages with the '{table_name}' table, first value column 'Actual {year[:4]}-20{year[5:]}'"
                if ext == "pdf"
                else f"{raw.path.name}: sheet 'ReceiptReport123', column right of 'Major Head' ('Actuals {year[:4]}-20{year[5:]}')"
            )
            pid = ctx.prov(
                raw=raw,
                table_id=f"Receipt Budget {release[13:20]}, {table_name}",
                locator=loc + "; rows matched by item number, label and major head",
                unit_as_published="Rs crore ('In crores')",
                price_basis="current",
                vintage=vintage,
                release=release,
                notes="Site banner: Excel is system-generated; in case of inconsistency the PDF is final."
                if ext == "xlsx"
                else None,
            )
            parent_label = {r.code: r.label for r in rb if r.code}
            keys: Counter[str] = Counter()
            recs: list[tuple[str, B.RBRow]] = []
            for r in addends:
                if r.value is None:
                    continue
                k = f"{r.major_head or 'na'}.{slug(_rb_key_label(r.label))}"
                recs.append((k, r))
                keys[k] += 1
            for k, r in recs:
                if keys[k] > 1:
                    par = parent_label.get(r.code.rsplit(".", 1)[0], "")
                    k = f"{r.major_head or 'na'}.{_slug(_rb_key_label(par)) or 'top'}.{slug(_rb_key_label(r.label))}"
                rows.append(
                    _row(
                        series_id=f"rb.{tab}.{k}",
                        source_id=MOF,
                        table_id=f"Receipt Budget, {table_name}",
                        item_code=slug(_rb_key_label(r.label)),
                        item_label=r.label,
                        institution="G_CEN",
                        side="receipts",
                        dim_other=_dim_other(major_head=r.major_head),
                        period=year,
                        value=round(r.value, 2),
                        vintage=vintage,
                        estimate_stage="Actuals",
                        prov_id=pid,
                    )
                )
            seen_tot: dict[str, float] = {}
            for r in rb:
                if r.kind != "total" or r.value is None:
                    continue
                k = slug(total_alias.get((tag, tab, r.label), r.label))
                if k in seen_tot:
                    if abs(seen_tot[k] - r.value) > 0.005:
                        raise ValueError(f"{tag} {tab}: {r.label!r} printed twice with different values")
                    continue
                seen_tot[k] = r.value
                rows.append(
                    _row(
                        series_id=f"rb.{tab}.total.{k}",
                        source_id=MOF,
                        table_id=f"Receipt Budget, {table_name}",
                        item_code=k,
                        item_label=r.label,
                        institution="G_CEN",
                        side="receipts",
                        period=year,
                        value=round(r.value, 2),
                        vintage=vintage,
                        estimate_stage="Actuals",
                        prov_id=pid,
                    )
                )
    _check_unique(rows, "Receipt Budget")
    return Dataset(
        "union_fiscal_rb_receipts",
        pl.DataFrame(rows, infer_schema_length=None),
        "Receipt Budget tax and non-tax revenue tables, Actuals 2022-23, 2023-24, 2024-25 (Budgets 2024-25 to 2026-27)",
    )


# ---------------------------------------------------------------------------------------------
# AFS
# ---------------------------------------------------------------------------------------------


def _afs_dataset(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    for tag in AFS_BUDGETS:
        _base, vintage, year, release = BUDGETS[tag]
        raw = ctx.raw(MOF, f"{tag}_allafs.xlsx")
        afs = B.afs_rows(raw.path, actual_year=year)
        pids: dict[str, str] = {}
        for sheet, (key, title) in B.AFS_SHEETS.items():
            rs = [r for r in afs if r.sheet == key]
            if not rs:
                raise ValueError(f"{tag} AFS {sheet}: no rows")
            pids[key] = ctx.prov(
                raw=raw,
                table_id=f"Annual Financial Statement, {title.title()}",
                locator=f"allafs.xlsx sheet '{sheet}', column {rs[0].col} ('Actuals {year[:4]}-20{year[5:]}'), rows "
                f"{min(r.row for r in rs)}-{max(r.row for r in rs)}; rows matched by major head or English label",
                unit_as_published="Rs crore ('In Rs crores')",
                price_basis="current",
                vintage=vintage,
                release=release,
                notes="Site banner: Excel is system-generated; in case of inconsistency the PDF is final.",
            )
        for r in afs:
            rows.append(
                _row(
                    series_id=f"afs.{r.sheet}.{r.key}",
                    source_id=MOF,
                    table_id="Annual Financial Statement " + ("Statement I" if r.sheet.startswith("cfi") else "Statement III"),
                    item_code=f"{r.sheet}.{r.key}",
                    item_label=r.label,
                    institution="G_CEN",
                    side="receipts" if r.sheet.endswith("receipts") else "payments",
                    dim_other=_dim_other(major_head=r.major_head if re.fullmatch(r"\d{4}", r.major_head) else ""),
                    period=year,
                    value=round(r.value, 2),
                    vintage=vintage,
                    estimate_stage="Actuals",
                    prov_id=pids[r.sheet],
                )
            )
    # a series key must mean the same row in both vintages: same label (major-head keys aside)
    _check_unique(rows, "AFS")
    return Dataset(
        "union_fiscal_afs",
        pl.DataFrame(rows, infer_schema_length=None),
        "Annual Financial Statement I and III by major head, Actuals 2022-23 and 2023-24",
    )


# ---------------------------------------------------------------------------------------------
# Expenditure Profile statements
# ---------------------------------------------------------------------------------------------

# Spelling variants between Budget vintages that would split one series in two (key only; the
# published label is kept in item_label).
# (Glued PDF words such as 'SpecialAdditional' are repaired by _unglue, not listed here.)
LABEL_ALIASES: dict[str, str] = {}

# Expenditure Profile group headings renamed between Budget vintages (series key only; the
# published label stays in item_label). Statement 18 prints 'Transfer to ...' in Budgets 2024-25
# and 2026-27 and 'Transfers to ...' in Budget 2025-26; the lines and their items are the same.
EP_HEADING_ALIASES = {
    "transfer_to_states_other_than_i_ii": "transfers_to_states_other_than_i_ii",
    "transfer_to_delhi_puducherry_and_jammu_kashmir": "transfers_to_delhi_puducherry_and_jammu_kashmir",
}

_ENUM = re.compile(r"^(?:\d+|[IVX]+)\.\s+")


def _ep_level(st: str, r: B.EPRow) -> str:
    """'heading': the top-level groups, which (without the Grand Total) add up to the Grand Total in
    every statement; 'department': Statement 21's numbered department headings under a ministry
    heading (they add up to the Grand Total too); 'item'; 'subitem': a '4.01' line that is part of
    the item above it (items alone add up to the Grand Total)."""
    if r.is_group:
        if st == "stat21" and r.label != "Grand Total" and re.match(r"^\d+\.\s", r.label):
            return "department"
        return "heading"
    return "subitem" if r.sub_item else "item"


def _ep_dataset(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    counterparty = {"stat18": "G_STA", "stat20": "ROW", "stat21": "ROW"}
    for tag, (_base, vintage, year, release) in BUDGETS.items():
        for st, (title, src, stname) in EP_STATS.items():
            raw = ctx.raw(src, f"{tag}_{st}.xlsx")
            ep = B.ep_rows(raw.path, actual_year=year, title=title)
            if not ep:
                raise ValueError(f"{tag} {st}: no rows")
            pid = ctx.prov(
                raw=raw,
                table_id=f"Expenditure Profile, {stname}",
                locator=f"{st}.xlsx first sheet, 'Actuals {year[:4]}-20{year[5:]}' column(s) "
                f"{', '.join(sorted({r.col for r in ep}))}, rows {min(r.row for r in ep)}-{max(r.row for r in ep)}; "
                "rows matched by heading and item label",
                unit_as_published="Rs crore ('In Rs Crores')",
                price_basis="current",
                vintage=vintage,
                release=release,
                notes="Site banner: Excel is system-generated; in case of inconsistency the PDF is final.",
            )
            seen: Counter[str] = Counter()
            for r in ep:
                lab = _slug(_ENUM.sub("", r.label)) or "row"
                grp = EP_HEADING_ALIASES.get(g := _slug(_ENUM.sub("", r.group)), g)
                level = _ep_level(st, r)
                if level == "heading":
                    lab = EP_HEADING_ALIASES.get(lab, lab)
                if level == "department":
                    # Statement 21 prints each ministry ('Ministry of Home Affairs') and, under it, its
                    # numbered departments ('28. Ministry of Home Affairs', '29. Cabinet'); both add up to
                    # the Grand Total, so departments get their own level and name space (verify-1).
                    base = f"{st}.dept.{lab}"
                    code = f"dept.{lab}"
                elif r.is_group or not grp:
                    base, code = f"{st}.{lab}", lab
                else:
                    base, code = f"{st}.{grp}.{lab}", f"{grp}.{lab}"
                sid = base + (f".{r.component}" if r.component else "")
                seen[sid] += 1
                if seen[sid] > 1:
                    if not r.number:
                        raise ValueError(f"{tag} {st}: heading {r.label!r} printed twice at the same level")
                    sid = f"{base}.n{_slug(r.number)}" + (f".{r.component}" if r.component else "")
                if level == "subitem":
                    label = f"{r.number} {r.label}"  # as printed: '4.01 Contribution for hoisting ...'
                elif r.is_group or not r.group:
                    label = r.label
                else:
                    label = f"{r.label} [{r.group}]"
                rows.append(
                    _row(
                        series_id=sid,
                        source_id=src,
                        table_id=f"Expenditure Profile, {stname}",
                        item_code=code,
                        item_label=label,
                        institution="G_CEN",
                        counterparty=counterparty.get(st),
                        side="payments",
                        dim_other=_dim_other(component=r.component, level=level),
                        period=year,
                        value=round(r.value, 2),
                        vintage=vintage,
                        estimate_stage="Actuals",
                        prov_id=pid,
                    )
                )
    _check_unique(rows, "Expenditure Profile")
    return Dataset(
        "union_fiscal_exp_profile",
        pl.DataFrame(rows, infer_schema_length=None),
        "Expenditure Profile Statements 1, 7, 18, 20, 21, Actuals 2022-23 to 2024-25",
    )


# ---------------------------------------------------------------------------------------------
# NSSF (Receipt Budget Annex 8)
# ---------------------------------------------------------------------------------------------

_A8_SECTIONS = [
    ("Savings Deposits", "savings_deposits"),
    ("Savings Certificates", "savings_certificates"),
    ("Public Provident Fund", "ppf"),
    ("31.3.1999", "special_cgs_pre1999_balances"),
    ("collection from 1.4.99", "special_cgs_post1999"),
    ("1.4.99 onwards", "special_sgs_post1999"),
    ("Central/State Government Securities", "reinvestment_of_redemptions"),
    ("Investment in Public Agencies", "public_agencies"),
]


def _a8_section(section: str) -> str | None:
    """Section code; the lettered public-agency sub-blocks ('(b)Investment in Talcher Fertilizers
    Ltd.', '(d)Others') change from year to year and are keyed by their name."""
    m = re.search(r"\([a-z]\)\s*(?:Investment in\s+)?(.+)$", section)
    if m:
        return "public_agencies_" + slug(m.group(1))
    return next((c for k, c in _A8_SECTIONS if k in section), None)
_A8_TOTALS = {
    "TOTAL DEPOSITS": "total_deposits",
    "Net collection during the year": "net_collection",
    "TOTAL INVESTMENTS": "total_investments",
    "Accumulated balance Income(-)/Expenditure(+) Account": "accumulated_income_expenditure_balance",
    "Cash Balance": "cash_balance",
    "Total": "total",
}


def _a8_line(label: str) -> tuple[str, str]:
    lo = label.lower()
    if "as on 1st april" in lo or "opening balance" in lo:
        return "opening", "stock_open"
    if lo.startswith("accretion") or lo.startswith("additional investment") or lo.startswith("additions"):
        return "additions", "flow"
    if "redemption" in lo or "repayment" in lo:
        return "reductions", "flow"
    raise ValueError(f"Annex 8: unmapped line {label!r}")


def _nssf_dataset(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    for tag in ANNEX8_BUDGETS:
        _base, vintage, year, release = BUDGETS[tag]
        raw = ctx.raw(MOF, f"{tag}_annex8.pdf")
        a8 = B.annex8_rows(raw.path, actual_year=year)
        pid = ctx.prov(
            raw=raw,
            table_id="Receipt Budget Annex 8, Sources and application of National Small Savings Fund",
            locator=f"annex8.pdf page 1, column 'Actual {year[:4]}-20{year[5:]}'; rows matched by section and label",
            unit_as_published="Rs crore (Receipt Budget)",
            price_basis="current",
            vintage=vintage,
            release=release,
        )
        y0 = int(year[:4])
        for r in a8:
            if r.label in _A8_TOTALS:
                code = _A8_TOTALS[r.label]
                sf = "flow" if code == "net_collection" else "stock"
                period, ptype = (year, "fy") if sf == "flow" else (f"{y0 + 1}-03-31", "date")
                sid = f"nssf.{code}"
            else:
                sec = _a8_section(r.section)
                if sec is None:
                    raise ValueError(f"Annex 8 ({tag}): unmapped section {r.section!r}")
                what, kind = _a8_line(r.label)
                sf = "stock" if kind == "stock_open" else "flow"
                # an opening stock 'as on 1st April' is the stock at close of the previous 31 March,
                # the same date as the previous year's closing totals (one date per stock)
                period, ptype = (f"{y0}-03-31", "date") if sf == "stock" else (year, "fy")
                sid = f"nssf.{sec}.{what}"
                code = f"{sec}.{what}"
            rows.append(
                _row(
                    series_id=sid,
                    source_id=MOF,
                    table_id="Receipt Budget Annex 8 (NSSF)",
                    item_code=code,
                    item_label=clean_label(f"{r.label} [{r.section.split(': ', 1)[-1]}]")
                    if r.label not in _A8_TOTALS
                    else r.label,
                    institution="G_CEN",
                    instrument="small_savings",
                    stock_flow=sf,
                    period=period,
                    period_type=ptype,
                    value=round(r.value, 2),
                    vintage=vintage,
                    estimate_stage="Actuals",
                    prov_id=pid,
                )
            )
    _check_unique(rows, "Annex 8")
    return Dataset(
        "union_fiscal_nssf",
        pl.DataFrame(rows, infer_schema_length=None),
        "National Small Savings Fund sources and application (Receipt Budget Annex 8), 2023-24 and 2024-25",
    )


# ---------------------------------------------------------------------------------------------
# PPAC and NSI
# ---------------------------------------------------------------------------------------------


def _ppac_dataset(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(PPAC, "ppac_contribution_to_exchequer.xls")
    pr, vintage = O.ppac_rows(raw.path)
    if vintage != "2026-07-17":
        ctx.warn(f"PPAC table posted {vintage} (expected 17.07.2026): re-check the anchor values")
    rel = f"PPAC, Contribution of Petroleum Sector to Exchequer (table posted {vintage})"
    pid = ctx.prov(
        raw=raw,
        table_id="PPAC, Contribution of Petroleum Sector to Exchequer (sheet 'Anx 1')",
        locator=f"sheet 'Anx 1', rows {min(r.row for r in pr)}-{max(r.row for r in pr)}, year columns "
        f"{min(r.col for r in pr)}:{max(r.col for r in pr)} (2014-15 .. 2025-26 (P))",
        unit_as_published="Rs crore ('(Rs. Crore)')",
        price_basis="current",
        vintage=vintage,
        release=rel,
        notes="Cells hold binary floats (e.g. 14514.189999999999); values rounded to 2 decimals as displayed.",
    )
    inst = {"centre": "G_CEN", "states": "G_STA", "all": None}
    rows = [
        _row(
            series_id=f"ppac.{r.block}.{r.part}.{r.code}",
            source_id=PPAC,
            table_id="PPAC Contribution of Petroleum Sector to Exchequer",
            item_code=f"{r.part}.{r.code}",
            item_label=r.label,
            institution=inst[r.block],
            industry="petroleum_sector",
            side="receipts",
            period=r.period,
            value=r.value,
            vintage=vintage,
            estimate_stage="Provisional" if r.provisional else "n.a.",
            prov_id=pid,
        )
        for r in pr
    ]
    _check_unique(rows, "PPAC")
    return Dataset(
        "union_fiscal_ppac_exchequer",
        pl.DataFrame(rows, infer_schema_length=None),
        "PPAC petroleum sector contribution to Central and State exchequer, 2014-15 to 2025-26 (P)",
    )


def _nsi_dataset(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(NSI, "nsi_collections_id152.html")
    nr = O.nsi_rows(raw.path)
    pid = ctx.prov(
        raw=raw,
        table_id="NSI, Collection under National Savings Schemes (InternalPage Id_Pk=152)",
        locator=f"HTML table 'Year | Gross(Deposit) | Withdrawal | Net', table rows {min(r.row for r in nr)}-"
        f"{max(r.row for r in nr)}",
        unit_as_published="Rs crore ('Rs. In Crores')",
        price_basis="current",
        vintage=NSI_VINTAGE,
        release="National Savings Institute web table (undated; latest row 2025-26), retrieved from nsiindia.gov.in",
        notes="The page carries no publication date; vintage set to the year of the latest row's publication (2026).",
    )
    rows = [
        _row(
            series_id=f"nsi.{r.item}",
            source_id=NSI,
            table_id="NSI Collection under National Savings Schemes",
            item_code=r.item,
            item_label=r.label,
            institution="G_CEN",
            instrument="small_savings",
            period=r.period,
            value=r.value,
            vintage=NSI_VINTAGE,
            estimate_stage="n.a.",
            prov_id=pid,
        )
        for r in nr
    ]
    _check_unique(rows, "NSI")
    return Dataset(
        "union_fiscal_nsi_collections",
        pl.DataFrame(rows, infer_schema_length=None),
        "NSI collections under National Savings Schemes (gross, withdrawals, net), 2002-03 to 2025-26",
    )


# ---------------------------------------------------------------------------------------------
# Expenditure Profile Statement 6: grants for creation of capital assets (GCCA)
# ---------------------------------------------------------------------------------------------


def _gcca_dataset(ctx: BuildContext) -> Dataset:
    """Statement 6 by ministry, demand and item, Actuals column of each Budget. Closure checks on
    all four printed value columns (Actuals, BE, RE, BE): items = their demand line, demands =
    their ministry line, ministries = Grand Total, to 0.015 crore."""
    rows: list[dict[str, Any]] = []
    for tag, (_base, vintage, year, release) in BUDGETS.items():
        raw = ctx.raw(MOF, f"{tag}_stat6.xlsx")
        s6 = B.stat6_rows(raw.path, actual_year=year)
        _stat6_closures(s6, f"{tag} Statement 6")
        pid = ctx.prov(
            raw=raw,
            table_id="Expenditure Profile, Statement 6",
            locator=f"stat6.xlsx first sheet, 'Actuals {year[:4]}-20{year[5:]}' column {s6[0].col}, rows "
            f"{min(r.row for r in s6)}-{max(r.row for r in s6)}; rows matched by ministry, 'Demand No.' line, "
            "department heading and item label",
            unit_as_published="Rs crore ('In Rs Crores')",
            price_basis="current",
            vintage=vintage,
            release=release,
            notes="Object head 'Grants for creation of capital assets' (GCCA), all grantees (States, UTs, "
            "autonomous bodies, PSUs, others); the statement does not split by grantee. "
            "Site banner: Excel is system-generated; in case of inconsistency the PDF is final.",
        )
        n_demands: Counter[str] = Counter(r.ministry for r in s6 if r.level == "demand")
        keyed: list[tuple[str, str, B.S6Row]] = []
        for r in s6:
            m = slug(r.ministry) if r.ministry else ""
            if r.level == "total":
                keyed.append(("stat6.grand_total", "grand_total", r))
            elif r.level == "ministry":
                keyed.append((f"stat6.ministry.{m}", f"ministry.{m}", r))
            elif r.level == "demand":
                sub = "" if n_demands[r.ministry] == 1 else "." + (_slug(r.department) or f"d{r.demand}")
                keyed.append((f"stat6.demand.{m}{sub}", f"demand.{m}{sub}", r))
            else:
                keyed.append((f"stat6.item.{m}.{slug(r.label)}", f"item.{m}.{slug(r.label)}", r))
        clash = Counter(k for k, _c, _r in keyed)
        for sid, code, r in keyed:
            if clash[sid] > 1:  # the same item label under two demands of one ministry
                dept = _slug(r.department) or f"d{r.demand}"
                sid = f"stat6.item.{slug(r.ministry)}.{dept}.{slug(r.label)}"
                code = f"item.{slug(r.ministry)}.{dept}.{slug(r.label)}"
            if r.level == "item":
                label = f"{r.number}. {r.label} [Demand No. {r.demand}: {r.department or r.ministry}]"
            elif r.level == "demand":
                label = f"Demand No. {r.demand} [{r.department or r.ministry}]"
            else:
                label = r.label
            rows.append(
                _row(
                    series_id=sid,
                    source_id=MOF,
                    table_id="Expenditure Profile, Statement 6",
                    item_code=code,
                    item_label=label,
                    institution="G_CEN",
                    side="payments",
                    dim_other=_dim_other(level=r.level),
                    period=year,
                    value=round(r.values[0], 2),
                    vintage=vintage,
                    estimate_stage="Actuals",
                    prov_id=pid,
                )
            )
    _check_unique(rows, "Statement 6")
    return Dataset(
        "union_fiscal_gcca",
        pl.DataFrame(rows, infer_schema_length=None),
        "Expenditure Profile Statement 6, grants for creation of capital assets by ministry/demand/item, "
        "Actuals 2022-23 to 2024-25",
    )


def _stat6_closures(s6: list[B.S6Row], what: str) -> None:
    def close(parts: list[B.S6Row], total: B.S6Row, name: str) -> None:
        for k in range(4):
            got = sum(p.values[k] for p in parts)
            if abs(got - total.values[k]) > 0.015:
                raise ValueError(f"{what}: {name} column {k}: parts {got:.2f} != printed {total.values[k]:.2f}")

    gt = [r for r in s6 if r.level == "total"]
    ministries = [r for r in s6 if r.level == "ministry"]
    demands = [r for r in s6 if r.level == "demand"]
    items = [r for r in s6 if r.level == "item"]
    close(ministries, gt[0], "ministries vs Grand Total")
    for mn in ministries:
        close([d for d in demands if d.ministry == mn.ministry], mn, f"demands of {mn.ministry!r}")
    for d in demands:
        its = [x for x in items if x.ministry == d.ministry and x.demand == d.demand]
        if not its:
            raise ValueError(f"{what}: Demand No. {d.demand} ({d.ministry}) has no items")
        close(its, d, f"items of Demand No. {d.demand}")


# ---------------------------------------------------------------------------------------------
# Finance Accounts: Appendix to Statement 9 (grants-in-aid by grantee) and Statement 14 (funds)
# ---------------------------------------------------------------------------------------------

_GIA_MEASURE_LABELS = {
    ("cash", "total"): "total funds released as grants-in-aid",
    ("cash", "capital_assets"): "funds allocated for creation of capital assets",
    ("in_kind", "total"): "total value of grants-in-aid in kind",
    ("in_kind", "capital_assets"): "grants-in-aid in kind being capital assets in nature",
}
_GIA_TITLES = {
    "cash": "'Details of Total Funds released during the Year 2023-24 as Grants-in-aid and Funds allocated for "
    "Creation of Assets', columns 2 (total grants-in-aid released) and 3 (of which for creation of capital assets)",
    "in_kind": "'Details of Total value of grants-in-aid in kind released during the Year 2023-24 and value of "
    "Grants-in-aid in kind being Capital Assets in Nature', columns 2 and 3",
}


def _fa_gia_dataset(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(CGA, "fa2324_statement9_appendix.pdf")
    gia = FO.gia_rows(raw.path, year=FA_YEAR)
    pids: dict[str, str] = {}
    for table in ("cash", "in_kind"):
        page = next(r.page for r in gia if r.table == table)
        pids[table] = ctx.prov(
            raw=raw,
            table_id="Finance Accounts 2023-24, Appendix to Statement No. 9 (IGAS-2)",
            locator=f"PDF page {page}, table {_GIA_TITLES[table]}; rows matched by English grantee category",
            unit_as_published="Rs lakh ('Rupees in lakhs')",
            conversion=conversion_note("INR_lakh"),
            price_basis="current",
            vintage=FA_VINTAGE,
            release=FA_RELEASE,
            notes=FA_VINTAGE_NOTE,
        )
    rows: list[dict[str, Any]] = []
    for r in gia:
        for measure, v in (("total", r.total), ("capital_assets", r.capital)):
            rows.append(
                _row(
                    series_id=f"gia.{r.table}.{r.category}.{measure}",
                    source_id=CGA,
                    table_id="Finance Accounts 2023-24, Appendix to Statement No. 9 (IGAS-2)",
                    item_code=f"{r.table}.{measure}",
                    item_label=f"{r.label}: {_GIA_MEASURE_LABELS[(r.table, measure)]}",
                    institution="G_CEN",
                    side="payments",
                    dim_other=_dim_other(grantee=r.category, form=r.table, measure=measure),
                    period=FA_YEAR,
                    value=round(v * 0.01, 4),
                    vintage=FA_VINTAGE,
                    estimate_stage="Audited",
                    prov_id=pids[r.table],
                )
            )
    _check_unique(rows, "FA Appendix to Statement 9")
    return Dataset(
        "union_fiscal_fa_gia",
        pl.DataFrame(rows, infer_schema_length=None),
        "Union Finance Accounts 2023-24, grants-in-aid released by category of grantee and the part for creation "
        "of capital assets (IGAS-2 disclosure, audited)",
    )


FA14_INSTRUMENT = {"8009": "provident_funds", "8011": "insurance_and_pension_funds", "8014": "postal_life_insurance"}
_FA14_MEASURES = (
    # measure, value index, stock/flow, period, period type, side, printed column
    ("balance", 0, "stock", "2023-03-31", "date", "liabilities", "amount on 1st April 2023"),
    ("balance", 3, "stock", "2024-03-31", "date", "liabilities", "amount on 31st March 2024"),
    ("additions", 1, "flow", FA_YEAR, "fy", "receipts", "additions during the year"),
    ("discharges", 2, "flow", FA_YEAR, "fy", "payments", "discharges during the year"),
)


def _fa_pf_dataset(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(CGA, "fa2324_statement14.pdf")
    st = FO.st14_rows(raw.path)
    prov: dict[int, str] = {}
    rows: list[dict[str, Any]] = []
    for r in st:
        if r.page not in prov:
            prov[r.page] = ctx.prov(
                raw=raw,
                table_id="Finance Accounts 2023-24, Statement No. 14",
                locator=f"Statement No. 14 (debts and other interest bearing obligations), section I 'Small Savings, "
                f"Provident Funds etc.', printed page {r.printed_page} (PDF page {r.page}); columns 2-5 'Amount on "
                "1st April, 2023', 'Additions during the year', 'Discharges during the year', 'Amount on 31st March, "
                "2024'; rows matched by head-of-account codes",
                unit_as_published="Rs thousand ('In thousands of rupees')",
                conversion=conversion_note("INR_thousand"),
                price_basis="current",
                vintage=FA_VINTAGE,
                release=FA_RELEASE,
                notes=FA_VINTAGE_NOTE
                + " The opening amount 'on 1st April, 2023' is dated 2023-03-31 (one date per stock).",
            )
        if r.kind == "minor":
            base, code = f"fa14.{r.major}.{r.sub_major}.{r.minor}", f"mh{r.major}.{r.sub_major}.{r.minor}"
            dims = {"major_head": r.major, "sub_major_head": r.sub_major, "minor_head": r.minor}
            label = f"{r.label} [{r.sub_major_label}]" if r.sub_major_label else r.label
        elif r.kind == "sm_total":
            base, code = f"fa14.{r.major}.{r.sub_major}.total", f"mh{r.major}.{r.sub_major}.total"
            dims = {"major_head": r.major, "sub_major_head": r.sub_major}
            label = f"{r.label} [{r.sub_major_label}]"
        else:
            base, code = f"fa14.{r.major}.total", f"mh{r.major}.total"
            dims = {"major_head": r.major}
            label = r.label
        for measure, k, sf, period, ptype, side, when in _FA14_MEASURES:
            rows.append(
                _row(
                    series_id=f"{base}.{measure}",
                    source_id=CGA,
                    table_id="Finance Accounts 2023-24, Statement No. 14",
                    item_code=f"{code}.{measure}",
                    item_label=clean_label(f"{label}: {when}"),
                    institution="G_CEN",
                    instrument=FA14_INSTRUMENT[r.major],
                    side=side,
                    stock_flow=sf,
                    dim_other=_dim_other(**dims),
                    period=period,
                    period_type=ptype,
                    value=round(r.values[k] * 1e-4, 4),
                    vintage=FA_VINTAGE,
                    estimate_stage="Audited",
                    prov_id=prov[r.page],
                )
            )
    _check_unique(rows, "FA Statement 14")
    return Dataset(
        "union_fiscal_fa_provident_funds",
        pl.DataFrame(rows, infer_schema_length=None),
        "Union Finance Accounts 2023-24 St 14: State Provident Funds (GPF), Insurance and Pension Funds and Postal "
        "Life Insurance, balances and gross additions/discharges (audited)",
    )


# ---------------------------------------------------------------------------------------------
# PIB monthly GST releases
# ---------------------------------------------------------------------------------------------

# Releases pinned before www.pib.gov.in served a bot challenge (2026-09-29, union_fiscal-1). The
# build reads exactly these; fetch keeps trying the rest of GST_MONTHS on later online runs.
PIB_MONTHS_PINNED = [(2023, 4), (2023, 5)]


def _pib_gst_dataset(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    for y, m in PIB_MONTHS_PINNED:
        raw = ctx.raw(PIB, f"pib_gst_{y}-{m:02d}.html")
        rel = P.release(raw.path, year=y, month=m)
        release = f"PIB (Ministry of Finance) release {rel.prid}, posted {rel.posted}: {rel.title[:160]}"
        pid_h = ctx.prov(
            raw=raw,
            table_id=f"PIB GST collections release {rel.prid}",
            locator="release text, the paragraph beginning 'The gross ... revenue collected in the month of "
            f"{calendar.month_name[m]}, {y} is' (headline figures)",
            unit_as_published="Rs crore (release text)",
            price_basis="current",
            vintage=rel.posted,
            release=release,
            notes="Provisional monthly cash collections as released. Gross = CGST + SGST + IGST + cess (checked to 2 "
            "crore); post-settlement CGST/SGST = collections + IGST settled to each (checked).",
        )
        mon_prev = f"{calendar.month_abbr[m]}-{str(y - 1)[2:]}"
        mon_cur = f"{calendar.month_abbr[m]}-{str(y)[2:]}"
        pid_t = ctx.prov(
            raw=raw,
            table_id=f"PIB GST collections release {rel.prid}, table 'State-wise growth of GST Revenues'",
            locator=f"table 'State/UT | {mon_prev} | {mon_cur} | Growth (%)', rows by State/UT name "
            "(Growth column not ingested)",
            unit_as_published="Rs crore (release text)",
            price_basis="current",
            vintage=rel.posted,
            release=release,
            notes="Footnote [1]: does not include GST on import of goods. The previous-year column is as printed "
            "in this release. Rows add up to the printed Grand Total (checked).",
        )
        for k in P.HEADLINE:
            rows.append(
                _row(
                    series_id=f"pib.gst.{k}",
                    source_id=PIB,
                    table_id="PIB monthly GST release (text)",
                    item_code=k,
                    item_label=k.replace("_", " "),
                    side="receipts",
                    period=rel.month,
                    period_type="month",
                    value=rel.headline[k],
                    vintage=rel.posted,
                    estimate_stage="Provisional",
                    prov_id=pid_h,
                )
            )
        for name, month, v, _where in rel.state_month:
            if name in P.GST_TOTAL_ROWS:
                key = P.GST_TOTAL_ROWS[name]
                geo_code, dims = "IN", _dim_other(gst_jurisdiction=key)
            else:
                geo_code = state_code(name)
                key, dims = geo_code.lower(), None
            rows.append(
                _row(
                    series_id=f"pib.gst_domestic_by_state.{key}",
                    source_id=PIB,
                    table_id="PIB monthly GST release, State-wise GST revenues (excl. imports of goods)",
                    item_code="gst_domestic_collections",
                    item_label=f"GST collected in {name} (excluding GST on import of goods)",
                    geography=geo_code,
                    side="receipts",
                    dim_other=dims,
                    period=month,
                    period_type="month",
                    value=v,
                    vintage=rel.posted,
                    estimate_stage="Provisional",
                    prov_id=pid_t,
                )
            )
    _check_unique(rows, "PIB GST")
    return Dataset(
        "union_fiscal_pib_gst",
        pl.DataFrame(rows, infer_schema_length=None),
        "PIB monthly GST collection releases (headline split and State-wise domestic collections), April-May 2023",
    )


def build(ctx: BuildContext) -> list[Dataset]:
    return [
        _fa_dataset(ctx, "8"),
        _fa_dataset(ctx, "9"),
        _rb_dataset(ctx),
        _afs_dataset(ctx),
        _ep_dataset(ctx),
        _nssf_dataset(ctx),
        _ppac_dataset(ctx),
        _nsi_dataset(ctx),
        _gcca_dataset(ctx),
        _fa_gia_dataset(ctx),
        _fa_pf_dataset(ctx),
        _pib_gst_dataset(ctx),
    ]
