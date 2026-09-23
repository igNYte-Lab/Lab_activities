"""Spacecraft Material Flammability Database — interactive dashboard.

IgNYte Lab, Department of Mechanical & Aerospace Engineering, NYU Tandon.
Designed to be embedded in a Google Sites page (?embed=true), so it has no
sidebar: filters sit above the charts and each view lives in its own tab.
"""

from pathlib import Path
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Settings you may want to edit ─────────────────────────────────────────────
DATA_FILE = Path(__file__).parent / "Microgravity_Database_converted.xlsx"
DATA_SHEET = 0                             # first sheet of the workbook, whatever its name
ARTICLES_SHEET = "Articles Used"

DATASET_NAME = "Spacecraft Material Flammability Database"
LAB_NAME = "IgNYte Lab"
LAB_URL = "https://www.ignytelab.org"
DATA_VERSION = "September 2026"          # update when the spreadsheet changes
CITE_AS = (
    f"M. Elimami, A. Bonhoure, A. Guibaud, low-gravity flammability experiments dataset 1960-2026."
    f"(version 1.0). https://www.ignytelab.org"
)

st.set_page_config(
    page_title=f"M. Elimami, A. Bonhoure, A. Guibaud, low-gravity flammability experiments dataset 1960-2026. · IgNYte Lab",
    page_icon=":material/local_fire_department:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Layout-only CSS (no colours, so it works in light and dark mode).
st.html("""
<style>
  .stMainBlockContainer { padding: 1.25rem 1.5rem 2.5rem; max-width: 1200px; }
  h1 { font-size: 2rem !important; padding: 0 0 0.25rem !important; }
  [data-testid="stCaptionContainer"]:has(+ *) { margin-bottom: -0.5rem; }
  [data-testid="stMetric"] { min-width: 140px; }
  [data-testid="stMetricValue"] { font-size: 1.65rem; }
  [data-testid="stMetricDelta"] svg { display: none; }
  .stTabs [data-baseweb="tab-list"] { gap: 0.25rem; }
  .stTabs [data-baseweb="tab"] { padding: 0.5rem 0.75rem; }
</style>
""")

# ── Column names in the spreadsheet ───────────────────────────────────────────
# Two spreadsheet layouts are supported; the app picks whichever one matches.
_COMMON = {
    "article": "Citation_Article (MLA)",
    "doi": "Citation_DOI",
    "material": "Sample_Material of sample",
    "o2": "Flow_Oxygen Concentration",
    "notes": "Info",
}
LAYOUTS = {
    # Original layout: values typed with their units ("1 atm", "101.3 kPa"), speeds in mm/s.
    "mixed units": _COMMON | {
        "geometry": "Sample_Geometry of Sample (flat, wire, or Cylindrical)",
        "dims": ("Sample_Dimensions of sample (Wire is in diameter, cylinder is in "
                 "radius x length, rectangle is in L x W x H)"),
        "pressure": "Flow_Pressure",
        "flow": "Flow_Flow Velocity (Co flow is + and counter flow is -)",
        "gravity": "Flow_Gravity (g/gearth)",
        "platform": ("Flow_Expireimental facility (Parabolic Aircraft, Drop Tower, "
                     "Spacecraft, Sounding Rocket, Ground)"),
        "outcome": "Outputs_Ignition (Yes/No)",
        "fsr": "Outputs_FSR (Flame Spread Rate)",
    },
    # SI layout: pressure in Pa, speeds in m/s, dimensions in metres.
    "SI units": _COMMON | {
        "geometry": "Sample_Geometry of Sample",
        "dims": ("Sample_Dimensions of sample (Wire is L m x D m; Cylinder is Core Diameter m "
                 "x Outer Diameter m; Flat is L m x H m x W m; Spherical is D m)"),
        "pressure": "Flow_Pressure (Pa)",
        "flow": "Flow_Flow Velocity (m/s)",
        "gravity": "Flow_Gravity",
        "platform": "Extra_Facility",
        "outcome": "Outputs_Ignition",
        "fsr": "Outputs_FSR (m/s)",
    },
}
PA_TO_KPA = 1e-3
MS_TO_MMS = 1e3

O2, PRESSURE, FLOW, GRAVITY, FSR = (
    "O2 (%)", "Pressure (kPa)", "Flow velocity (mm/s)", "Gravity (g)", "FSR (mm/s)")
CONDITIONS = [O2, PRESSURE, FLOW, GRAVITY]
AXIS_TITLES = {
    O2: "Oxygen concentration (% by volume)",
    PRESSURE: "Pressure (kPa)",
    FLOW: "Flow velocity (mm/s)  ← opposed · concurrent →",
    GRAVITY: "Gravity level (g / g₀)",
    FSR: "Flame spread rate (mm/s)",
}

PROPAGATION, EXTINCTION = "Propagation", "Extinction"
FLOW_ORDER = ["Opposed flow", "Concurrent flow", "No forced flow", "Flow not reported"]
GRAVITY_ORDER = ["Microgravity (≤ 0.01 g)", "Partial gravity (0.01–0.9 g)",
                 "Normal gravity (0.9–1.1 g)", "Hypergravity (> 1.1 g)"]
NOT_REPORTED = "Not reported"

# Chart colours, validated for colour-vision deficiency on each surface.
# A scatter can only keep 3 categorical hues distinguishable; the rest are grey.
PALETTES = {
    "light": {"cat": ["#2a78d6", "#eb6834", "#1baf7a"], "grey": "#9b9a94",
              "ordinal": ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"],
              "surface": "#ffffff"},
    "dark": {"cat": ["#3987e5", "#d95926", "#199e70"], "grey": "#7a7974",
             "ordinal": ["#184f95", "#2a78d6", "#6da7ec", "#b7d3f6"],
             "surface": "#0e1117"},
}


# ── Parsing helpers ───────────────────────────────────────────────────────────
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?")
PRESSURE_TO_KPA = {"kpa": 1.0, "atm": 101.325, "psia": 6.89476, "psi": 6.89476,
                   "mpa": 1000.0, "hpa": 0.1, "bar": 100.0, "mbar": 0.1,
                   "torr": 0.133322, "mmhg": 0.133322, "pa": 0.001}


def first_number(v):
    if pd.isna(v):
        return np.nan
    if isinstance(v, (int, float, np.number)):
        return float(v)
    m = NUM_RE.search(str(v))
    return float(m.group()) if m else np.nan


def parse_o2(v):
    """Return O2 in % by volume. Fractions (≤ 1) are converted; '26.9% O2' is kept."""
    x = first_number(v)
    if np.isnan(x):
        return np.nan
    return x * 100 if x <= 1.0 else x


def parse_pressure(v):
    """Return pressure in kPa, converting atm / psia / MPa / hPa. Bare numbers are kPa."""
    if pd.isna(v):
        return np.nan
    if isinstance(v, (int, float, np.number)):
        return float(v)
    s = str(v).strip().lower()
    m = NUM_RE.search(s)
    if not m:
        return np.nan
    unit = re.search(r"[a-z]+", s[m.end():])
    factor = PRESSURE_TO_KPA.get(unit.group(), np.nan) if unit else 1.0
    return float(m.group()) * factor


def parse_outcome(v):
    s = str(v).strip().lower()
    if s.startswith("y"):
        return PROPAGATION
    if s.startswith("n") and s != "nan":
        return EXTINCTION
    return None


def flow_direction(fv):
    if pd.isna(fv):
        return FLOW_ORDER[3]
    if fv < 0:
        return FLOW_ORDER[0]
    if fv > 0:
        return FLOW_ORDER[1]
    return FLOW_ORDER[2]


def gravity_level(g):
    if pd.isna(g):
        return NOT_REPORTED
    if g <= 0.01:
        return GRAVITY_ORDER[0]
    if g < 0.9:
        return GRAVITY_ORDER[1]
    if g <= 1.1:
        return GRAVITY_ORDER[2]
    return GRAVITY_ORDER[3]


def clean_text(v):
    if pd.isna(v):
        return None
    s = re.sub(r"\s+", " ", str(v).replace("\xa0", " ")).strip()
    return None if s in ("", "-", "nan", "None") else s


def clean_geometry(v):
    s = clean_text(v)
    if s is None:
        return None
    s = s.title()
    return re.sub(r"^Cylinder\b", "Cylindrical", s)


def clean_dimensions(v):
    s = clean_text(v)
    if s is None:
        return None
    return re.sub(r"(\d)\s*mm\b", r"\1 mm", s)


def clean_platform(v):
    s = str(v).lower()
    if pd.isna(v) or s in ("", "-", "nan"):
        return NOT_REPORTED
    if "drop" in s and "centrifuge" in s:
        return "Drop tower + centrifuge"
    if "drop" in s:
        return "Drop tower"
    if "parabolic" in s:
        return "Parabolic flight"
    if "spacecraft" in s or "iss" in s:
        return "Spacecraft / ISS"
    if "centrifuge" in s:
        return "Centrifuge"
    if "rocket" in s:
        return "Sounding rocket"
    if "ground" in s:
        return "Ground laboratory"
    return str(v).strip()


# In the spreadsheet, the word "microgravity" was replaced by "0" inside
# citations (e.g. "... in 0."). Restore it for display.
MICROGRAVITY_RE = re.compile(r"(?<![\w.\-/:])0(?![\w\-/%:])(?!\.\d)")


def restore_microgravity(s):
    def repl(m):
        before = s[:m.start()].rstrip()
        capital = not before or before[-1] in ".“\"'‘:("
        return "Microgravity" if capital else "microgravity"
    return MICROGRAVITY_RE.sub(repl, s)


TITLE_RE = re.compile(r"[“\"]([^”\"]{8,})[”\"]|[‘']([^’']{15,})[’']")
YEAR_RE = re.compile(r"(?<![\w\-–—/])(19[5-9]\d|20[0-2]\d)(?!\d)")   # skips report numbers like "X-1992"


def article_title(s):
    m = TITLE_RE.search(s)
    if m:
        return (m.group(1) or m.group(2)).strip(" .,")
    m = re.search(r"\((?:19|20)\d\d\)\s*(.+)$", s)      # "Name et al. (2017) Title"
    if m and re.search(r"[A-Za-z]{4,}", m.group(1)):
        return m.group(1).strip(" .,")
    return None


def article_key(s):
    t = article_title(s) or s
    return re.sub(r"[^a-z0-9]", "", restore_microgravity(t).lower())


def article_label(s):
    title = article_title(s)
    authors = s[:s.find(title)] if title and title in s else s.split("(")[0]
    surname = re.match(r"\s*([^\s,.(]+)", s).group(1)
    multi = bool(re.search(r"et al|\band\b|;|&", authors)) or authors.count(",") >= 3
    paren = re.search(r"\((19[5-9]\d|20[0-2]\d)\)", s)
    years = YEAR_RE.findall(s)
    year = paren.group(1) if paren else (years[0] if years else "n.d.")
    label = f"{surname}{' et al.' if multi else ''} ({year})"
    if title:
        t = restore_microgravity(title)
        label += " — " + (t if len(t) <= 60 else t[:58].rstrip() + "…")
    return label


def doi_link(v):
    """Return (url or None, display text) for a DOI / report identifier."""
    s = clean_text(v)
    if s is None:
        return None, None
    m = re.search(r"10\.\d{4,9}/\S+", s)
    if m:
        doi = m.group(0).rstrip(".")
        return f"https://doi.org/{doi}", doi
    if s.startswith("http"):
        url = s.replace(" ", "")
        return url, url
    return None, s


def fmt_num(x, digits=3):
    if pd.isna(x):
        return "—"
    return f"{x:.{digits}g}" if abs(x) < 1e4 else f"{x:,.0f}"


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading the database…")
def load_data(path: str):
    raw = pd.read_excel(path, sheet_name=DATA_SHEET, header=[0, 1])
    raw.columns = [
        f"{str(a).strip()}_{str(b).strip()}" if "Unnamed" not in str(b) else str(a).strip()
        for a, b in raw.columns
    ]
    # Pick the layout whose columns are all present.
    missing_by_layout = {name: [c for c in cols.values() if c not in raw.columns]
                         for name, cols in LAYOUTS.items()}
    layout = next((n for n, miss in missing_by_layout.items() if not miss), None)
    if layout is None:
        closest = min(missing_by_layout, key=lambda n: len(missing_by_layout[n]))
        raise KeyError("columns not found in the spreadsheet: "
                       + "; ".join(missing_by_layout[closest]))
    SRC = LAYOUTS[layout]
    si = layout == "SI units"
    raw = raw.dropna(subset=[SRC["article"]]).reset_index(drop=True)

    df = pd.DataFrame(index=raw.index)
    articles = raw[SRC["article"]].astype(str).str.strip()
    df["study_key"] = articles.map(article_key)
    df["Material"] = raw[SRC["material"]].map(clean_text)
    df["Geometry"] = raw[SRC["geometry"]].map(clean_geometry)
    df["Dimensions"] = raw[SRC["dims"]].map(clean_dimensions)
    df["Test platform"] = raw[SRC["platform"]].map(clean_platform)
    df[O2] = raw[SRC["o2"]].map(parse_o2)
    if si:
        df[PRESSURE] = raw[SRC["pressure"]].map(first_number) * PA_TO_KPA
        df[FLOW] = raw[SRC["flow"]].map(first_number) * MS_TO_MMS
    else:
        df[PRESSURE] = raw[SRC["pressure"]].map(parse_pressure)   # converts atm, psia, MPa, hPa
        df[FLOW] = raw[SRC["flow"]].map(first_number)
    df[GRAVITY] = raw[SRC["gravity"]].map(first_number)
    df["Outcome"] = raw[SRC["outcome"]].map(parse_outcome)
    df[FSR] = pd.to_numeric(raw[SRC["fsr"]], errors="coerce") * (MS_TO_MMS if si else 1.0)
    df["Flow direction"] = df[FLOW].map(flow_direction)
    df["Gravity level"] = df[GRAVITY].map(gravity_level)
    df["Notes"] = raw[SRC["notes"]].map(clean_text)

    # One entry per study: the same paper is sometimes cited in several ways.
    # DOIs in the data sheet were auto-incremented row by row, so prefer the DOI
    # from the "Articles Used" sheet, then the first row of each study.
    curated = {}
    try:
        art = pd.read_excel(path, sheet_name=ARTICLES_SHEET)
        for mla, doi in zip(art.iloc[:, 0], art.iloc[:, 1]):
            if pd.notna(mla) and pd.notna(doi):
                curated.setdefault(article_key(str(mla)), doi)
    except Exception:
        pass

    grp = pd.DataFrame({"key": df["study_key"], "article": articles, "doi": raw[SRC["doi"]]})
    rows = []
    for key, g in grp.groupby("key", sort=False):
        longest = max(g["article"].unique(), key=len)
        first_doi = g["doi"].dropna()
        url, text = doi_link(curated.get(key, first_doi.iloc[0] if len(first_doi) else None))
        rows.append({"key": key, "label": article_label(longest),
                     "citation": restore_microgravity(longest), "url": url, "doi": text})
    studies = pd.DataFrame(rows)
    dup = studies["label"].duplicated(keep=False)
    studies.loc[dup, "label"] += " [" + (studies[dup].groupby("label").cumcount() + 1).astype(str) + "]"
    df["Study"] = df["study_key"].map(studies.set_index("key")["label"])

    # Pre-formatted hover text (cheap to reuse on every rerun).
    df["hover"] = (
        "<b>" + df["Study"].str.split(" — ").str[0] + "</b><br>"
        + df["Material"].fillna("Material not reported") + " · "
        + df["Geometry"].fillna("geometry n/a") + " · " + df["Dimensions"].fillna("size n/a")
        + "<br>" + df["Test platform"]
        + "<br>O₂ " + df[O2].map(lambda x: fmt_num(x) + " %")
        + " · P " + df[PRESSURE].map(lambda x: fmt_num(x, 4) + " kPa")
        + "<br>Flow " + df[FLOW].map(lambda x: fmt_num(x) + " mm/s")
        + " · g " + df[GRAVITY].map(lambda x: fmt_num(x) + " g₀")
        + df[FSR].map(lambda x: "" if pd.isna(x) else f"<br>Spread rate {fmt_num(x)} mm/s")
    )
    return df, studies


try:
    data, studies = load_data(str(DATA_FILE))
except Exception as exc:  # never fall back to invented data on a public page
    st.error(f"The database file could not be loaded ({exc}). "
             f"Check that `{DATA_FILE.name}` sits next to `app.py` and that the column "
             f"names in the `LAYOUTS` block of `app.py` match the spreadsheet.")
    st.stop()

theme = st.context.theme.type if st.context.theme.type in PALETTES else "light"
PAL = PALETTES[theme]
PLOT_CONFIG = {"displaylogo": False,
               "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
               "toImageButtonOptions": {"format": "png", "scale": 2}}

# ── Header ────────────────────────────────────────────────────────────────────
st.caption(f":violet[**{LAB_NAME} · NYU Tandon School of Engineering**]")
st.title(DATASET_NAME, anchor=False)
st.markdown(
    f"{len(data):,} flame-spread and extinction tests on solid materials, from "
    f"{studies.shape[0]} published studies, covering microgravity, partial gravity, "
    "normal gravity and hypergravity. Filter the tests below, then explore them in the tabs."
)

# ── Filters ───────────────────────────────────────────────────────────────────
ALL = "All"
FILTER_KEYS = {"f_study": "Study", "f_platform": "Test platform",
               "f_geometry": "Geometry", "f_material": "Material"}


def reset_filters():
    for k in FILTER_KEYS:
        st.session_state[k] = ALL
    st.session_state["f_dims"] = []
    for k in [k for k in st.session_state if str(k).startswith("rng_")]:
        del st.session_state[k]


filt = data
with st.container(border=True):
    def select_filter(slot, label, key, column):
        global filt
        options = sorted(filt[column].dropna().unique())
        if st.session_state.get(key, ALL) not in [ALL, *options]:
            st.session_state[key] = ALL
        with slot:
            choice = st.selectbox(
                label, [ALL, *options], key=key,
                format_func=lambda v: f"All ({len(options)})" if v == ALL else v)
        if choice != ALL:
            filt = filt[filt[column] == choice]

    r = st.columns([2.4, 1.4, 1.3, 1.6, 1.7])
    select_filter(r[0], "Study", "f_study", "Study")
    select_filter(r[1], "Test platform", "f_platform", "Test platform")
    select_filter(r[2], "Sample geometry", "f_geometry", "Geometry")
    select_filter(r[3], "Material", "f_material", "Material")

    dim_options = sorted(filt["Dimensions"].dropna().unique())
    if "f_dims" in st.session_state:
        st.session_state["f_dims"] = [d for d in st.session_state["f_dims"] if d in dim_options]
    with r[4]:
        sel_dims = st.multiselect("Sample dimensions", dim_options, key="f_dims",
                                  placeholder=f"All ({len(dim_options)})")
    if sel_dims:
        filt = filt[filt["Dimensions"].isin(sel_dims)]

    active = sum(st.session_state.get(k, ALL) != ALL for k in FILTER_KEYS) + bool(sel_dims)
    bar = st.container(horizontal=True, vertical_alignment="center")
    bar.caption(f"Showing **{len(filt):,}** of {len(data):,} tests from "
                f"**{filt['study_key'].nunique()}** studies"
                + (f" · {active} filter{'s' if active > 1 else ''} active" if active else ""))
    bar.space("stretch")
    bar.button("Reset filters", icon=":material/restart_alt:", type="tertiary",
               on_click=reset_filters, disabled=not active)

if filt.empty:
    st.warning("No tests match these filters. Try removing one, or reset them.")
    st.stop()

# ── Key figures ───────────────────────────────────────────────────────────────
n = len(filt)
n_prop = int((filt["Outcome"] == PROPAGATION).sum())
n_ext = int((filt["Outcome"] == EXTINCTION).sum())
fsr_vals = filt[FSR].dropna()
kpis = st.container(horizontal=True, gap="small")
k = [kpis] * 4
k[0].metric("Tests", f"{n:,}", delta=f"from {filt['study_key'].nunique()} studies",
            delta_color="off", delta_arrow="off", border=True, width="stretch")
k[1].metric("Flame propagated", f"{n_prop:,}", delta=f"{n_prop / n:.0%} of tests",
            delta_color="off", delta_arrow="off", border=True, width="stretch")
k[2].metric("Flame extinguished", f"{n_ext:,}", delta=f"{n_ext / n:.0%} of tests",
            delta_color="off", delta_arrow="off", border=True, width="stretch")
k[3].metric("Median spread rate",
            f"{fsr_vals.median():.2f} mm/s" if len(fsr_vals) else "—",
            delta=f"from {len(fsr_vals):,} measured tests" if len(fsr_vals) else "no rates measured",
            delta_color="off", delta_arrow="off", border=True, width="stretch")


# ── Chart helpers ─────────────────────────────────────────────────────────────
def base_layout(fig, x, y, height=540, log_y=False):
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, xanchor="left",
                    title_text="", groupclick="toggleitem"),
        hoverlabel=dict(align="left"),
        xaxis_title=AXIS_TITLES[x], yaxis_title=AXIS_TITLES[y],
    )
    if log_y:
        fig.update_yaxes(type="log")
    return fig


