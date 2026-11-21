"""
clean.py — turns the raw datasets into data/places.csv (the file the model and backend use).

Run from the repo root:
    python pipeline/clean.py

Inputs (data/raw/):
  1. Selected_Food_Report_*/selected food table *.xlsx   NBS food prices (zone averages)
  2. nigeria_uscb_202001.xlsx                            USCB: population, under-5 mortality, wealth
  3. ndhs_stunting.csv              (optional)           NDHS 2024 stunting by state, typed by hand
  4. crc_cities.csv                 (optional)           colorectal cancer registry index by state
  5. data/places_config.csv                              our places + interview demand
  6. soya beans.csv / awara.csv / beans.csv              Google Trends "interest by region"
  7. hotosm_*/points_of_interest.geojson                 OpenStreetMap shops & food outlets
  8. data/products.csv                                   our products + the Trends term for each

Output:
  data/places.csv   one row per place, the Project Spec fields + market_type
                    + demand_<term> / label_demand_<term> for each Google Trends term
  data/states.csv   all 37 states with scores and their k-means market type
  data/sources.csv  every source used
"""

import glob
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from marketlens_ai.scoring import suggest_capacity  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cluster import assign_market_types  # noqa: E402

RAW = os.path.join(ROOT, "data", "raw")
OUT_PLACES = os.path.join(ROOT, "data", "places.csv")
OUT_SOURCES = os.path.join(ROOT, "data", "sources.csv")
OUT_STATES = os.path.join(ROOT, "data", "states.csv")
CONFIG = os.path.join(ROOT, "data", "places_config.csv")
PRODUCTS = os.path.join(ROOT, "data", "products.csv")

# --- state -> geopolitical zone (NBS reports prices by zone) ---
ZONES = {
    "NORTH CENTRAL": ["BENUE", "KOGI", "KWARA", "NASARAWA", "NIGER", "PLATEAU", "FCT"],
    "NORTH EAST": ["ADAMAWA", "BAUCHI", "BORNO", "GOMBE", "TARABA", "YOBE"],
    "NORTH WEST": ["JIGAWA", "KADUNA", "KANO", "KATSINA", "KEBBI", "SOKOTO", "ZAMFARA"],
    "SOUTH EAST": ["ABIA", "ANAMBRA", "EBONYI", "ENUGU", "IMO"],
    "SOUTH SOUTH": ["AKWA IBOM", "BAYELSA", "CROSS RIVER", "DELTA", "EDO", "RIVERS"],
    "SOUTH WEST": ["EKITI", "LAGOS", "OGUN", "ONDO", "OSUN", "OYO"],
}
STATE_TO_ZONE = {s: z for z, states in ZONES.items() for s in states}

MEAT_ITEMS = ["Beef Boneless", "Chicken meat (Frozen)", "Goat Meat Bone in"]

# OSM tags that point to processed-meat buying (supermarkets, fast food, etc.)
PROCESSED_MEAT_TAGS = {
    "shop": {"supermarket", "mall", "convenience", "butcher"},
    "amenity": {"fast_food", "restaurant", "cafe"},
}


# ---------------------------------------------------------------- helpers
def norm_state(name) -> str:
    """One spelling for every state: upper case, 'FCT' for Abuja, no ' STATE'."""
    if name is None or (isinstance(name, float) and np.isnan(name)):
        return ""
    s = str(name).strip().upper().replace("’", "'")
    if s.endswith(" STATE"):
        s = s[: -len(" STATE")]
    if s in ("FEDERAL CAPITAL TERRITORY", "ABUJA", "FCT ABUJA", "FCT"):
        return "FCT"
    if s == "REPUBLIC OF NIGER":          # Google Trends mislabels Niger State this way
        return "NIGER"
    return s


def term_slug(term: str) -> str:
    """'soya beans' -> 'soya_beans' (used in column names)."""
    return "_".join(str(term).strip().lower().split())


def norm_lga(name) -> str:
    return str(name).strip().upper().replace("’", "'") if name is not None else ""


