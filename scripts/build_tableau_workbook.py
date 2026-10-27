"""Generate tableau/kestrel_cx.twb (3 dashboards) from the CSVs in tableau/extracts/.

Usage (from the project root, after scripts/prepare_tableau.py):  python scripts/build_tableau_workbook.py
Open the .twb in Tableau Desktop/Public, check the numbers, then publish. Paths are absolute to this folder.
"""
import csv
import sys
import uuid
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[1]
EXTRACTS = ROOT / "tableau" / "extracts"
# Tableau needs the Windows path of the extracts folder; pass it if this script runs elsewhere
DIR = (sys.argv[1] if len(sys.argv) > 1 else str(EXTRACTS)).replace("\\", "/")
ORANGE, BLUE, GREY = "#eb6834", "#2a78d6", "#9a9890"

TYPES = {"integer": ("integer", 20, "Sum"), "real": ("real", 5, "Sum"),
         "date": ("date", 133, "Year"), "string": ("string", 129, "Count")}


def col_type(name, sample):
    if name in ("month_start",):
        return "date"
    if name.endswith(("_aud", "_pct", "proxy_h2")):
        return "real"
    try:
        int(sample)
        return "integer" if not name.endswith("code") else "string"
    except ValueError:
        try:
            float(sample)
            return "real"
        except ValueError:
            return "string"


def sid():
    return f"<simple-id uuid='{{{str(uuid.uuid4()).upper()}}}' />"


CAPTIONS = {"h2_cohort_12m_revenue_proxy_mid_aud": "Exposure at 25% churn (AUD)",
            "ai_name_flagged_responses": "Comments flagged", "excluded_responses": "Rows excluded"}


def caption(c):
    if c in CAPTIONS:
        return CAPTIONS[c]
    return c.replace("_", " ").title().replace("Ai ", "AI ").replace("Aud", "AUD")


class DS:
    def __init__(self, key, fn, calcs):
        self.key, self.fn, self.calcs = key, fn, calcs
        rows = list(csv.reader(open(EXTRACTS / fn, encoding="utf-8")))
        header, sample = rows[0], rows[1]
        self.cols = [(c, col_type(c, s)) for c, s in zip(header, sample)]
        self.name = f"federated.{key}"
        self.dim = {c for c, t in self.cols if t in ("string", "date")}

    def ref(self, inst):
        return f"[{self.name}].[{inst}]"

    def column_xml(self, c):
        t = dict(self.cols)[c]
        role, typ = ("dimension", "nominal") if t == "string" else (("dimension", "ordinal") if t == "date" else ("measure", "quantitative"))
        return f"<column caption={quoteattr(caption(c))} datatype='{t}' name='[{c}]' role='{role}' type='{typ}' />"

    def calc_xml(self, cid):
        cap, formula, fmt = self.calcs[cid]
        f = f" default-format='{fmt}'" if fmt else ""
        return (f"<column caption={quoteattr(cap)} datatype='real'{f} name='[{cid}]' role='measure' type='quantitative'>"
                f"<calculation class='tableau' formula={quoteattr(formula)} /></column>")

    def xml(self):
        tbl = f"[{self.fn.replace('.', '#')}]"
        cols = "".join(f"<column datatype='{t}' name='{c}' ordinal='{i}' />" for i, (c, t) in enumerate(self.cols))
        rel = (f"<relation connection='textscan.{self.key}' name='{self.fn}' table='{tbl}' type='table'>"
               f"<columns character-set='UTF-8' header='yes' locale='en_AU' separator=','>{cols}</columns></relation>")
        oid = f"{self.fn}_{self.key.upper()}0000000000000000000000000000"[:len(self.fn) + 33]
        md = "".join(
            f"<metadata-record class='column'><remote-name>{c}</remote-name><remote-type>{TYPES[t][1]}</remote-type>"
            f"<local-name>[{c}]</local-name><parent-name>[{self.fn}]</parent-name><remote-alias>{c}</remote-alias>"
            f"<ordinal>{i}</ordinal><local-type>{t}</local-type><aggregation>{TYPES[t][2]}</aggregation>"
            f"<contains-null>true</contains-null><object-id>[{oid}]</object-id></metadata-record>"
            for i, (c, t) in enumerate(self.cols))
        return (f"<datasource caption='{self.key}' inline='true' name='{self.name}' version='18.1'>"
                f"<connection class='federated'><named-connections><named-connection caption='{self.key}' name='textscan.{self.key}'>"
                f"<connection class='textscan' directory='{DIR}' filename='{self.fn}' password='' server='' />"
                f"</named-connection></named-connections>{rel}<metadata-records>{md}</metadata-records></connection>"
                f"<aliases enabled='yes' />"
                + "".join(self.column_xml(c) for c, _ in self.cols)
                + "".join(self.calc_xml(k) for k in self.calcs)
                + f"<layout dim-ordering='alphabetic' measure-ordering='alphabetic' show-structure='true' />"
                f"<object-graph><objects><object caption='{self.fn}' id='{oid}'><properties context=''>{rel}</properties></object></objects></object-graph>"
                f"</datasource>")