def slider_format(var):
    return lambda v: fmt_num(v, 4)


def range_filter(slot, frame, var):
    """Select-slider over the values that actually occur. Rows with a missing
    value are only excluded once the user narrows the range."""
    key = f"rng_{var}"
    values = [float(v) for v in np.sort(frame[var].dropna().unique())]
    if len(values) < 2:
        slot.caption(f"{var}: " + (f"single value ({fmt_num(values[0])})" if values else "no values"))
        return frame
    current = st.session_state.get(key)
    if current is not None and (current[0] not in values or current[1] not in values):
        del st.session_state[key]
    lo, hi = slot.select_slider(var, options=values, value=(values[0], values[-1]),
                                key=key, format_func=slider_format(var))
    if lo == values[0] and hi == values[-1]:
        return frame
    return frame[frame[var].between(lo, hi)]


def point_marker(color, filled=True, size=8):
    if filled:
        return dict(symbol="circle", size=size, color=color, opacity=0.85,
                    line=dict(width=1, color=PAL["surface"]))
    return dict(symbol="circle-open", size=size, color=color, opacity=0.9,
                line=dict(width=1.6, color=color))


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_map, tab_fsr, tab_data, tab_sources, tab_about = st.tabs(
    ["Flammability map", "Flame spread rate", "Data", "Sources", "About & glossary"])