def scale_0_100(series: pd.Series) -> pd.Series:
    """Min-max scale to 0-100 (NaN stays NaN)."""
    lo, hi = series.min(), series.max()
    if pd.isna(lo) or hi == lo:
        return series * 0 + 50
    return (series - lo) / (hi - lo) * 100


def rank_0_100(series: pd.Series) -> pd.Series:
    """Percentile rank 0-100. Robust when one state is a big outlier."""
    return series.rank(pct=True) * 100


def find(pattern: str):
    hits = glob.glob(os.path.join(RAW, pattern), recursive=True)
    return hits[0] if hits else None


def say(msg: str):
    print(f"  - {msg}")


# ---------------------------------------------------------------- 1. USCB
def load_uscb() -> pd.DataFrame:
    path = find("nigeria_uscb_*.xlsx")
    if not path:
        sys.exit("Missing data/raw/nigeria_uscb_202001.xlsx")

    def sheet(name):
        df = pd.read_excel(path, sheet_name=name)
        return df.iloc[1:]          # row 0 = long descriptions

    pop = sheet("Population Estimates")
    health = sheet("Health")
    poverty = sheet("Poverty")

    states = pop[pop["ADM_LEVEL"] == 1][["ADM1_NAME", "EST_POP"]].copy()
    states["state"] = states["ADM1_NAME"].map(norm_state)
    states["population"] = pd.to_numeric(states["EST_POP"], errors="coerce")

    lgas = pop[pop["ADM_LEVEL"] == 2][["ADM1_NAME", "ADM2_NAME", "EST_POP"]].copy()
    lgas["state"] = lgas["ADM1_NAME"].map(norm_state)
    lgas["lga"] = lgas["ADM2_NAME"].map(norm_lga)
    lgas["population"] = pd.to_numeric(lgas["EST_POP"], errors="coerce")

    h = health[health["ADM_LEVEL"] == 1][["ADM1_NAME", "HLT_MO_UN5"]].copy()
    h["state"] = h["ADM1_NAME"].map(norm_state)
    h["u5mr"] = pd.to_numeric(h["HLT_MO_UN5"], errors="coerce")
    h.loc[h["u5mr"] < 0, "u5mr"] = np.nan          # -999 = missing

    p = poverty[poverty["ADM_LEVEL"] == 1][["ADM1_NAME", "POV_WI_POO", "POV_WI_SEC"]].copy()
    p["state"] = p["ADM1_NAME"].map(norm_state)
    p["poor40"] = (pd.to_numeric(p["POV_WI_POO"], errors="coerce")
                   + pd.to_numeric(p["POV_WI_SEC"], errors="coerce"))

    out = (states[["state", "population"]]
           .merge(h[["state", "u5mr"]], on="state", how="left")
           .merge(p[["state", "poor40"]], on="state", how="left"))
    say(f"USCB: {len(out)} states, {len(lgas)} LGAs")
    return out, lgas[["state", "lga", "population"]]


# ---------------------------------------------------------------- 2. NBS prices
def load_meat_prices() -> pd.DataFrame:
    path = find("**/selected food table*.xlsx")
    if not path:
        sys.exit("Missing NBS 'selected food table ... .xlsx' in data/raw/")
    zone = pd.read_excel(path, sheet_name="Zone All item")
    zone["Item Label"] = zone["Item Label"].astype(str).str.strip()
    meat = zone[zone["Item Label"].isin(MEAT_ITEMS)]
    if len(meat) != len(MEAT_ITEMS):
        found = list(meat["Item Label"])
        sys.exit(f"Expected meat items {MEAT_ITEMS}, found {found}")

    zone_cols = [c for c in zone.columns if str(c).strip().upper() in ZONES]
    zone_avg = meat[zone_cols].astype(float).mean()        # average of the 3 meats
    national = zone_avg.mean()
    ratio = (zone_avg / national).rename(lambda c: str(c).strip().upper())

    rows = [{"state": s, "zone": z, "meat_price_ratio": ratio[z]}
            for s, z in STATE_TO_ZONE.items()]
    say("NBS meat price ratio by zone: "
        + ", ".join(f"{z.title()} {ratio[z]:.2f}" for z in ratio.index))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 3. NDHS (optional)