fm = DS("feedback_monthly", "feedback_monthly.csv", {
    "neg_share": ("Negative share", "SUM([negative_responses]) / SUM([rated_responses])", "p0.0%")})
td = DS("theme_drivers", "theme_drivers.csv", {
    "theme_share": ("Share of negative responses", "SUM([negative_theme_mentions]) / SUM([negative_responses_with_ai])", "p0%")})
dq = DS("data_quality", "data_quality.csv", {
    "ai_coverage": ("AI coverage of comments", "SUM([enriched_responses]) / SUM([commented_responses])", "p0.0%"),
    "undated_unrated": ("Undated or unrated responses", "SUM([accepted_undated_responses]) + SUM([accepted_unrated_responses])", ""),
    "ai_failed": ("AI errors or missing", "SUM([ai_error_responses]) + SUM([ai_missing_responses])", "")})
vs = DS("value_scenarios", "value_scenarios.csv", {})
SOURCES = [fm, td, dq, vs]


def inst(ds, field, kind):
    """Return (instance_name, column-instance xml) for a field used on a shelf."""
    if field in ds.calcs:
        n = f"usr:{field}:qk"
        return n, f"<column-instance column='[{field}]' derivation='User' name='[{n}]' pivot='key' type='quantitative' />"
    if kind == "month":
        n = f"tmn:{field}:qk"
        return n, f"<column-instance column='[{field}]' derivation='Month-Trunc' name='[{n}]' pivot='key' type='quantitative' />"
    if kind == "sum":
        n = f"sum:{field}:qk"
        return n, f"<column-instance column='[{field}]' derivation='Sum' name='[{n}]' pivot='key' type='quantitative' />"
    n = f"none:{field}:nk"
    return n, f"<column-instance column='[{field}]' derivation='None' name='[{n}]' pivot='key' type='nominal' />"