# Flammability map ─────────────────────────────────────────────────────────────
with tab_map:
    c = st.columns(2)
    x_var = c[0].selectbox("Horizontal axis", CONDITIONS, index=CONDITIONS.index(GRAVITY), key="map_x")
    y_choices = [v for v in CONDITIONS if v != x_var]
    if st.session_state.get("map_y") not in y_choices:
        st.session_state["map_y"] = O2 if O2 in y_choices else y_choices[0]
    y_var = c[1].selectbox("Vertical axis", y_choices, key="map_y")

    others = [v for v in CONDITIONS if v not in (x_var, y_var)]
    s = st.columns(2)
    frame = filt
    for slot, var in zip(s, others):
        frame = range_filter(slot, frame, var)

    plot = frame.dropna(subset=[x_var, y_var])
    plot = plot[plot["Outcome"].notna()]
    colors = dict(zip(FLOW_ORDER, PAL["cat"] + [PAL["grey"]]))

    fig = go.Figure()
    for rank, regime in enumerate(FLOW_ORDER):
        sub_r = plot[plot["Flow direction"] == regime]
        if sub_r.empty:
            continue
        for outcome, filled in ((PROPAGATION, True), (EXTINCTION, False)):
            sub = sub_r[sub_r["Outcome"] == outcome]
            if sub.empty:
                continue
            fig.add_trace(go.Scatter(
                x=sub[x_var], y=sub[y_var], mode="markers",
                name=f"{outcome} ({len(sub):,})",
                legendgroup=regime, legendgrouptitle_text=regime, legendrank=rank * 10 + (0 if filled else 1),
                marker=point_marker(colors[regime], filled),
                text=sub["hover"],
                hovertemplate=f"%{{text}}<extra>{outcome} · {regime.lower()}</extra>",
            ))
    # Draw grey "not reported" points underneath the coloured ones.
    fig.data = sorted(fig.data, key=lambda t: t.legendgroup != FLOW_ORDER[3], reverse=False)
    base_layout(fig, x_var, y_var)
    st.plotly_chart(fig, config=PLOT_CONFIG, key="map_chart")

    hidden = len(frame) - len(plot)
    st.caption(
        "**Filled circles**: the flame propagated for the duration of the experiment · **open circles**: the sample did not ignite, or the flame went out before the end of the experiment.\n "
        "Drag to zoom, double-click to reset, click a legend entry to hide it."
        + (f" {hidden:,} tests in this selection have no value for one of the axes or no "
           "reported outcome, so they are not plotted." if hidden else "")
    )