def load_stunting():
    path = find("ndhs_stunting.csv")
    if not path:
        say("NDHS stunting not found -> using under-5 mortality + poverty proxy")
        return None
    df = pd.read_csv(path)
    df["state"] = df["state"].map(norm_state)
    df["stunting_pct"] = pd.to_numeric(df["stunting_pct"], errors="coerce")
    df = df.dropna(subset=["stunting_pct"])
    if df.empty:
        say("NDHS stunting file is empty -> using proxy")
        return None
    say(f"NDHS stunting: {len(df)} states")
    return df[["state", "stunting_pct"]]


# ---------------------------------------------------------------- 4. Cancer registry (optional)
def load_crc_registry():
    path = find("crc_cities.csv")
    if not path:
        return None
    df = pd.read_csv(path)
    df["state"] = df["state"].map(norm_state)
    df["crc_registry_index"] = pd.to_numeric(df.get("crc_index"), errors="coerce")
    df = df.dropna(subset=["crc_registry_index"])
    return df[["state", "crc_registry_index"]] if not df.empty else None


# ---------------------------------------------------------------- 6. Google Trends
def load_trends() -> pd.DataFrame:
    frames = []
    for path in glob.glob(os.path.join(RAW, "*.csv")):
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        first = str(df.columns[0]).strip().lower()
        if first == "time":
            say(f"SKIPPED {os.path.basename(path)}: it is 'interest over time'. "
                f"Re-export 'Interest by subregion' for this term.")
            continue
        if first != "region" or len(df.columns) != 2:
            continue
        term = str(df.columns[1]).strip()
        df.columns = ["region", "value"]
        df["state"] = df["region"].map(norm_state)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["term"] = term
        frames.append(df[["state", "term", "value"]])
        say(f"Trends '{term}': {df['value'].notna().sum()} states")
    if not frames:
        return pd.DataFrame(columns=["state", "trends_index"]), []
    allt = pd.concat(frames)
    allt["slug"] = allt["term"].map(term_slug)

    # one column per term (trends_awara, trends_soya_beans, ...) + their average
    wide = allt.pivot_table(index="state", columns="slug", values="value", aggfunc="mean")
    slugs = sorted(wide.columns)
    wide.columns = [f"trends_{c}" for c in wide.columns]
    wide["trends_index"] = wide.mean(axis=1)
    return wide.reset_index(), slugs


# ---------------------------------------------------------------- 8. products
def load_products(slugs) -> pd.DataFrame:
    """data/products.csv: id, name, uses (; separated), trends_term."""
    if not os.path.exists(PRODUCTS):
        say("data/products.csv not found -> every product uses the average demand")
        return pd.DataFrame(columns=["id", "name", "uses", "trends_term"])
    df = pd.read_csv(PRODUCTS, dtype=str).fillna("")
    for _, p in df.iterrows():
        slug = term_slug(p["trends_term"]) if p["trends_term"].strip() else ""
        if slug and slug in slugs:
            say(f"Product '{p['id']}' -> demand from Trends '{p['trends_term']}'")
        else:
            say(f"Product '{p['id']}': no Trends file for '{p['trends_term']}' -> uses the average demand")
    return df


# ---------------------------------------------------------------- 7. OpenStreetMap
def load_osm():
    path = find("**/points_of_interest.geojson")
    if not path:
        say("OSM file not found -> processed-meat proxy unavailable")
        return None, None
    with open(path, encoding="utf-8") as f:
        features = json.load(f)["features"]

    rows = []
    for ft in features:
        p = ft["properties"]
        hit = (p.get("shop") in PROCESSED_MEAT_TAGS["shop"]
               or p.get("amenity") in PROCESSED_MEAT_TAGS["amenity"])
        if hit:
            rows.append({"state": norm_state(p.get("adm1_name")),
                         "lga": norm_lga(p.get("adm2_name"))})
    df = pd.DataFrame(rows)
    by_state = df.groupby("state").size().rename("pm_outlets").reset_index()
    by_lga = df.groupby(["state", "lga"]).size().rename("pm_outlets").reset_index()
    say(f"OSM: {len(df)} food/retail outlets that suggest processed-meat buying")
    return by_state, by_lga


