"""EPFO Annual Reports 2023-24 and 2024-25 (PDF text layer): parsers.

Both reports are kept as two vintages of one dataset, so the revision of 2023-24 between them is
visible (e.g. EPF contributions 2,26,198.57 cr in AR 2023-24 vs 2,33,489.80 cr in AR 2024-25).
Pages are pinned by number for each report and every page must contain its anchor text; values
are read with anchored regular expressions and every expected item must be found exactly once.

AR 2024-25's EPF contribution for 2024-25 includes Rs 7,320.22 cr of central 'Past Accumulation'
(transfers of existing balances from exempted PF trusts, not contributions; the zonal figures may hold
more, unpublished); its EPS payment includes central 'CPPS' 6,813.22 (pensions paid through the new
Centralised Pension Payment System) and an unexplained 'Adjustment of Pension Disbursement Savings A/c
Balance' 381.88. See PAST_ACC_2425, APP5I_CENTRAL_NOTE and the issues file (finsector_markets-5, -37).
Appendix-5(i) totals are checked against their zone rows plus these central lines at build time.
App. 5(i) 'Total EPS contribution' / 'Total contribution' exclude the Central Government's EPS share
(govt_share_note; build-checked).

The EPS outgo table (AR 2023-24 para 2.15 'EPS Payments'; AR 2024-25 para 2.16 Table 5) is a second dataset,
finsector_markets_epfo_eps_outgo: Pension Disbursed vs Withdrawal Benefits, 2019-20..2024-25. Its totals do not tie
to the para 5.5 / App. 5(i) EPS payment before 2024-25 (excess 38-382 cr, unexplained; build-checked, issue -37).

Coverage: un-exempted sector only (EPFO-managed funds). Exempted establishments' own PF trusts
are not in these tables apart from AR 2023-24 para 5.22 (investments made during the year).
The Consolidated Annual Accounts (audited) are not ingested (latest 2022-23; see issues file).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pypdf

from pipeline.core.unit import BuildContext, Dataset, RawFile
from pipeline.core.units import normalize_fy, parse_number

from .common import Rows, frame

SRC = "epfo_annual_report_accounts"


@dataclass(frozen=True)
class Report:
    raw: str
    fy: str  # the report year
    vintage: str
    release: str
    pages: dict[str, tuple[int, ...]]  # section -> 1-based PDF page numbers
    anchors: dict[str, str]  # section -> text that must appear on the first page of the section


AR2324 = Report(
    raw="epfo_annual_report_2023_24.pdf",
    fy="2023-24",
    vintage="2024-12",
    release="EPFO Annual Report 2023-24 (PDF created 14 Dec 2024; figures for 2023-24 marked unaudited)",
    pages={"contrib": (84,), "fiveyear": (85,), "invest": (92, 93, 94, 95, 96), "exempted": (98, 99),
           "app5i": (235,), "rates": (241,), "eps_outgo": (39,)},
    anchors={"contrib": "CONTRIBUTIONS RECEIVED (ALL THREE SCHEMES)", "fiveyear": "PROVIDENT FUND CONTRIBUTIONS RECEIVED",
             "invest": "Corpus and Category wise breakup of Investments", "exempted": "INVESTMENTS MADE BY EXEMPTED",
             "app5i": "Contribution and Payment of all three Schemes", "rates": "Rate of Interest on EPF balances",
             "eps_outgo": "EPS Fund - Receipts, Payments and Corpus"},
)
AR2425 = Report(
    raw="epfo_annual_report_2024_25.pdf",
    fy="2024-25",
    vintage="2026-02",
    release="EPFO Annual Report 2024-25 (PDF created 27 Feb 2026; figures for 2024-25 marked un-audited)",
    pages={"contrib": (78,), "fiveyear": (78,), "invest": (85, 86, 87, 88, 89, 90, 91), "app5i": (236,),
           "rates": (242,), "eps_outgo": (40, 41)},
    anchors={"contrib": "CONTRIBUTIONS RECEIVED (ALL THREE SCHEMES)",
             "fiveyear": "CONTRIBUTION AND PAYMENT OF ALL THREE SCHEMES (UNEXEMPTED)",
             "invest": "Corpus and Category wise breakup of Investments",
             "app5i": "Contribution and Payment of all three Schemes", "rates": "Rate of Interest on EPF balances",
             "eps_outgo": "EPS Fund- Receipts, Payments and Corpus"},
)

PAST_ACC_2425 = (
    "AR 2024-25 EPF contribution 2024-25 (2,58,132.93) INCLUDES 'Past Accumulation of Rs. 7,320.22 Crore which is "
    "accounted for at the Central level' (para 5.4 footnote, p.78; 'Past Accumulation 7,320.22' line in App. 5(i), "
    "p.236, whose note says the figures 'include the Contributions, Securities received on cancellation of exemption "
    "and Past accumulations'). Past accumulations are PF balances transferred from exempted establishments' own "
    "trusts on cancellation or surrender of exemption ('the employer has the responsibility to transfer the entire "
    "corpus to the accounts of the Central Board of Trustees, EPF', PDF p.68), not new contributions: for S9 subtract "
    "7,320.22 and treat it as a transfer inside the funded-pension sector. That is a lower bound on the correction: "
    "the note covers the zone rows too, so the zonal EPF sum 2,50,812.70 may also hold such transfers (not published) "
    "and is an upper bound on new EPF contributions 2024-25 (Phase 2 uncertainty on S9). Context only: an online "
    "surrender-of-exemption module launched 13.08.2024 (PDF p.70) and an 'Online System for Surrender of Exemption "
    "and Transfer of Past Accumulations' (PDF p.137); the report does not say why only 2024-25 has a central line."
)
PAST_ACC_2324_REV = (
    " The 2023-24 row (2,33,489.80; total 2,99,271.83) exceeds AR 2023-24's 2,26,198.57 (total 2,91,980.60) by "
    "7,291.23, all in EPF; AR 2023-24 App. 5(i) has no past-accumulation line, so the revision is probably the "
    "2023-24 central past accumulation (not stated in either report; not verified)."
)
APP5I_2324_NOTE = (
    "AR 2023-24 App. 5(i) prints no 'Past Accumulation' line (compare AR 2024-25), no central line of any kind and no "
    "note on transfers: its 22 zone rows add to 'Total' in all 8 columns (checked at build time, within Rs 0.05 cr). "
    "The report does not say whether zonal EPF contributions 2,26,198.57 include securities or past accumulations "
    "received from exempted trusts; AR 2024-25 revises 2023-24 EPF contributions to 2,33,489.80 (+7,291.23), "
    "cause not stated. App. 5(i) EPS payment 2023-24 (23,410.17, pensions and withdrawal benefits) exceeds the "
    "report's own EPS outgo table (para 2.15 'EPS Payments', PDF p.39: Pension Disbursed 15,130.68 + Withdrawal "
    "Benefits 7,908.25 = 23,038.94; dataset finsector_markets_epfo_eps_outgo) by 371.23; the report does not explain "
    "the difference (Phase 2 uncertainty on S9; the build asserts it)."
)
# AR 2024-25 App. 5(i) (PDF p.236): the lines printed between the 22 zone rows and 'Total', with the column(s) they
# sit in (from the text positions on the rotated page). The build asserts each line and that Total = zones + these.
APP5I_CENTRAL_2425 = (  # (label regex, value, column indices 0..7 it is added to)
    (r"Past Accumulation 7,320\.22\*\* 7,320\.22", 7320.22, (0, 6)),  # EPF contribution, total contribution
    (r"CPPS 6813\.22 6813\.22", 6813.22, (3, 7)),  # EPS payment, total payment
    (r"Adjustment of Pension Disbursement Savings\s*\nA/c Balance\s*\n381\.88 381\.88", 381.88, (3, 7)),
    (r"Adjustments of remittances at\s*\nHead Office level\s*\n0\.19", 0.19, (2, 6)),  # EPS contribution
)
APP5I_CENTRAL_NOTE = (
    " App. 5(i) 2024-25 (PDF p.236) prints three more central lines above 'Total': 'CPPS 6813.22' and 'Adjustment "
    "of Pension Disbursement Savings A/c Balance 381.88' (EPS payment and total payment columns) and 'Adjustments of "
    "remittances at Head Office level 0.19' (EPS contribution column, by print position; included in the total "
    "contribution). EPS payment 27,963.41 = 22 zones 20,768.29 + 6,813.22 + 381.88 (+0.02); total payment "
    "1,75,909.82 = zones 1,68,714.70 + the same two; EPS contribution 73,788.40 = zones 73,788.18 + 0.19 (+0.03); "
    "total contribution 3,35,628.81 = zones 3,28,308.36 + 7,320.22 + 0.19 (+0.04) (all build-checked). CPPS is the "
    "Centralised Pension Payment System ('pan India Since Jan 2025', PDF p.45; 'fully implemented in December 2024', "
    "PDF p.136; the interim CPPS paid Rs 213.55 crore to 9,30,448 pensioners on 30 Nov 2024, PDF p.137): pensions "
    "moved from zonal to central payment, so zonal EPS payments fall from 23,410.17 (2023-24) to 20,768.29 while the "
    "total rises 19.4%; never add CPPS to the zones again. The EPS payment is pensions AND withdrawal benefits: "
    "EPFO's outgo table (para 2.16 Table 5, PDF pp.40-41; dataset finsector_markets_epfo_eps_outgo) splits 2024-25 "
    "into Pension Disbursed 18,957.86 and Withdrawal Benefits 9,005.90 (27,963.76), reconciled to 27,963.41 by a "
    "0.35 Life Assurance Benefit entry, so EPFO counts the unexplained 381.88 inside that outgo (in which part is not "
    "stated). If the 381.88 is instead a book adjustment, total EPS payments 2024-25 are 27,581.53 (not verified; "
    "Phase 2). For S9 take pensions vs withdrawal benefits from Table 5. In 2020-21..2023-24 this EPS payment exceeds "
    "the Table 5 total by 38-382 cr (371.23 in 2023-24), unexplained (see that dataset's notes). Para 5.5 prints the "
    "same 2024-25 totals without the breakdown."
)
# App. 5(i)'s EPS column is the employers' share only (verifier V14); the build asserts the identities stated here.
GOVT_SHARE = {"2023-24": (62423.93, 9356.48, "62,423.93", "9,356.48"),
              "2024-25": (73788.40, 10049.70, "73,788.40", "10,049.70")}


def govt_share_note(fy: str) -> str:
    _, _, emp, gov = GOVT_SHARE[fy]
    return (f" App. 5(i) 'Total EPS contribution' is the employers' share only ({emp}, = para 5.4 a)) and 'Total "
            "contribution' = EPF + that + EDLI: both exclude the Central Government's share of EPS (para 5.4 b), "
            f"{gov} for {fy}; series para54.eps_contribution_government), despite the word 'Total' (build-checked).")


AMOUNT = r"(\d{1,3}(?:,\d{2})*,\d{3}\.\d{2}|\d{1,3}\.\d{2}|\d+\.\d{2})"  # Indian-grouped rupee amount

SCHEMES = (  # (heading regex, code, label)
    (r"a\)\s*Employees.\s*Provident\s*Fund", "epf", "Employees' Provident Fund"),
    (r"b\)\s*Employees.\s*Pension\s*Fund", "eps", "Employees' Pension Fund"),
    (r"c\)\s*Employees.\s*Deposit\s*Linked\s*Insurance\s*Fund", "edli", "Employees' Deposit Linked Insurance Fund"),
    (r"d\)\s*Staff\s*Provident\s*Fund", "staff_pf", "Staff Provident Fund"),
    (r"e\)\s*Staff\s*Pension\s*and\s*Gratuity", "staff_pension_gratuity", "Staff Pension and Gratuity Fund"),
)
CATEGORIES = (  # (label regex, instrument code, label)
    (r"Central Govt\. Securities \(CTG\)", "central_govt_securities", "Central Govt. Securities (CTG)"),
    (r"State Development Loan \(SDL\)", "state_development_loans", "State Development Loan (SDL)"),
    (r"State Guaranteed Securities \(STG\)", "state_guaranteed_securities", "State Guaranteed Securities (STG)"),
    (r"Special Deposit Scheme \(SDS\)", "special_deposit_scheme", "Special Deposit Scheme (SDS)"),
    (r"Public Account with Central Govt\.", "public_account_central_govt", "Public Account with Central Govt."),
    (r"Corporate Bonds - PSU/PSFIs", "corporate_bonds_psu", "Corporate Bonds - PSU/PSFIs"),
    (r"Corporate Bonds -Private Sector \(PVT\)", "corporate_bonds_private", "Corporate Bonds - Private Sector (PVT)"),
    (r"ETF\(at cost Price\)", "etf_at_cost", "ETF (at cost price)"),
    (r"TREPS/LMF in hand", "treps_lmf", "TREPS/LMF in hand"),
    (r"Invits", "invits", "InvITs"),  # from AR 2024-25 only
)


def _amount(s: str) -> float:
    v = parse_number(s)
    if v is None:
        raise ValueError(f"not an amount: {s!r}")
    return v


def _text(reader: pypdf.PdfReader, rep: Report, section: str) -> str:
    pages = rep.pages[section]
    texts = [reader.pages[p - 1].extract_text() or "" for p in pages]
    if rep.anchors[section] not in texts[0]:
        raise ValueError(f"{rep.raw} page {pages[0]}: anchor {rep.anchors[section]!r} not found (report changed?)")
    return re.sub(r"[ \t ]+", " ", "\n".join(texts))


def _one(pattern: str, text: str, what: str) -> re.Match[str]:
    ms = list(re.finditer(pattern, text, flags=re.M))
    if len(ms) != 1:
        raise ValueError(f"EPFO {what}: pattern matched {len(ms)} times (expected 1): {pattern}")
    return ms[0]


class _Emit:
    def __init__(self, rows: Rows, raw: RawFile, rep: Report):
        self.rows, self.raw, self.rep = rows, raw, rep

    def prov(self, section: str, table_id: str, what: str, unit_pub: str = "Rs crore", notes: str | None = None) -> str:
        pages = self.rep.pages[section]
        return self.rows.prov(
            self.raw,
            table_id=table_id,
            locator=f"PDF page(s) {', '.join(map(str, pages))} (text layer): {what}",
            unit_as_published=unit_pub,
            release=self.rep.release,
            money=unit_pub != "per cent",
            notes=notes,
        )

    def add(self, pid, sid, table_id, code, label, value, period, *, stock=False, unit="INR_crore", stage=None, **dims):
        self.rows.add(prov_id=pid, series_id=sid, table_id=table_id, item_code=code, item_label=label, value=value,
                      unit=unit, stock_flow="stock" if stock else ("flow" if unit == "INR_crore" else "n/a"),
                      period=period, period_type="date" if stock else "fy", estimate_stage=stage, **dims)


def _contrib(e: _Emit, reader: pypdf.PdfReader) -> None:
    rep = e.rep
    t = _text(reader, rep, "contrib")
    table = "Para 5.4 (contributions received from un-exempted establishments)"
    pid = e.prov("contrib", table, f"'Contributions Received from Un-exempted Establishments' table, {rep.fy}",
                 notes=PAST_ACC_2425 if rep is AR2425 else None)
    items = (
        (r"Employees. Provident Funds Scheme " + AMOUNT, "epf_contribution", "Employees' Provident Funds Scheme", "epf"),
        (r"a\) Employers. Share " + AMOUNT, "eps_contribution_employer", "Employees' Pension Scheme: employers' share", "eps"),
        (r"b\) Government.s Share " + AMOUNT, "eps_contribution_government", "Employees' Pension Scheme: Government's share", "eps"),
        (r"Total: " + AMOUNT, "eps_contribution_total", "Employees' Pension Scheme: total", "eps"),
        (r"Insurance Scheme:\s*\n\s*Employers. Share " + AMOUNT, "edli_contribution", "Employees' Deposit Linked Insurance Scheme: employers' share", "edli"),
    )
    for pat, code, label, scheme in items:
        m = _one(pat, t, f"{rep.fy} {code}")
        e.add(pid, f"para54.{code}.current", table, code, label, _amount(m.group(1)), rep.fy, stage="Unaudited",
              institution=f"epfo_{scheme}")


def _fiveyear(e: _Emit, reader: pypdf.PdfReader) -> None:
    rep = e.rep
    t = _text(reader, rep, "fiveyear")
    if rep is AR2324:
        table = "Paras 5.5 and 5.8 (five-year PF and pension contribution tables)"
        pid = e.prov("fiveyear", table, "'PROVIDENT FUND CONTRIBUTIONS RECEIVED' (2019-20..2023-24) and the "
                     "Pension Fund five-year table (employer's and Central Govt. shares); variation % not read")
        pf = t[t.index("PROVIDENT FUND CONTRIBUTIONS RECEIVED"): t.index("Pension Fund")]
        eps = t[t.index("5.8 The following table"):]
        got_pf = re.findall(r"^(\d{4}-\d{2})\*? " + AMOUNT + r" -?\d+\.\d+\s*$", pf, flags=re.M)
        got_eps = re.findall(r"^(\d{4}-\d{2})\*? " + AMOUNT + " " + AMOUNT + r" -?\d+\.\d+\s*$", eps, flags=re.M)
        want = ["2023-24", "2022-23", "2021-22", "2020-21", "2019-20"]
        if [y for y, _ in got_pf] != want or [y for y, _, _ in got_eps] != want:
            raise ValueError(f"EPFO AR 2023-24 five-year tables: years {got_pf} / {got_eps}")
        for y, v in got_pf:
            e.add(pid, "fiveyear.epf_contribution.current", table, "epf_contribution",
                  "EPF contributions received (un-exempted sector)", _amount(v), normalize_fy(y),
                  stage="Unaudited" if y == rep.fy else None, institution="epfo_epf")
        for y, emp, gov in got_eps:
            for code, label, v in (("eps_contribution_employer", "Pension Fund: employer's share", emp),
                                   ("eps_contribution_government", "Pension Fund: Central Govt. share", gov)):
                e.add(pid, f"fiveyear.{code}.current", table, code, label, _amount(v), normalize_fy(y),
                      stage="Unaudited" if y == rep.fy else None, institution="epfo_eps")
        return
    table = "Para 5.5 (contribution and payment of all three schemes, last five years)"
    pid = e.prov("fiveyear", table, "'CONTRIBUTION AND PAYMENT OF ALL THREE SCHEMES (UNEXEMPTED)' rows "
                 "2024-25..2020-21, the eight amount columns; year-wise variation % not read",
                 notes=PAST_ACC_2425 + PAST_ACC_2324_REV + APP5I_CENTRAL_NOTE + govt_share_note(rep.fy))
    got = re.findall(r"^(\d{4}-\d{2})\*? " + " +".join([AMOUNT] * 8) + r" +-?\d+\.\d+% +-?\d+\.\d+%\s*$", t, flags=re.M)
    if [g[0] for g in got] != ["2024-25", "2023-24", "2022-23", "2021-22", "2020-21"]:
        raise ValueError(f"EPFO AR 2024-25 five-year table: years {[g[0] for g in got]}")
    cols = (("epf_contribution", "EPF contribution received", "epf"), ("epf_payment", "EPF payments", "epf"),
            ("eps_contribution_employer", "EPS contribution received (employers' share)", "eps"),
            ("eps_payment", "EPS payments", "eps"), ("edli_contribution", "EDLI contribution received", "edli"),
            ("edli_payment", "EDLI payments", "edli"), ("total_contribution", "Total contribution received", "all"),
            ("total_payment", "Total payments", "all"))
    for g in got:
        for (code, label, scheme), v in zip(cols, g[1:], strict=True):
            e.add(pid, f"fiveyear.{code}.current", table, code, label, _amount(v), g[0],
                  stage="Unaudited" if g[0] == rep.fy else None, institution=f"epfo_{scheme}")


def _check_app5i_lines(rep: Report, t: str, total: list[float]) -> None:
    """Assert what the App. 5(i) provenance notes say: Total = 22 zone rows (+ the AR 2024-25 central lines).

    Zone rows are the lines with eight amounts other than 'Total' (a zone name wrapped onto two lines keeps its
    amounts on one). A changed page (another central line, a moved value) fails the build.
    """
    zones = [[_amount(v) for v in z] for z in re.findall(r"^(?!Total )\D.*?" + " +".join([AMOUNT] * 8) + r"\s*$",
                                                          t, flags=re.M)]
    if len(zones) != 22:
        raise ValueError(f"EPFO {rep.fy} Appendix-5(i): {len(zones)} zone rows (expected 22)")
    expect = [sum(z[i] for z in zones) for i in range(8)]
    central = APP5I_CENTRAL_2425 if rep is AR2425 else ()
    for pat, value, cols in central:
        _one(r"^" + pat + r"\s*$", t, f"{rep.fy} Appendix-5(i) central line {value}")
        for i in cols:
            expect[i] += value
    if rep is AR2324 and re.search(r"Past Accumulation|CPPS|Adjustment|cancellation of exemption", t, flags=re.I):
        raise ValueError("EPFO AR 2023-24 Appendix-5(i): a central line or transfer note appeared (notes say none)")
    bad = [(i, round(total[i] - expect[i], 2)) for i in range(8) if abs(total[i] - expect[i]) > 0.05]
    if bad:
        raise ValueError(f"EPFO {rep.fy} Appendix-5(i): Total != zones + central lines in columns {bad}")


def _app5i(e: _Emit, reader: pypdf.PdfReader) -> None:
    rep = e.rep
    t = _text(reader, rep, "app5i")
    table = "Appendix-5(i) (contribution and payment of all three schemes, un-exempted)"
    pid = e.prov("app5i", table, f"Appendix-5(i) 'Total' row, {rep.fy}; the zone rows and the central lines above "
                 "'Total' are checked against it at build time but not emitted (see notes)",
                 notes=(PAST_ACC_2425 + APP5I_CENTRAL_NOTE if rep is AR2425 else APP5I_2324_NOTE)
                 + govt_share_note(rep.fy))
    m = _one(r"^Total " + " +".join([AMOUNT] * 8) + r"\s*$", t, f"{rep.fy} Appendix-5(i) total")
    _check_app5i_lines(rep, t, [_amount(v) for v in m.groups()])
    cols = (("epf_contribution", "Total EPF contribution", "epf"), ("epf_payment", "Total EPF payment", "epf"),
            ("eps_contribution", "Total EPS contribution", "eps"), ("eps_payment", "Total EPS payment", "eps"),
            ("edli_contribution", "Total EDLI contribution", "edli"), ("edli_payment", "Total EDLI payment", "edli"),
            ("total_contribution", "Total contribution", "all"), ("total_payment", "Total payment", "all"))
    for (code, label, scheme), v in zip(cols, m.groups(), strict=True):
        e.add(pid, f"app5i.{code}.current", table, code, label, _amount(v), rep.fy, stage="Unaudited",
              institution=f"epfo_{scheme}")

# EPS outgo table: AR 2023-24 para 2.15 'EPS Payments' (PDF p.39), AR 2024-25 para 2.16 'Table 5' (PDF pp.40-41).
EPS_OUTGO_YEARS = {"2023-24": ["2019-20", "2020-21", "2021-22", "2022-23", "2023-24"],
                   "2024-25": ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]}
# EPS payment of the five-year table / App. 5(i) minus the outgo-table total, as stated in the notes (build-checked).
EPS_OUTGO_EXCESS = {"2020-21": 38.03, "2021-22": 382.46, "2022-23": 315.97, "2023-24": 371.23, "2024-25": -0.35}
EPS_OUTGO_NOTE = (
    "The report's split of EPS outgo into 'Pension Disbursed' (monthly pensions) and 'Withdrawal Benefits' (paid "
    "'on exit from service or on superannuation, provided the member has not rendered service eligible for pension', "
    "AR 2024-25 PDF p.36, AR 2023-24 PDF p.37); 'Total' is their sum (checked at build time within Rs 0.015 cr). "
    "This is the source for S9 EPS pensions vs lump-sum withdrawal benefits. It does not tie to the EPS payment of "
    "para 5.5 / App. 5(i) (series fiveyear.eps_payment / app5i.eps_payment in finsector_markets_epfo_ar): that "
    "figure exceeds the outgo total by 38.03 (2020-21), 382.46 (2021-22), 315.97 (2022-23) and 371.23 (2023-24), "
    "and is 0.35 below it in 2024-25 (build-checked); the reports do not explain the earlier-year excess (Phase 2 "
    "uncertainty on S9). Both vintages print identical values for the overlapping years 2020-21..2023-24."
)
EPS_OUTGO_NOTE_2425 = (
    " AR 2024-25 note under Table 5: 'The total outgo Rs. 27,963.76 Cr shown above is slightly different from figure "
    "given in Balance Sheet (Rs. 27,963.41) due to adjustment of Life Assurance Benefit (Rs. 0.35 Cr) entry in "
    "Balance Sheet.' The Balance-Sheet 27,963.41 is the App. 5(i) EPS payment, which includes the central lines CPPS "
    "6,813.22 and the unexplained 'Adjustment of Pension Disbursement Savings A/c Balance' 381.88 (issues file "
    "finsector_markets-37), so EPFO's own split counts the 381.88 inside pensions plus withdrawal benefits (which of "
    "the two is not stated). Pension Disbursed rises 25.3% from 2023-24 (15,130.68 to 18,957.86); the table gives "
    "no reason. Context, not a statement about these figures: 'Table D i.e, Return of contribution on exit from "
    "employment has been amended vide GSR 326 (E) dated 14.06.2024. Now withdrawal benefits are available even for "
    "1 month contribution' (PDF p.46)."
)


def _eps_outgo(e: _Emit, reader: pypdf.PdfReader) -> dict[str, float]:
    """The EPS outgo table; returns {fy: total} for the cross-check against the EPS payment."""
    rep = e.rep
    t = _text(reader, rep, "eps_outgo")
    flat = re.sub(r"\s+", " ", t)
    if rep is AR2324:
        table = "Para 2.15 (EPS Payments: pension disbursed and withdrawal benefits)"
        need = ("EPS Payments ( Rs. in crores )", "Year Pension Disbursed Withdrawal Benefits Total")
        notes = EPS_OUTGO_NOTE
    else:
        table = "Table 5 (para 2.16, Employee's Pension Fund outgo distribution financial year wise)"
        need = ("Pension Fund outgo distribution",
                "Year Pension Disbursed (Rs. crores) Withdrawal Benefits (Rs. crores) Total (Rs.crores)",
                "Balance Sheet (Rs. 27,963.41)", "Life Assurance Benefit (Rs. 0.35 Cr)")
        notes = EPS_OUTGO_NOTE + EPS_OUTGO_NOTE_2425
    for s in need:
        if s not in flat:
            raise ValueError(f"EPFO {rep.fy} EPS outgo table: {s!r} not found (report changed?)")
    pid = e.prov("eps_outgo", table, "rows by financial year; columns Pension Disbursed, Withdrawal Benefits, Total",
                 notes=notes)
    body = t[t.index("Withdrawal"):]
    got = re.findall(r"^(\d{4}-\d{2}(?:\d{2})?) " + AMOUNT + " " + AMOUNT + " " + AMOUNT + r"\s*$", body, flags=re.M)
    years = [normalize_fy(g[0]) for g in got]
    if years != EPS_OUTGO_YEARS[rep.fy]:
        raise ValueError(f"EPFO {rep.fy} EPS outgo table: years {years}")
    totals = {}
    for (_, pen, wd, tot), fy in zip(got, years, strict=True):
        pen, wd, tot = _amount(pen), _amount(wd), _amount(tot)
        if abs(pen + wd - tot) > 0.015:
            raise ValueError(f"EPFO {rep.fy} EPS outgo {fy}: {pen} + {wd} != {tot}")
        stage = "Unaudited" if fy == rep.fy else None
        for code, label, v in (("pension_disbursed", "Pension Disbursed", pen),
                               ("withdrawal_benefits", "Withdrawal Benefits", wd), ("total_outgo", "Total", tot)):
            e.add(pid, f"eps_outgo.{code}.current", table, f"eps_{code}", f"EPS outgo: {label}", v, fy, stage=stage,
                  institution="epfo_eps")
        totals[fy] = tot
    return totals


def _check_eps_outgo(rep: Report, rows: list[dict], outgo: dict[str, float]) -> None:
    """EPS payment (five-year table for AR 2024-25, App. 5(i) for AR 2023-24) minus outgo total = EPS_OUTGO_EXCESS."""
    sid = "fiveyear.eps_payment.current" if rep is AR2425 else "app5i.eps_payment.current"
    pay = {r["period"]: r["value"] for r in rows if r["series_id"] == sid}
    years = [y for y in outgo if y in pay]
    if years != (EPS_OUTGO_YEARS[rep.fy][:] if rep is AR2425 else [rep.fy]):
        raise ValueError(f"EPFO {rep.fy} EPS outgo check: overlapping years {years}")
    bad = [(y, round(pay[y] - outgo[y], 2)) for y in years if abs(pay[y] - outgo[y] - EPS_OUTGO_EXCESS[y]) > 0.005]
    if bad:
        raise ValueError(f"EPFO {rep.fy}: EPS payment - outgo total differs from the documented excess: {bad}")


def _check_govt_share(rep: Report, rows: list[dict]) -> None:
    """App. 5(i) EPS contribution = para 5.4 employers' share; total contribution excludes the Government's share."""
    v = {r["series_id"]: r["value"] for r in rows
         if r["period"] == rep.fy and r["series_id"].startswith(("app5i.", "para54."))}
    emp, gov, _, _ = GOVT_SHARE[rep.fy]
    ok = (abs(v["app5i.eps_contribution.current"] - emp) < 0.005
          and abs(v["para54.eps_contribution_employer.current"] - emp) < 0.005
          and abs(v["para54.eps_contribution_government.current"] - gov) < 0.005
          and abs(v["app5i.total_contribution.current"] - v["app5i.epf_contribution.current"] - emp
                  - v["app5i.edli_contribution.current"]) < 0.015)
    if not ok:
        raise ValueError(f"EPFO {rep.fy}: App. 5(i) EPS/total contribution no longer = employers' share only (notes)")


def _invest(e: _Emit, reader: pypdf.PdfReader) -> None:
    rep = e.rep
    t = _text(reader, rep, "invest")
    start = t.index(rep.anchors["invest"])
    t = t[start:]
    cons = t.find("Consolidated statement")
    if cons > 0:
        t = t[:cons]
    heads = [(_one(pat, t, f"{rep.fy} scheme heading {code}").start(), code, label) for pat, code, label in SCHEMES]
    if [h[0] for h in heads] != sorted(h[0] for h in heads):
        raise ValueError(f"EPFO {rep.fy}: scheme sections out of order")
    end_y = int(rep.fy[:4]) + 1
    table = "Para 5.20/5.15 (corpus and category-wise break-up of investments, un-exempted sector)"
    pid = e.prov("invest", table, "sections a)-e): 'Total Investments as on' lines, 'Net addition' line and the "
                 "category rows (face value; ETFs at cost); percentages not read",
                 notes="Face value (ETF at cost price) as printed; not market value. A category printed '-' "
                 "with a 0.00% share (EPF 'Public Account with Central Govt.') is read as nil and emitted as 0.")
    for i, (pos, scheme, slabel) in enumerate(heads):
        block = t[pos: heads[i + 1][0] if i + 1 < len(heads) else len(t)]
        tot = re.findall(r"Total Investments as on (\d{2})\.(\d{2})\.(\d{4}) " + AMOUNT, block)
        dates = [f"{y}-{m}-{d}" for d, m, y, _ in tot]
        if dates != [f"{end_y - 1}-03-31", f"{end_y}-03-31"]:
            raise ValueError(f"EPFO {rep.fy} {scheme}: total-investment dates {dates}")
        for (d, m, y, v), date in zip(tot, dates, strict=True):
            e.add(pid, f"invest.{scheme}.total.current", table, "investments_face_value",
                  f"{slabel}: total investments (face value)", _amount(v), date, stock=True,
                  institution=f"epfo_{scheme}", instrument="total")
        na = _one(r"Net addition in Investments at Face value during the year (\d{4}-\d{2}) " + AMOUNT, block,
                  f"{rep.fy} {scheme} net addition")
        if na.group(1) != rep.fy:
            raise ValueError(f"EPFO {rep.fy} {scheme}: net addition year {na.group(1)}")
        e.add(pid, f"invest.{scheme}.net_addition.current", table, "net_addition_investments",
              f"{slabel}: net addition in investments at face value during the year", _amount(na.group(2)), rep.fy,
              institution=f"epfo_{scheme}")
        for pat, code, label in CATEGORIES:
            ms = re.findall(r"^\d+\.? ?" + pat + r" +(" + AMOUNT[1:-1] + r"|-) +\d+\.\d+%\s*$", block, flags=re.M)
            if code == "invits" and not ms and rep is AR2324:
                continue
            if len(ms) != 1:
                raise ValueError(f"EPFO {rep.fy} {scheme}: category {label!r} found {len(ms)} times")
            v = 0.0 if ms[0].strip() == "-" else _amount(ms[0])
            e.add(pid, f"invest.{scheme}.{code}.current", table, "investments_face_value", f"{slabel}: {label}", v,
                  f"{end_y}-03-31", stock=True, institution=f"epfo_{scheme}", instrument=code)
        tm = _one(r"^TOTAL " + AMOUNT + r" 100\.00%\s*$", block, f"{rep.fy} {scheme} TOTAL")
        e.add(pid, f"invest.{scheme}.category_total.current", table, "investments_face_value",
              f"{slabel}: TOTAL of the category table", _amount(tm.group(1)), f"{end_y}-03-31", stock=True,
              institution=f"epfo_{scheme}", instrument="category_total")


def _exempted(e: _Emit, reader: pypdf.PdfReader) -> None:
    rep = e.rep
    t = _text(reader, rep, "exempted")
    table = "Para 5.22 (investments made by exempted establishments during 2023-24)"
    pid = e.prov("exempted", table, "'INVESTMENTS MADE BY EXEMPTED ESTABLISHMENTS DURING 2023-24' (continued on the "
                 "next page)", notes="The published table's three category rows do not add up to 'TOTAL GROSS "
                 "INVESTMENT' (1,397.11 + 2,46,513.82 + 1,47,102.54 = 3,95,013.47 vs 4,56,848.78; gap 61,835.31). "
                 "The rendered pages 98-99 show only these three rows, so the gap is in the publication, not an "
                 "extraction loss. Totals and categories are ingested as printed.")
    for pat, code, label in (
        (r"^Special Deposit Account " + AMOUNT, "special_deposit_account", "Special Deposit Account"),
        (r"^Govt\. Guaranteed Securities " + AMOUNT, "govt_guaranteed_securities", "Govt. Guaranteed Securities"),
        (r"^Others " + AMOUNT, "others", "Others"),
        (r"^TOTAL GROSS INVESTMENT " + AMOUNT, "total_gross", "TOTAL GROSS INVESTMENT"),
        (r"^LESS: Redemption " + AMOUNT, "redemption", "LESS: Redemption"),
        (r"^TOTAL NET INVESTMENT " + AMOUNT, "total_net", "TOTAL NET INVESTMENT"),
    ):
        m = _one(pat, t, f"exempted {code}")
        e.add(pid, f"exempted.{code}.current", table, f"exempted_investment_{code}",
              f"Investments made by exempted establishments: {label}", _amount(m.group(1)), rep.fy,
              institution="pf_exempted_trusts")


def _rates(e: _Emit, reader: pypdf.PdfReader) -> None:
    rep = e.rep
    t = _text(reader, rep, "rates")
    table = "Appendix-5(vii) (rate of interest on EPF balances, 1952 onwards)"
    pid = e.prov("rates", table, "Appendix-5(vii), both year/rate column pairs; 1978-79 (rate plus bonus) and "
                 "2000-01 (two rates within the year) are not read", unit_pub="per cent")
    found = re.findall(r"(\d{4}-\d{2}) (\d+(?:\.\d+)?)%(?![+(\d])", t)
    years = [normalize_fy(y) for y, _ in found]
    if len(years) != len(set(years)) or rep.fy not in years or "2013-14" not in years:
        raise ValueError(f"EPFO {rep.fy} rates: unexpected years {years}")
    for y, v in found:
        e.add(pid, "app5vii.epf_interest_rate", table, "epf_interest_rate", "Rate of interest on EPF balances",
              float(v), normalize_fy(y), unit="percent", institution="epfo_epf")


def build(ctx: BuildContext, unit: str) -> list[Dataset]:
    all_rows: list[dict] = []
    outgo_rows: list[dict] = []
    for rep in (AR2324, AR2425):
        raw = ctx.raw(SRC, rep.raw)
        reader = pypdf.PdfReader(raw.path)
        rows = Rows(ctx, SRC, rep.vintage)
        e = _Emit(rows, raw, rep)
        _contrib(e, reader)
        _fiveyear(e, reader)
        _app5i(e, reader)
        _invest(e, reader)
        if "exempted" in rep.pages:
            _exempted(e, reader)
        _rates(e, reader)
        _check_govt_share(rep, rows.rows)
        orows = Rows(ctx, SRC, rep.vintage)
        outgo = _eps_outgo(_Emit(orows, raw, rep), reader)
        _check_eps_outgo(rep, rows.rows, outgo)
        all_rows += rows.rows
        outgo_rows += orows.rows
    return [Dataset(f"{unit}_epfo_ar", frame(all_rows),
                    "EPFO Annual Reports 2023-24 and 2024-25 (two vintages): contributions, payments, investments by "
                    "scheme x category, exempted-sector investments, EPF interest rates"),
            Dataset(f"{unit}_epfo_eps_outgo", frame(outgo_rows),
                    "EPFO Annual Reports 2023-24 and 2024-25 (two vintages): EPS outgo split into pensions disbursed "
                    "and withdrawal benefits, 2019-20 to 2024-25")]