# Flame spread rate ────────────────────────────────────────────────────────────
with tab_fsr:
    COLOR_BY = ["Flow direction", "Gravity level", "Geometry", "Test platform", "Material", "Dimensions"]
    c = st.columns([1.2, 1.2, 0.8], vertical_alignment="bottom")
    fx = c[0].selectbox("Horizontal axis", CONDITIONS, key="fsr_x")
    color_by = c[1].selectbox("Colour points by", COLOR_BY, key="fsr_color",
                              format_func=lambda v: "Sample geometry" if v == "Geometry" else
                              ("Sample dimensions" if v == "Dimensions" else v))
    log_y = c[2].toggle("Log scale", key="fsr_log", help="Useful because spread rates span 0.01–200 mm/s.")

    fsr_df = filt.dropna(subset=[fx, FSR])
    if log_y:
        fsr_df = fsr_df[fsr_df[FSR] > 0]

    # Colour assignment: fixed for flow & gravity; top-3 + grey otherwise.
    groups = fsr_df[color_by].fillna(NOT_REPORTED)
    if color_by == "Flow direction":
        order = [g for g in FLOW_ORDER if g in set(groups)]
        cmap = dict(zip(FLOW_ORDER, PAL["cat"] + [PAL["grey"]]))
        note = ""
    elif color_by == "Gravity level":
        order = [g for g in GRAVITY_ORDER + [NOT_REPORTED] if g in set(groups)]
        cmap = dict(zip(GRAVITY_ORDER, PAL["ordinal"])) | {NOT_REPORTED: PAL["grey"]}
        note = " Darker blue means higher gravity." if theme == "light" else " Lighter blue means higher gravity."
    else:
        counts = groups[groups != NOT_REPORTED].value_counts()
        top = list(counts.index[:3])
        groups = groups.where(groups.isin(top), "Other")
        order = top + (["Other"] if (groups == "Other").any() else [])
        cmap = dict(zip(top, PAL["cat"])) | {"Other": PAL["grey"]}
        note = (" Colours mark the three most common groups in this selection; the rest are grey."
                " Narrow the filters above to compare specific groups." if len(counts) > 3 else "")

    fig2 = go.Figure()
    for g in sorted(order, key=lambda g: g in ("Other", NOT_REPORTED, FLOW_ORDER[3])):
        sub = fsr_df[groups == g]
        fig2.add_trace(go.Scatter(
            x=sub[fx], y=sub[FSR], mode="markers", name=f"{g} ({len(sub):,})",
            marker=point_marker(cmap.get(g, PAL["grey"]), True, size=8),
            text=sub["hover"], hovertemplate=f"%{{text}}<extra>{g}</extra>",
            legendrank=order.index(g),
        ))
    fig2.data = sorted(fig2.data, key=lambda t: not t.name.startswith(("Other", NOT_REPORTED, FLOW_ORDER[3])))
    base_layout(fig2, fx, FSR, log_y=log_y)
    if fsr_df.empty:
        st.info("None of the tests in this selection has a measured spread rate.")
    else:
        st.plotly_chart(fig2, config=PLOT_CONFIG, key="fsr_chart")
    st.caption(
        f"{len(fsr_df):,} tests with a measured spread rate.{note}"
        + (" Rates of zero are hidden on the log scale." if log_y else "")
    )