# ---------------------------------------------------------------- build
def build():
    print("MarketLens data pipeline")
    states, lgas = load_uscb()
    meat = load_meat_prices()
    stunting = load_stunting()
    crc_reg = load_crc_registry()
    trends, slugs = load_trends()
    load_products(slugs)
    osm_state, osm_lga = load_osm()

    s = states.merge(meat, on="state", how="left").merge(trends, on="state", how="left")

    # --- Affordability: meat price (zone) x share of poorer households (state) ---
    s["meat_burden"] = s["meat_price_ratio"] * (1 + s["poor40"] / 100)
    s["meat_cost"] = scale_0_100(s["meat_burden"])

    # --- Health, protein lens ---
    if stunting is not None:
        s = s.merge(stunting, on="state", how="left")
        s["protein_deficiency"] = scale_0_100(s["stunting_pct"])
        protein_label = "measured"
    else:
        s["protein_deficiency"] = (scale_0_100(s["u5mr"]) + scale_0_100(s["poor40"])) / 2
        protein_label = "estimated"

    # --- Health, cancer lens: processed-meat outlets per 100k people ---
    if osm_state is not None:
        s = s.merge(osm_state, on="state", how="left")
        s["pm_outlets"] = s["pm_outlets"].fillna(0)
        s["pm_density"] = s["pm_outlets"] / s["population"] * 100_000
        s["crc_index"] = rank_0_100(s["pm_density"])
    else:
        s["crc_index"] = np.nan
    if crc_reg is not None:
        s = s.merge(crc_reg, on="state", how="left")
        has = s["crc_registry_index"].notna()
        s.loc[has, "crc_index"] = (s.loc[has, "crc_index"] + s.loc[has, "crc_registry_index"]) / 2

    # --- k-means market types (unsupervised learning over all 37 states) ---
    s["demand"] = s["trends_index"]
    s, report = assign_market_types(s)
    s[["state", "zone", "population", "demand", "protein_deficiency", "crc_index",
       "meat_cost", "cluster", "market_type"]].round(1).to_csv(OUT_STATES, index=False)
    say(f"k-means: k={report['k']}, silhouette={report['silhouette']} "
        f"(tried {report['silhouette_by_k']})")
    for name, members in report["groups"].items():
        say(f"  {name}: {', '.join(members)}")

    state_lookup = s.set_index("state")

    # --- our places ---
    cfg = pd.read_csv(CONFIG, dtype=str).fillna("")
    out = []
    for _, c in cfg.iterrows():
        st = norm_state(c["state"])
        if st not in state_lookup.index:
            sys.exit(f"Unknown state '{c['state']}' for {c['id']}")
        row = state_lookup.loc[st]

        # population: chosen LGAs for rural places, whole state otherwise
        lga_list = [norm_lga(x) for x in c["lgas"].split(";") if x.strip()]
        if lga_list:
            sel = lgas[(lgas["state"] == st) & (lgas["lga"].isin(lga_list))]
            missing = set(lga_list) - set(sel["lga"])
            if missing:
                sys.exit(f"{c['id']}: LGAs not found in USCB file: {missing}")
            population = int(sel["population"].sum())
        else:
            population = int(row["population"])

        # cancer proxy for rural places: use their own LGAs, not the whole state
        crc = row["crc_index"]
        if lga_list and osm_lga is not None:
            outlets = osm_lga[(osm_lga["state"] == st) & (osm_lga["lga"].isin(lga_list))]["pm_outlets"].sum()
            density = outlets / population * 100_000
            crc = float((s["pm_density"] <= density).mean() * 100)   # same percentile scale

        # demand: Google Trends + interviews (whatever exists)
        def demand_from(trends_value):
            parts = []
            if pd.notna(trends_value):
                parts.append(float(trends_value))
            if c["demand_interviews"].strip():
                parts.append(float(c["demand_interviews"]))
            if parts:
                return round(float(np.mean(parts))), "estimated"
            return 40, "assumed"      # no signal yet

        demand, demand_label = demand_from(row.get("trends_index"))
        per_term = {}
        for slug in slugs:
            d, lab = demand_from(row.get(f"trends_{slug}"))
            per_term[f"demand_{slug}"] = d
            per_term[f"label_demand_{slug}"] = lab

        awareness = c["awareness_gap"].strip() or {
            "rural": "high", "city": "medium", "big_city": "low"}.get(c["area_type"], "medium")

        place = {
            "id": c["id"], "name": c["name"], "state": c["state"],
            "area_type": c["area_type"], "segment": c["segment"], "channel": c["channel"],
            "population": population,
            "demand": round(demand),
            "protein_deficiency": round(float(row["protein_deficiency"])),
            "crc_index": None if pd.isna(crc) else round(float(crc)),
            "meat_cost": round(float(row["meat_cost"])),
            "registered": int(c["registered"] or 0),
            "awareness_gap": awareness,
            "market_type": row["market_type"],
            "label_demand": demand_label,
            "label_health": protein_label,
            "label_meat_cost": "estimated",
            "source_ids": "S01;S02;S03;S06;S07" + (";S04" if stunting is not None else ""),
            **per_term,
        }
        place["capacity"] = (int(c["capacity_override"]) if c["capacity_override"].strip()
                             else suggest_capacity(place))
        out.append(place)

    cols = ["id", "name", "state", "area_type", "segment", "channel", "population",
            "demand", "protein_deficiency", "crc_index", "meat_cost", "capacity",
            "registered", "awareness_gap", "market_type", "label_demand", "label_health",
            "label_meat_cost", "source_ids"]
    for slug in slugs:
        cols += [f"demand_{slug}", f"label_demand_{slug}"]
    df = pd.DataFrame(out)[cols]
    df.to_csv(OUT_PLACES, index=False)
    write_sources()
    print(f"\nWrote {OUT_PLACES} ({len(df)} places)\n")
    print(df[["id", "demand"] + [f"demand_{x}" for x in slugs] +
             ["protein_deficiency", "crc_index", "meat_cost", "capacity", "registered"]].to_string(index=False))
    return df