def worksheet(name, title, ds, rows=(), cols=(), mark="Bar", color=None, text=None, filters=None,
              sort=None, colors=None, size=None):
    """rows/cols: list of (field, kind) with kind in none|sum|month|calc."""
    used, deps = {}, []
    def use(field, kind):
        n, x = inst(ds, field, kind)
        if n not in used:
            used[n] = x
        return ds.ref(n)
    r = " / ".join(use(f, k) for f, k in rows)
    c = " / ".join(use(f, k) for f, k in cols)
    enc = ""
    if color:
        enc += f"<color column='{use(*color)}' />"
    if text:
        enc += f"<text column='{use(*text)}' />"
    flt, slices = "", ""
    for field, members in (filters or {}).items():
        ref = use(field, "none")
        lvl = f"[none:{field}:nk]"
        if len(members) == 1:
            g = f"<groupfilter function='member' level='{lvl}' member={quoteattr(chr(34) + members[0] + chr(34))} user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate' />"
        else:
            g = (f"<groupfilter function='union' user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate'>"
                 + "".join(f"<groupfilter function='member' level='{lvl}' member={quoteattr(chr(34) + m + chr(34))} />" for m in members)
                 + "</groupfilter>")
        flt += f"<filter class='categorical' column='{ref}'>{g}</filter>"
        slices += f"<column>{ref}</column>"
    srt = ""
    if sort:
        dim, meas, direction = sort
        srt = f"<sort class='computed' column='{use(dim, 'none')}' direction='{direction}' using='{use(*meas)}' />"
    base_cols = {f for f, k in list(rows) + list(cols) + [x for x in (color, text) if x] if k != "calc"} | set(filters or {})
    base_cols |= {sort[0]} if sort else set()
    dep_cols = "".join(ds.column_xml(f) for f in sorted(base_cols) if f not in ds.calcs)
    dep_cols += "".join(ds.calc_xml(f) for f in ds.calcs if any(f in u for u in used))
    style = ""
    if colors:
        maps = "".join(f"<map to='{hexv}'><bucket>&quot;{escape(k)}&quot;</bucket></map>" for k, hexv in colors.items())
        style = f"<style><style-rule element='mark'><encoding attr='color' field='{ds.ref(f'none:{color[0]}:nk')}' type='palette'>{maps}</encoding></style-rule></style>"
    labels = "<style><style-rule element='mark'><format attr='mark-labels-show' value='true' /></style-rule></style>" if text or mark in ("Bar",) else ""
    sz = f"<size column='{use(*size)}' />" if size else ""
    return (f"<worksheet name={quoteattr(name)}><layout-options><title><formatted-text><run bold='true' fontsize='12'>{escape(title)}</run></formatted-text></title></layout-options>"
            f"<table><view><datasources><datasource caption='{ds.key}' name='{ds.name}' /></datasources>"
            f"<datasource-dependencies datasource='{ds.name}'>{dep_cols}{''.join(used.values())}</datasource-dependencies>"
            f"{flt}{srt}{'<slices>' + slices + '</slices>' if slices else ''}<aggregation value='true' /></view>{style or '<style />'}"
            f"<panes><pane selection-relaxation-option='selection-relaxation-allow'><view><breakdown value='auto' /></view>"
            f"<mark class='{mark}' /><encodings>{enc}{sz}</encodings>{labels}</pane></panes>"
            f"<rows>{r}</rows><cols>{c}</cols></table>{sid()}</worksheet>")

def dealers_with(*fields):
    """Dealerships with a non-zero total in data_quality.csv, so the short lists skip rows of zeros."""
    out = set()
    for r in csv.DictReader(open(EXTRACTS / "data_quality.csv", encoding="utf-8")):
        if sum(float(r[f] or 0) for f in fields) > 0:
            out.add(r["dealership_name"])
    return sorted(out)