# Data ─────────────────────────────────────────────────────────────────────────
with tab_data:
    TABLE_COLS = ["Study", "Material", "Geometry", "Dimensions", "Test platform",
                  O2, PRESSURE, FLOW, "Flow direction", GRAVITY, "Outcome", FSR, "Notes"]
    st.dataframe(
        filt[TABLE_COLS], hide_index=True, height=440,
        column_config={
            "Study": st.column_config.TextColumn(width="medium", pinned=True),
            O2: st.column_config.NumberColumn("O₂ (%)", format="%.2f"),
            PRESSURE: st.column_config.NumberColumn(format="%.1f"),
            FLOW: st.column_config.NumberColumn("Flow (mm/s)", format="%.1f"),
            GRAVITY: st.column_config.NumberColumn(format="%.3g"),
            FSR: st.column_config.NumberColumn("Spread rate (mm/s)", format="%.3g"),
        },
    )
    export = filt[TABLE_COLS].merge(
        studies[["label", "citation", "doi"]].rename(columns={"label": "Study", "citation": "Citation", "doi": "DOI"}),
        on="Study", how="left")
    b = st.container(horizontal=True, vertical_alignment="center")
    b.download_button(f"Download these {len(filt):,} tests (CSV)", export.to_csv(index=False).encode("utf-8"),
                      file_name="flammability_database_selection.csv", mime="text/csv",
                      icon=":material/download:", on_click="ignore")
    b.caption("Units: O₂ in % by volume · pressure in kPa · flow velocity and spread rate in mm/s "
              "(converted where the spreadsheet uses other units), negative flow for opposed "
              "flow · gravity in multiples of Earth gravity (g₀).")