def write_sources():
    rows = [
        ("S01", "Selected Food Price Watch (May 2026), zone averages", "National Bureau of Statistics",
         "https://microdata.nigerianstat.gov.ng/index.php/catalog/162", 2026, "zone",
         "meat_cost (beef, chicken, goat prices)"),
        ("S02", "Nigeria Subnational Population, Health and Poverty tables", "U.S. Census Bureau via HDX",
         "https://data.humdata.org/dataset/1caa305c-2d52-4361-a1bc-ce9b850859c6", 2019, "state / LGA",
         "population; under-5 mortality (MICS 2016-17); wealth quintiles (MICS 2016-17)"),
        ("S03", "Google Trends, interest by region (soya beans, awara), past 5 years", "Google",
         "https://trends.google.com", 2026, "state", "demand, per product"),
        ("S04", "Nigeria Demographic and Health Survey 2024", "NPC, FMoHSW and ICF",
         "https://www.dhsprogram.com/pubs/pdf/FR395/FR395.pdf", 2025, "state",
         "protein_deficiency (stunting)"),
        ("S05", "IARC Monographs Q&A on red and processed meat", "WHO / IARC",
         "https://www.iarc.who.int/wp-content/uploads/2018/11/Monographs-QA_Vol114.pdf", 2015, "global",
         "context: processed meat Group 1"),
        ("S06", "Points of Interest of Nigeria (OpenStreetMap export)", "HOT / OpenStreetMap contributors",
         "https://data.humdata.org/dataset/hotosm_nga_points_of_interest", 2026, "state / LGA",
         "crc_index (processed-meat outlet density proxy)"),
        ("S07", "MarketLens team interviews and assumptions", "MarketLens team",
         "", 2026, "local", "demand_interviews, awareness_gap, registered, capacity overrides"),
    ]
    pd.DataFrame(rows, columns=["id", "title", "publisher", "url", "year", "level", "used_for"]) \
        .to_csv(OUT_SOURCES, index=False)


if __name__ == "__main__":
    build()