GROUP_COLORS = {"Worsening four": ORANGE, "Other 20 dealerships": BLUE}
HALF_COLORS = {"H1 (Oct-Mar)": "#86b6ef", "H2 (Apr-Sep)": ORANGE}
S = [
    ("Department", "Negative share by department (rated responses scoring 1-2)",
     fm, dict(rows=[("department", "none")], cols=[("neg_share", "calc")], text=("neg_share", "calc"),
              sort=("department", ("neg_share", "calc"), "DESC"))),
    ("Monthly trend", "Negative share by month: the four worsening sites vs the other 20",
     fm, dict(cols=[("month_start", "month")], rows=[("neg_share", "calc")], mark="Line",
              color=("site_group", "none"), colors=GROUP_COLORS)),
    ("Headline", "Overall negative share",
     fm, dict(mark="Text", text=("neg_share", "calc"))),
    ("Heatmap", "Negative share by dealership and department",
     fm, dict(rows=[("dealership_name", "none")], cols=[("department", "none")], mark="Square",
              color=("neg_share", "calc"), text=("neg_share", "calc"),
              sort=("dealership_name", ("neg_share", "calc"), "DESC"))),
    ("H1 vs H2", "Negative share by dealership: Oct-Mar vs Apr-Sep",
     fm, dict(rows=[("dealership_name", "none")], cols=[("neg_share", "calc")], mark="Circle",
              color=("half_year", "none"), colors=HALF_COLORS,
              sort=("dealership_name", ("neg_share", "calc"), "DESC"))),
    ("Themes at worsening sites", "Themes in negative comments at the four worsening sites",
     td, dict(rows=[("theme_name", "none"), ("half_year", "none")], cols=[("theme_share", "calc")],
              color=("half_year", "none"), colors=HALF_COLORS, text=("theme_share", "calc"),
              filters={"site_group": ["Worsening four"], "theme_name": ["Waiting/booking", "Communication", "Repair quality", "Price/value", "Parts availability", "Staff service", "Sales process"]},
              sort=("theme_name", ("theme_share", "calc"), "DESC"))),
    ("Value scenarios", "Exposure at 25% churn, AUD",
     vs, dict(rows=[("dealership_name", "none")], cols=[("h2_cohort_12m_revenue_proxy_mid_aud", "sum")],
              text=("h2_cohort_12m_revenue_proxy_mid_aud", "sum"),
              sort=("dealership_name", ("h2_cohort_12m_revenue_proxy_mid_aud", "sum"), "DESC"))),
    ("Undated or unrated", "Accepted responses with no date or no rating (others: 0)",
     dq, dict(rows=[("dealership_name", "none")], cols=[("undated_unrated", "calc")], text=("undated_unrated", "calc"),
              filters={"dealership_name": dealers_with("accepted_undated_responses", "accepted_unrated_responses")},
              sort=("dealership_name", ("undated_unrated", "calc"), "DESC"))),
    ("AI coverage", "Comments with a valid AI label",
     dq, dict(rows=[("department", "none")], cols=[("ai_coverage", "calc")], text=("ai_coverage", "calc"),
              filters={"department": ["Parts", "Sales", "Service"]})),
    ("Name flags", "Comments flagged for a possible leftover name (repaired)",
     dq, dict(rows=[("dealership_name", "none")], cols=[("ai_name_flagged_responses", "sum")],
              text=("ai_name_flagged_responses", "sum"),
              sort=("dealership_name", ("ai_name_flagged_responses", "sum"), "DESC"))),
    ("Excluded", "Rows dropped as tests, duplicates or non-responses (others: 0)",
     dq, dict(rows=[("dealership_name", "none")], cols=[("excluded_responses", "sum")], text=("excluded_responses", "sum"),
              filters={"dealership_name": dealers_with("excluded_responses")},
              sort=("dealership_name", ("excluded_responses", "sum"), "DESC"))),
]

zid = [100]
def nid():
    zid[0] += 1
    return zid[0]

def text_zone(txt, x, y, w, h, size=14, bold=True):
    return (f"<zone h='{h}' id='{nid()}' type-v2='text' w='{w}' x='{x}' y='{y}'><formatted-text>"
            f"<run bold='{str(bold).lower()}' fontsize='{size}'>{escape(txt)}</run></formatted-text></zone>")

def legend_zone(sheet, ds, field, x, y, w, h):
    return (f"<zone h='{h}' id='{nid()}' name={quoteattr(sheet)} pane-specification-id='0' "
            f"param='{ds.ref(f'none:{field}:nk')}' type-v2='color' w='{w}' x='{x}' y='{y}' />")


def sheet_zone(name, x, y, w, h):
    return f"<zone h='{h}' id='{nid()}' name={quoteattr(name)} w='{w}' x='{x}' y='{y}' />"

def dashboard(name, title, subtitle, layout, legends=()):
    z = text_zone(title, 0, 0, 100000, 6000, 18) + text_zone(subtitle, 0, 6000, 100000, 5000, 10, False)
    z += "".join(legend_zone(*l) for l in legends)
    z += "".join(sheet_zone(n, x, y, w, h) for n, x, y, w, h in layout)
    return (f"<dashboard enable-sort-zone-taborder='true' name={quoteattr(name)}><style />"
            f"<size maxheight='900' maxwidth='1400' minheight='900' minwidth='1400' /><zones>"
            f"<zone h='100000' id='{nid()}' type-v2='layout-basic' w='100000' x='0' y='0'>{z}</zone></zones>{sid()}</dashboard>")