# Sources ──────────────────────────────────────────────────────────────────────
MD_ESCAPE = re.compile(r"([\\`*_\[\]$~<>#|])")


def md_escape(s):
    return MD_ESCAPE.sub(r"\\\1", s)


with tab_sources:
    counts = filt.groupby("study_key").size()
    shown = studies[studies["key"].isin(counts.index)].assign(n=lambda d: d["key"].map(counts))
    shown = shown.sort_values("label", key=lambda s: s.str.lower())
    st.caption(f"{len(shown)} studies contribute to the current selection, with the number of tests taken from each.")
    lines = []
    for r in shown.itertuples():
        url = r.url if isinstance(r.url, str) else None
        ident = r.doi if isinstance(r.doi, str) else None
        if ident and ident.lower() in r.citation.lower():
            ident = url = None                       # already part of the citation text
        link = f" [{md_escape(ident)}]({url})" if url else (f" {md_escape(ident)}" if ident else "")
        lines.append(f"**{md_escape(r.label.split(' — ')[0])}** · {r.n:,} tests  \n"
                     f"{md_escape(r.citation)}{link}")
    st.markdown("\n\n".join(lines))

# About & glossary ─────────────────────────────────────────────────────────────
with tab_about:
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.subheader("About this database", anchor=False)
        st.markdown(
            f"This database gathers published experiments on the flammability of solid materials "
            f"used or proposed for spacecraft. Each row is one test: a sample of a given material, "
            f"geometry and size, exposed to a controlled atmosphere (oxygen concentration, pressure, "
            f"flow velocity) at a given gravity level. It records whether the flame propagated or "
            f"went out and, when measured, how fast it spread.\n\n"
            f"Data were extracted from {studies.shape[0]} papers and technical reports by the "
            f"[{LAB_NAME}]({LAB_URL}) at NYU Tandon. Version: {DATA_VERSION}. \n"
            f"The initial website was developed by Jaskaran Singh Hanspal in 2026."
        )
        st.subheader("How to use it", anchor=False)
        st.markdown(
            "- **Filter** by study, test platform, sample geometry, material or size in the panel at the top. "
            "Every tab follows these filters.\n"
            "- **Flammability map**: choose any two test conditions as axes; the two sliders narrow "
            "the other two conditions. Only values that occur in the data can be selected.\n"
            "- **Charts**: drag to zoom, double-click to reset, click legend entries to show or hide "
            "groups, and use the camera icon to save a PNG.\n"
            "- **Data**: browse or download the selected tests with full citations."
        )
        st.subheader("How to cite", anchor=False)
        st.code(CITE_AS, language=None, wrap_lines=True)
        st.markdown("Please also cite the original studies listed in the **Sources** tab.")
        st.subheader("Corrections", anchor=False)
        st.markdown(f"Spotted an error or want a study added? Get in touch with "
                    f"[Dr. Augustin Guibaud](mailto:acg10084@nyu.edu).")
    with right:
        st.subheader("Glossary", anchor=False)
        st.markdown(
            "**Flame propagation / extinction**: whether the flame spread along the sample after "
            "ignition, or went out. Recorded as *Ignition = Yes / No* in the source spreadsheet.\n\n"
            "**Flame spread rate**: speed of the flame front along the sample, in mm/s.\n\n"
            "**Opposed flow**: the surrounding gas flows against the direction of flame spread "
            "(negative flow velocity).\n\n"
            "**Concurrent flow**: the gas flows in the same direction as the flame "
            "(positive flow velocity).\n\n"
            "**No forced flow**: no imposed flow (0 mm/s). On the ground, buoyancy still drives a flow; "
            "in microgravity the gas is quiescent.\n\n"
            "**Oxygen concentration**: oxygen share of the atmosphere, % by volume (air ≈ 21 %).\n\n"
            "**Limiting oxygen concentration (LOC)**: the lowest oxygen level at which a flame can "
            "keep spreading. On the flammability map it is the boundary between filled and open circles.\n\n"
            "**Gravity level**: acceleration relative to Earth gravity, g₀. Microgravity ≈ 0, "
            "Moon ≈ 0.17, Mars ≈ 0.38, hypergravity > 1.\n\n"
            "**Test platforms**: *drop towers* give a few seconds of microgravity, *parabolic flights* "
            "about 20 s per parabola, *sounding rockets* several minutes, and *spacecraft / ISS* "
            "long-duration tests. *Centrifuges* produce hypergravity; *ground laboratory* tests run at 1 g."
        )
