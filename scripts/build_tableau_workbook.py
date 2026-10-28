"""Generate tableau/kestrel_cx.twb (3 dashboards and a story) from the CSVs in tableau/extracts/.

Usage (from the project root, after scripts/prepare_tableau.py):
    python scripts/build_tableau_workbook.py [EXTRACTS_DIR] [--extracts EXTRACT_BACKED.twb]
Open the .twb in Tableau Desktop/Public, check the numbers, then publish. Paths are absolute to this folder.
Tableau Public only publishes extracts: --extracts copies the <extract> blocks from a workbook that
already points at .hyper files (Data > Extract Data once, then save), so a rebuild keeps them.
"""
import csv
import re
import sys
import uuid
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[1]
EXTRACTS = ROOT / "tableau" / "extracts"
# Tableau needs the Windows path of the extracts folder; pass it if this script runs elsewhere
ARGS = sys.argv[1:]
TEMPLATE = None
if "--extracts" in ARGS:
    i = ARGS.index("--extracts")
    TEMPLATE = Path(ARGS[i + 1]).read_text(encoding="utf-8")
    del ARGS[i:i + 2]
DIR = (ARGS[0] if ARGS else str(EXTRACTS)).replace("\\", "/")
ORANGE, BLUE, GREY = "#eb6834", "#2a78d6", "#9a9890"
CHURN = "[Parameters].[Churn rate]"
PARAMS = ("<datasource hasconnection='false' inline='true' name='Parameters' version='18.1'><aliases enabled='yes' />"
          "<column caption='Churn rate' datatype='real' default-format='p0%' name='[Churn rate]' param-domain-type='range' "
          "role='measure' type='quantitative' value='0.25'><calculation class='tableau' formula='0.25' />"
          "<range granularity='0.05' max='0.4' min='0.1' /></column></datasource>")
PARAM_DEP = ("<datasource-dependencies datasource='Parameters'><column caption='Churn rate' datatype='real' default-format='p0%' "
             "name='[Churn rate]' param-domain-type='range' role='measure' type='quantitative' value='0.25'>"
             "<calculation class='tableau' formula='0.25' /><range granularity='0.05' max='0.4' min='0.1' /></column></datasource-dependencies>")

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

    def extract_xml(self):
        """The <extract> block for this source from the --extracts workbook, if given."""
        if not TEMPLATE:
            return "", ""
        m = re.search(rf"<datasource caption='{self.key}'.*?</datasource>", TEMPLATE, re.S)
        e = re.search(r"<extract .*?</extract>", m.group(0), re.S) if m else None
        if not e:
            return "", ""
        return e.group(0), "<properties context='extract'><relation name='Extract' table='[Extract].[Extract]' type='table' /></properties>"

    def xml(self):
        ext, ext_props = self.extract_xml()
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
                + "".join(self.calc_xml(k) for k in self.calcs) + ext
                + f"<layout dim-ordering='alphabetic' measure-ordering='alphabetic' show-structure='true' />"
                f"<object-graph><objects><object caption='{self.fn}' id='{oid}'><properties context=''>{rel}</properties>{ext_props}</object></objects></object-graph>"
                f"</datasource>")


W4_H2 = "[site_group] = 'Worsening four' AND [half_year] = 'H2 (Apr-Sep)'"
W4_H1 = "[site_group] = 'Worsening four' AND [half_year] = 'H1 (Oct-Mar)'"
fm = DS("feedback_monthly", "feedback_monthly.csv", {
    "neg_share": ("Negative share", "SUM([negative_responses]) / SUM([rated_responses])", "p0.0%"),
    "service_share": ("Service share of negatives",
                      "SUM(IF [department] = 'Service' THEN [negative_responses] END) / SUM([negative_responses])", "p0%"),
    "w4_h2": ("Worsening four, Apr-Sep", f"SUM(IF {W4_H2} THEN [negative_responses] END) / SUM(IF {W4_H2} THEN [rated_responses] END)", "p0.0%"),
    "w4_h1": ("Worsening four, Oct-Mar", f"SUM(IF {W4_H1} THEN [negative_responses] END) / SUM(IF {W4_H1} THEN [rated_responses] END)", "p0.0%")})
