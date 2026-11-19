"""Constants shared by the fetch and build halves of the rbi_financial_accounts unit."""

from __future__ import annotations

UNIT = "rbi_financial_accounts"

SRC_FSF = "rbi_fsf_fof"
SRC_HHFS = "rbi_hh_fin_savings"
SRC_HBS = "rbi_hbs"
SRC_DEA = "dea_public_debt_reports"

# ---------------------------------------------------------------------------------------------
# RBI Flow of Funds (FSF 2023-24, RBI Bulletin January 2026)
# ---------------------------------------------------------------------------------------------
FSF_LANDING = "https://www.rbi.org.in/Scripts/FlowofFundsAccounts.aspx"
FSF_ARTICLE = "https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx?Id=23912"
FSF_XLSX = "https://rbidocs.rbi.org.in/rdocs/content/docs/FSF2023-24_21012026.xlsx"
FSF_XLSX_NAME = "FSF2023-24_21012026.xlsx"
FSF_ARTICLE_NAME = "fsf_2023_24_article.html"
FSF_VINTAGE = "2026-01-21"
FSF_RELEASE = "Financial Stocks and Flow of Funds of the Indian Economy 2023-24 (RBI Bulletin, 21 Jan 2026)"

# ---------------------------------------------------------------------------------------------
# RBI Bulletin September 2026, Current Statistics 52(a)/52(b) (household financial saving)
# ---------------------------------------------------------------------------------------------
BULLETIN_LANDING = "https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx"
HHFS_52A = "https://rbidocs.rbi.org.in/rdocs/Bulletin/PDFs/52AT_BULL25092026004CFAF0BB3B4F779B3E0ADBC8826701.PDF"
HHFS_52B = "https://rbidocs.rbi.org.in/rdocs/Bulletin/PDFs/52BT_BULL25092026DDFCB0C318CF4A64BEC4E3E590FF1510.PDF"
HHFS_52A_NAME = "bulletin_2026_09_t52a.pdf"
HHFS_52B_NAME = "bulletin_2026_09_t52b.pdf"
HHFS_VINTAGE = "2026-09-25"

# ---------------------------------------------------------------------------------------------
# RBI Handbook of Statistics on the Indian Economy 2025-26 (28th edition, 31 Jul 2026)
# ---------------------------------------------------------------------------------------------
HBS_LANDING = (
    "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20Economy"
)
HBS_LISTING_NAME = "hbs_2025_26_listing.html"
HBS_VIEW = "https://www.rbi.org.in/Scripts/PublicationsView.aspx?id={id}"
HBS_VINTAGE = "2026-07-31"
HBS_RELEASE = "Handbook of Statistics on the Indian Economy 2025-26 (RBI, 31 Jul 2026), HTML table view"
# Handbook tables this unit reads (HTML views on www.rbi.org.in; the XLSX copies are on rbidocs).
HBS_TABLES = (11, 12, 39, 49, 107, 109)

# ---------------------------------------------------------------------------------------------
# DEA public debt reports (dea.gov.in)
# ---------------------------------------------------------------------------------------------
DEA_LANDING = "https://dea.gov.in/reports-public-debt-management"
DEA_FILES = {
    "dea_qr_jan_mar_2023.pdf": "https://dea.gov.in/files/public_debt_management_documents/"
    "Quarterly_Report_on_Public_Debt_Management_for_the_quarter_January_March_2023.pdf",
    "dea_qr_jan_mar_2024.pdf": "https://dea.gov.in/files/public_debt_management_documents/"
    "Quarterly%20Report%20on%20Public%20Debt%20Management%20for%20the%20quarter%20January-March%202024.pdf",
    "dea_status_paper_2023_24.pdf": "https://dea.gov.in/files/public_debt_management_documents/"
    "Status%20Paper%20on%20Government%20Debt%20for%20%202023-24.pdf",
}

RBIDOCS_HOST = "rbidocs.rbi.org.in"
RBIDOCS_GAP_S = 10.0  # DECISIONS D1-4: at least 10 s between rbidocs requests