D = [
    dashboard("CX overview", "Service drives negative feedback, and four sites got worse from April",
              "22.3% of 7,079 rated responses were negative (rated 1-2 of 5), Oct 2025 - Sep 2026. Trend excludes 10 undated.",
              [("Department", 0, 11000, 100000, 27000),
               ("Monthly trend", 0, 38000, 84000, 62000)],
              [("Monthly trend", fm, "site_group", 84000, 38000, 16000, 20000)]),
    dashboard("Dealer investigation", "Where to focus: Parramatta and Dandenong Service",
              "Worsening four: Parramatta, Bendigo, Dandenong, Liverpool. Themes are Gemini labels. Exposure is an assumption.",
              [("Heatmap", 0, 11000, 34000, 89000), ("H1 vs H2", 34000, 11000, 30000, 79000),
               ("Themes at worsening sites", 64000, 11000, 36000, 52000), ("Value scenarios", 64000, 63000, 36000, 37000)],
              [("H1 vs H2", fm, "half_year", 34000, 90000, 30000, 10000)]),
    dashboard("Data quality", "What was excluded, missing or flagged",
              "7,432 source rows -> 7,116 Bronze -> 7,089 accepted. Hunter mapped to Newcastle (assumption).",
              [("Name flags", 0, 11000, 50000, 89000), ("AI coverage", 50000, 11000, 50000, 29000),
               ("Undated or unrated", 50000, 40000, 50000, 30000), ("Excluded", 50000, 70000, 50000, 30000)]),
]

windows = "".join(f"<window class='worksheet' name={quoteattr(n)}><cards><edge name='left'><strip size='160'><card type='pages' /><card type='filters' /><card type='marks' /></strip></edge><edge name='top'><strip size='2147483647'><card type='columns' /></strip><strip size='2147483647'><card type='rows' /></strip><strip size='30'><card type='title' /></strip></edge></cards>{sid()}</window>" for n, *_ in S)
DASH_SHEETS = {"CX overview": ["Department", "Monthly trend"],
               "Dealer investigation": ["Heatmap", "H1 vs H2", "Themes at worsening sites", "Value scenarios"],
               "Data quality": ["Name flags", "Undated or unrated", "AI coverage", "Excluded"]}
windows += "".join(f"<window class='dashboard' name={quoteattr(n)}><viewpoints>"
                   + "".join(f"<viewpoint name={quoteattr(v)} />" for v in vs_) + f"</viewpoints><active id='-1' />{sid()}</window>"
                   for n, vs_ in DASH_SHEETS.items())

xml = ("<?xml version='1.0' encoding='utf-8' ?>\n"
       "<workbook original-version='18.1' source-build='2026.2.3 (20262.26.0912.1023)' source-platform='win' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>"
       "<document-format-change-manifest><AccessibleZoneTabOrder /><AnimationOnByDefault /><MarkAnimation /><ObjectModelEncapsulateLegacy /><ObjectModelTableType /><SchemaViewerObjectModel /><SheetIdentifierTracking /><WindowsPersistSimpleIdentifiers /></document-format-change-manifest>"
       "<preferences><preference name='ui.encoding.shelf.height' value='24' /><preference name='ui.shelf.height' value='26' /></preferences>"
       "<datasources>" + "".join(d.xml() for d in SOURCES) + "</datasources>"
       "<worksheets>" + "".join(worksheet(n, t, ds, **kw) for n, t, ds, kw in S) + "</worksheets>"
       "<dashboards>" + "".join(D) + "</dashboards>"
       "<windows saved-dpi-scale-factor='1.5' source-height='44'>" + windows + "</windows></workbook>")
out = ROOT / "tableau" / "kestrel_cx.twb"
out.write_text(xml, encoding="utf-8")
print("wrote", out)