td = DS("theme_drivers", "theme_drivers.csv", {
    "theme_share": ("Share of negative responses", "SUM([negative_theme_mentions]) / SUM([negative_responses_with_ai])", "p0%")})
dq = DS("data_quality", "data_quality.csv", {
    "ai_coverage": ("AI coverage of comments", "SUM([enriched_responses]) / SUM([commented_responses])", "p0.0%"),
    "undated_unrated": ("Undated or unrated responses", "SUM([accepted_undated_responses]) + SUM([accepted_unrated_responses])", ""),
    "ai_failed": ("AI errors or missing", "SUM([ai_error_responses]) + SUM([ai_missing_responses])", "")})
# the scenario CSV is linear in churn (mid = 25%), so any churn rate is mid / 0.25 * rate
vs = DS("value_scenarios", "value_scenarios.csv", {
    "exposure": ("Exposure at chosen churn (AUD)", f"SUM([h2_cohort_12m_revenue_proxy_mid_aud]) / 0.25 * {CHURN}", "n#,##0"),
    "exposure_m": ("Exposure at chosen churn (AUD M)", f"SUM([h2_cohort_12m_revenue_proxy_mid_aud]) / 0.25 * {CHURN} / 1000000", "n#,##0.00")})
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
              sort=None, colors=None, size=None, tooltip=(), quick=(), label=None):
    """rows/cols: list of (field, kind) with kind in none|sum|month|calc.
    quick: (field, group) filters shared across sheets and shown on dashboards; label: KPI text runs."""
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
    for t in tooltip:
        # a KPI label only shows fields on the Text shelf, so KPI extras go there too
        enc += f"<text column='{use(*t)}' />" if label and t[1] == "calc" else f"<tooltip column='{use(*t)}' />"
    flt, slices = "", ""
    for field, group in quick:
        ref = use(field, "none")
        flt += (f"<filter class='categorical' column='{ref}' filter-group='{group}'><groupfilter function='level-members' "
                f"level='[none:{field}:nk]' user:ui-enumeration='all' user:ui-marker='enumerate' /></filter>")
        slices += f"<column>{ref}</column>"
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
    base_cols = {f for f, k in list(rows) + list(cols) + list(tooltip) + [x for x in (color, text) if x] if k != "calc"}
    base_cols |= set(filters or {}) | {f for f, _ in quick}
    base_cols |= {sort[0]} if sort else set()
    dep_cols = "".join(ds.column_xml(f) for f in sorted(base_cols) if f not in ds.calcs)
    dep_cols += "".join(ds.calc_xml(f) for f in ds.calcs if any(f in u for u in used))
    style = ""
    if colors:
        maps = "".join(f"<map to='{hexv}'><bucket>&quot;{escape(k)}&quot;</bucket></map>" for k, hexv in colors.items())
        style = f"<style><style-rule element='mark'><encoding attr='color' field='{ds.ref(f'none:{color[0]}:nk')}' type='palette'>{maps}</encoding></style-rule></style>"
    labels = "<style><style-rule element='mark'><format attr='mark-labels-show' value='true' /></style-rule></style>" if text or mark in ("Bar",) else ""
    sz = f"<size column='{use(*size)}' />" if size else ""
    custom = ""
    if label:
        runs = []
        for part in label:
            if isinstance(part, tuple):
                txt, attrs = part
            else:
                txt, attrs = part, "fontsize='10' fontcolor='#555555'"
            if txt == "\n":
                runs.append("<run>Æ&#10;</run>")
                continue
            # Tableau wants each field reference in a run of its own
            for i, piece in enumerate(re.split(r"\{(\w+)\}", txt)):
                if piece:
                    piece = "<" + use(piece, "calc") + ">" if i % 2 else piece
                    runs.append(f"<run {attrs}>{escape(piece)}</run>")
        custom = f"<customized-label><formatted-text>{''.join(runs)}</formatted-text></customized-label>"
    params = any(CHURN in ds.calcs[f][1] for f in ds.calcs if any(f in u for u in used))
    p_ds = "<datasource name='Parameters' />" if params else ""
    return (f"<worksheet name={quoteattr(name)}><layout-options><title><formatted-text><run bold='true' fontsize='12'>{escape(title)}</run></formatted-text></title></layout-options>"
            f"<table><view><datasources><datasource caption='{ds.key}' name='{ds.name}' />{p_ds}</datasources>"
            f"<datasource-dependencies datasource='{ds.name}'>{dep_cols}{''.join(used.values())}</datasource-dependencies>"
            f"{PARAM_DEP if params else ''}"
            f"{flt}{srt}{'<slices>' + slices + '</slices>' if slices else ''}<aggregation value='true' /></view>{style or '<style />'}"
            f"<panes><pane selection-relaxation-option='selection-relaxation-allow'><view><breakdown value='auto' /></view>"
            f"<mark class='{mark}' /><encodings>{enc}{sz}</encodings>{custom}{labels}</pane></panes>"
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
DEPT_COLORS = {"Service": ORANGE, "Parts": BLUE, "Sales": GREY}
SEVEN = ["Waiting/booking", "Communication", "Repair quality", "Price/value", "Parts availability", "Staff service", "Sales process"]
FM_TIPS = [("rated_responses", "sum"), ("negative_responses", "sum")]
QUICK = [("state", 2), ("department", 3)]  # state and department filters shared by the overview sheets
BIG = "fontsize='18' bold='true' fontcolor='{}'"
CAP = "fontsize='10' bold='true' fontcolor='#333333'"
S = [
    ("KPI negative", "Negative share", fm,
     dict(mark="Text", text=("neg_share", "calc"), tooltip=FM_TIPS, quick=QUICK,
          label=[("Negative share", CAP), "\n", ("{neg_share}", BIG.format(ORANGE)), "\n", "of rated responses"])),
    ("KPI service", "Service share of negatives", fm,
     dict(mark="Text", text=("service_share", "calc"), tooltip=FM_TIPS, quick=QUICK,
          label=[("Service share", CAP), "\n", ("{service_share}", BIG.format(ORANGE)), "\n", "of negatives are Service"])),
    ("KPI worsening", "Worsening four, Apr-Sep", fm,
     dict(mark="Text", text=("w4_h2", "calc"), tooltip=[("w4_h1", "calc")], quick=QUICK,
          label=[("Worsening four, Apr-Sep", CAP), "\n", ("{w4_h2}", BIG.format(ORANGE)), "\n", "negative, from {w4_h1} in H1"])),
    ("KPI exposure", "Revenue at risk", vs,
     dict(mark="Text", text=("exposure_m", "calc"),
          label=[("Revenue at risk", CAP), "\n", ("$", BIG.format(BLUE)), ("{exposure_m}M", BIG.format(BLUE)), "\n", "a year at chosen churn"])),
    ("Department", "By department (click a bar to filter)",
     fm, dict(rows=[("department", "none")], cols=[("neg_share", "calc")], text=("neg_share", "calc"),
              tooltip=FM_TIPS, quick=QUICK, sort=("department", ("neg_share", "calc"), "DESC"))),
    ("Monthly trend", "Negative share by month: the four worsening sites vs the other 20",
     fm, dict(cols=[("month_start", "month")], rows=[("neg_share", "calc")], mark="Line",
              color=("site_group", "none"), colors=GROUP_COLORS, tooltip=FM_TIPS, quick=QUICK)),
    ("Heatmap", "Negative share by dealership and department (click a cell)",
     fm, dict(rows=[("dealership_name", "none")], cols=[("department", "none")], mark="Square",
              color=("neg_share", "calc"), text=("neg_share", "calc"), tooltip=FM_TIPS,
              sort=("dealership_name", ("neg_share", "calc"), "DESC"))),
    ("Dealer trend", "Monthly trend for the selection",
     fm, dict(cols=[("month_start", "month")], rows=[("neg_share", "calc")], mark="Line",
              color=("department", "none"), colors=DEPT_COLORS, tooltip=FM_TIPS)),
    ("Dealer themes", "Themes for the selection",
     td, dict(rows=[("theme_name", "none"), ("half_year", "none")], cols=[("theme_share", "calc")],
              color=("half_year", "none"), colors=HALF_COLORS, text=("theme_share", "calc"),
              tooltip=[("negative_theme_mentions", "sum"), ("negative_responses_with_ai", "sum")],
              filters={"theme_name": SEVEN}, sort=("theme_name", ("theme_share", "calc"), "DESC"))),
    ("H1 vs H2", "Negative share, Oct-Mar vs Apr-Sep",
     fm, dict(rows=[("dealership_name", "none")], cols=[("neg_share", "calc")], mark="Circle",
              color=("half_year", "none"), colors=HALF_COLORS, tooltip=FM_TIPS,
              sort=("dealership_name", ("neg_share", "calc"), "DESC"))),
    ("Themes at worsening sites", "Complaint themes at the worsening four",
     td, dict(rows=[("theme_name", "none"), ("half_year", "none")], cols=[("theme_share", "calc")],
              color=("half_year", "none"), colors=HALF_COLORS, text=("theme_share", "calc"),
              tooltip=[("negative_theme_mentions", "sum"), ("negative_responses_with_ai", "sum")],
              filters={"site_group": ["Worsening four"], "theme_name": SEVEN},
              sort=("theme_name", ("theme_share", "calc"), "DESC"))),
    ("Value scenarios", "Revenue at risk at the chosen churn rate, AUD",
     vs, dict(rows=[("dealership_name", "none")], cols=[("exposure", "calc")], text=("exposure", "calc"),
              tooltip=[("h1_pct", "sum"), ("h2_pct", "sum"), ("n_h2", "sum")],
              sort=("dealership_name", ("exposure", "calc"), "DESC"))),
    ("Undated or unrated", "Accepted responses with no date or no rating (others: 0)",
     dq, dict(rows=[("dealership_name", "none")], cols=[("undated_unrated", "calc")], text=("undated_unrated", "calc"),
              filters={"dealership_name": dealers_with("accepted_undated_responses", "accepted_unrated_responses")},
              sort=("dealership_name", ("undated_unrated", "calc"), "DESC"))),
    ("AI coverage", "Comments with a valid AI label",
     dq, dict(rows=[("department", "none")], cols=[("ai_coverage", "calc")], text=("ai_coverage", "calc"),
              tooltip=[("commented_responses", "sum"), ("enriched_responses", "sum")],
              filters={"department": ["Parts", "Sales", "Service"]})),
    ("Name flags", "Comments flagged for a possible leftover name (repaired)",
     dq, dict(rows=[("dealership_name", "none")], cols=[("ai_name_flagged_responses", "sum")],
              text=("ai_name_flagged_responses", "sum"), tooltip=[("commented_responses", "sum")],
              sort=("dealership_name", ("ai_name_flagged_responses", "sum"), "DESC"))),
    ("Excluded", "Rows dropped as tests, duplicates or non-responses (others: 0)",
     dq, dict(rows=[("dealership_name", "none")], cols=[("excluded_responses", "sum")], text=("excluded_responses", "sum"),
              tooltip=[("source_feedback_rows", "sum")],
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


def filter_zone(sheet, ds, field, x, y, w, h):
    return (f"<zone h='{h}' id='{nid()}' mode='checkdropdown' name={quoteattr(sheet)} "
            f"param='{ds.ref(f'none:{field}:nk')}' type-v2='filter' w='{w}' x='{x}' y='{y}' />")


def churn_zone(x, y, w, h):
    return f"<zone h='{h}' id='{nid()}' mode='slider' param='{CHURN}' type-v2='paramctrl' w='{w}' x='{x}' y='{y}' />"


def sheet_zone(name, x, y, w, h):
    title = " show-title='false'" if name.startswith("KPI") else ""
    return f"<zone h='{h}' id='{nid()}' name={quoteattr(name)}{title} w='{w}' x='{x}' y='{y}' />"

def dashboard(name, title, subtitle, layout, legends=(), extra=""):
    z = text_zone(title, 0, 0, 100000, 6000, 18) + text_zone(subtitle, 0, 6000, 100000, 4500, 10, False)
    z += "".join(legend_zone(*l) for l in legends) + extra
    z += "".join(sheet_zone(n, x, y, w, h) for n, x, y, w, h in layout)
    return (f"<dashboard enable-sort-zone-taborder='true' name={quoteattr(name)}><style />"
            f"<size maxheight='900' maxwidth='1400' minheight='900' minwidth='1400' /><zones>"
            f"<zone h='100000' id='{nid()}' type-v2='layout-basic' w='100000' x='0' y='0'>{z}</zone></zones>{sid()}</dashboard>")

D = [
    dashboard("CX overview", "Service drives negative feedback, and four sites got worse from April",
              "7,079 rated responses, Oct 2025 - Sep 2026. Filter by state or department, click a department bar, or drag the churn slider.",
              [("KPI negative", 0, 10500, 19000, 14500), ("KPI service", 19000, 10500, 19000, 14500),
               ("KPI worsening", 38000, 10500, 19000, 14500), ("KPI exposure", 57000, 10500, 19000, 14500),
               ("Monthly trend", 0, 25000, 60000, 37000), ("Value scenarios", 0, 66000, 60000, 34000),
               ("Themes at worsening sites", 60000, 25000, 40000, 48000), ("Department", 60000, 77000, 40000, 23000)],
              [("Monthly trend", fm, "site_group", 0, 62000, 60000, 4000),
               ("Themes at worsening sites", td, "half_year", 60000, 73000, 40000, 4000)],
              filter_zone("Monthly trend", fm, "state", 77000, 10500, 23000, 5000)
              + filter_zone("Monthly trend", fm, "department", 77000, 15500, 23000, 5000)
              + churn_zone(77000, 20500, 23000, 4500)),
    dashboard("Dealer investigation", "Where to focus: Parramatta and Dandenong Service",
              "Click a heatmap cell to see that site's monthly trend and complaint themes. Click it again to clear.",
              [("Heatmap", 0, 10500, 32000, 89500), ("Dealer trend", 32000, 10500, 36000, 38000),
               ("Dealer themes", 32000, 52500, 36000, 47500), ("H1 vs H2", 68000, 10500, 32000, 85000)],
              [("Dealer trend", fm, "department", 32000, 48500, 36000, 4000),
               ("H1 vs H2", fm, "half_year", 68000, 95500, 32000, 4500)]),
    dashboard("Data quality", "What was excluded, missing or flagged",
              "7,432 source rows -> 7,116 Bronze -> 7,089 accepted. Hunter mapped to Newcastle (assumption). Hover for counts.",
              [("Name flags", 0, 10500, 50000, 89500), ("AI coverage", 50000, 10500, 50000, 29500),
               ("Undated or unrated", 50000, 40000, 50000, 30000), ("Excluded", 50000, 70000, 50000, 30000)]),
]

STORY = "Kestrel Motor Group: what's driving negative feedback"
POINTS = [("1. What's driving it", "CX overview"), ("2. Where to focus", "Dealer investigation"), ("3. Can we trust it", "Data quality")]
story = (f"<dashboard name={quoteattr(STORY)} type='storyboard'><style />"
         "<size maxheight='1080' maxwidth='1400' minheight='1080' minwidth='1400' sizing-mode='fixed' /><zones>"
         "<zone h='100000' id='2' type-v2='layout-basic' w='100000' x='0' y='0'>"
         "<zone h='98518' id='1' param='vert' removable='false' type-v2='layout-flow' w='98858' x='571' y='741'>"
         "<zone h='4630' id='3' type-v2='title' w='98858' x='571' y='741' />"
         "<zone h='9352' id='4' is-fixed='true' paired-zone-id='5' removable='false' type-v2='flipboard-nav' w='98858' x='571' y='5371' />"
         "<zone h='84536' id='5' paired-zone-id='4' removable='false' type-v2='flipboard' w='98858' x='571' y='14723'>"
         "<flipboard active-id='1' nav-type='caption' show-nav-arrows='true'><story-points>"
         + "".join(f"<story-point caption={quoteattr(c)} captured-sheet={quoteattr(d)} id='{i}' />" for i, (c, d) in enumerate(POINTS, 1))
         + f"</story-points></flipboard></zone></zone></zone></zones>{sid()}</dashboard>")


def action(n, caption, dash, sheet, exclude):
    return (f"<action caption={quoteattr(caption)} name='[Action{n}]'><activation auto-clear='true' type='on-select' />"
            f"<source dashboard={quoteattr(dash)} type='sheet' worksheet={quoteattr(sheet)} />"
            f"<command command='tsc:tsl-filter'><param name='exclude' value={quoteattr(','.join(exclude))} />"
            f"<param name='special-fields' value='all' /><param name='target' value={quoteattr(dash)} /></command></action>")


ACTIONS = (action(1, "Department bar filters the overview", "CX overview", "Department",
                  ["KPI negative", "KPI service", "KPI worsening", "KPI exposure", "Value scenarios"])
           + action(2, "Heatmap cell filters trend and themes", "Dealer investigation", "Heatmap",
                    ["H1 vs H2"]))

hidden = " hidden='true'"
windows = "".join(f"<window class='worksheet'{hidden} name={quoteattr(n)}><cards><edge name='left'><strip size='160'><card type='pages' /><card type='filters' /><card type='marks' /></strip></edge><edge name='top'><strip size='2147483647'><card type='columns' /></strip><strip size='2147483647'><card type='rows' /></strip><strip size='30'><card type='title' /></strip></edge></cards>{sid()}</window>" for n, *_ in S)
DASH_SHEETS = {"CX overview": ["KPI negative", "KPI service", "KPI worsening", "KPI exposure", "Monthly trend", "Department",
                               "Themes at worsening sites", "Value scenarios"],
               "Dealer investigation": ["Heatmap", "Dealer trend", "Dealer themes", "H1 vs H2"],
               "Data quality": ["Name flags", "Undated or unrated", "AI coverage", "Excluded"]}
# KPI tiles fill their zone; long dealer lists squeeze to fit instead of scrolling
FIT = {**{v: "entire-view" for v in DASH_SHEETS["CX overview"] if v.startswith("KPI")},
       "H1 vs H2": "fit-height"}
windows += "".join(f"<window class='dashboard'{hidden} name={quoteattr(n)}><viewpoints>"
                   + "".join(f"<viewpoint name={quoteattr(v)}><zoom type='{FIT[v]}' /></viewpoint>" if v in FIT
                           else f"<viewpoint name={quoteattr(v)} />" for v in vs_) + f"</viewpoints><active id='-1' />{sid()}</window>"
                   for n, vs_ in DASH_SHEETS.items())
windows += f"<window class='dashboard' maximized='true' name={quoteattr(STORY)}><viewpoints /><active id='-1' />{sid()}</window>"

xml = ("<?xml version='1.0' encoding='utf-8' ?>\n"
       "<workbook original-version='18.1' source-build='2026.2.3 (20262.26.0912.1023)' source-platform='win' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>"
       "<document-format-change-manifest><AccessibleZoneTabOrder /><AnimationOnByDefault /><MarkAnimation /><ObjectModelEncapsulateLegacy /><ObjectModelExtractV2 /><ObjectModelTableType /><SchemaViewerObjectModel /><SheetIdentifierTracking /><VConnDownstreamExtractsWithWarnings /><WindowsPersistSimpleIdentifiers /></document-format-change-manifest>"
       "<preferences><preference name='ui.encoding.shelf.height' value='24' /><preference name='ui.shelf.height' value='26' /></preferences>"
       "<datasources>" + PARAMS + "".join(d.xml() for d in SOURCES) + "</datasources>"
       "<actions>" + ACTIONS + "</actions>"
       "<worksheets>" + "".join(worksheet(n, t, ds, **kw) for n, t, ds, kw in S) + "</worksheets>"
       "<dashboards>" + "".join(D) + story + "</dashboards>"
       "<windows saved-dpi-scale-factor='1.5' source-height='44'>" + windows + "</windows></workbook>")
out = ROOT / "tableau" / "kestrel_cx.twb"
out.write_text(xml, encoding="utf-8")
print("wrote", out)
