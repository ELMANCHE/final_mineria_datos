#!/usr/bin/env python3
"""01_profile.py — Perfilamiento de las 3 fuentes (secciones 2.3 y 2.4).

Fuentes:
  - Data Original/Variables Especificas/*.DBF  -> detalle por declaracion
  - Data Original/Report de Partida Exportador/*.xls -> agregados mensuales SUNAT
  - Data Original/cdro_G9.xlsx                  -> cuadro nacional por sector (2005-2025)

Salidas en processed/:
  - dbf_all.pkl, xls_all.pkl, g9_all.pkl  (datos crudos leidos, sin tocar)
  - profile_summary.csv                   (metricas por fuente/anio)
  - profile_report.md                     (reporte legible para el Cap. II)
"""
import glob
import os
import re
import struct
from collections import Counter

import numpy as np
import pandas as pd
from dbfread import DBF

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "Data Original")
OUT = os.path.join(BASE, "processed")
os.makedirs(OUT, exist_ok=True)

report = []
def sec(t): report.append(f"\n## {t}\n")
def p(*a): report.append(" ".join(str(x) for x in a))

# ---------------------------------------------------------------- DBF
def read_dbf(path):
    table = DBF(path, encoding="latin1", char_decode_errors="replace")
    df = pd.DataFrame(iter(table))
    year = int(re.search(r"(\d{4})", os.path.basename(path)).group(1))
    df["anio_fuente"] = year
    return df

sec("DBF — Variables Especificas (detalle por declaracion)")
dbf_files = sorted(glob.glob(os.path.join(DATA, "Variables Especificas", "*.DBF")))
dbf_parts = []
for f in dbf_files:
    d = read_dbf(f)
    dbf_parts.append(d)
    p(f"- {os.path.basename(f)}: {len(d)} regs, {d.shape[1]-1} campos")
dbf = pd.concat(dbf_parts, ignore_index=True)
dbf.to_pickle(os.path.join(OUT, "dbf_all.pkl"))
p(f"\nTOTAL DBF: {len(dbf)} registros, {dbf.shape[1]} columnas (incl. anio_fuente)")
p("Columnas:", ", ".join(dbf.columns))

# tipos y nulos
p("\n### Nulos por columna (DBF)")
nulls = dbf.isna().sum()
nulls = nulls[nulls > 0].sort_values(ascending=False)
if len(nulls):
    for c, n in nulls.items():
        p(f"- `{c}`: {n} ({n/len(dbf)*100:.1f}%)")
else:
    p("Sin nulos.")

# duplicados
p("\n### Duplicados (DBF)")
p(f"- Filas completamente identicas: {dbf.duplicated().sum()}")
for key in ["NRO_DOCU", "NDCL", "NRO_DOCU+CADUANA+FECHA", "NDCL+CADUANA"]:
    cols = key.split("+")
    p(f"- Duplicados por {key}: {dbf.duplicated(subset=cols).sum()}")

# valores unicos clave
for c in ["CNAN", "CADUANA", "ADUA_DESC", "CPAIS", "UNID_FIQTY", "TIPO_DOCU",
          "VIA_TRANSP", "CAGE", "CEMPTRA"]:
    vals = dbf[c].astype(str).str.strip().replace("", "(vacio)")
    vc = vals.value_counts()
    p(f"\n`{c}` — {vals.nunique()} unicos. Top:")
    for v, n in vc.head(15).items():
        p(f"  {v!r}: {n}")

# correspondencia codigo->descripcion
for pair in [("CADUANA", "ADUA_DESC"), ("CPAIS", "PAIS_DESC"), ("PUER_DESC", None),
             ("CAGE", "CAGE_DESC"), ("CEMPTRA", "CEMPT_DESC")]:
    c1, c2 = pair
    m = dbf[[c1, c2]].drop_duplicates().dropna() if c2 else dbf[[c1]].drop_duplicates()
    p(f"\nMapeo {c1}" + (f" -> {c2}" if c2 else "") + f" ({len(m)} combinaciones):")
    for _, r in m.head(40).iterrows():
        p("  ", dict(r))

# fechas: nulidad, rango, diferencias
p("\n### Fechas (DBF)")
for c in ["FECHA", "FEC_NUM", "FEC_REG"]:
    s = pd.to_numeric(dbf[c], errors="coerce")
    valid = s.dropna()
    p(f"- `{c}`: nulos={dbf[c].isna().sum() + (s.isna().sum()-dbf[c].isna().sum())}, "
      f"rango={int(valid.min()) if len(valid) else '-'} a {int(valid.max()) if len(valid) else '-'}")
# consistencia entre fechas donde ambas existen
a = pd.to_datetime(dbf["FEC_NUM"].astype("Int64").astype(str), format="%Y%m%d", errors="coerce")
b = pd.to_datetime(dbf["FEC_REG"].astype("Int64").astype(str), format="%Y%m%d", errors="coerce")
c2 = pd.to_datetime(dbf["FECHA"].astype("Int64").astype(str), format="%Y%m%d", errors="coerce")
p(f"- FEC_NUM vs FEC_REG difieren en {(a != b).sum()} regs; FECHA vs FEC_NUM difieren en {(c2 != a).sum()} regs")

# montos y pesos
for c in ["FOB_DOLPOL", "PESO_NETO", "PESO_BRUTO", "UNID_FIQTY"]:
    s = pd.to_numeric(dbf[c], errors="coerce")
    p(f"- `{c}`: nulos={s.isna().sum()}, ceros={(s == 0).sum()}, "
      f"min={s.min()}, max={s.max()}, suma={s.sum():,.2f}")

# totales por anio (DBF)
p("\n### DBF: registros y FOB por anio")
dbf["fob"] = pd.to_numeric(dbf["FOB_DOLPOL"], errors="coerce").fillna(0)
dbf["peso"] = pd.to_numeric(dbf["PESO_NETO"], errors="coerce")
t = dbf.groupby("anio_fuente").agg(regs=("fob", "size"), fob_usd=("fob", "sum"),
                                   peso_kg=("peso", "sum")).reset_index()
for _, r in t.iterrows():
    p(f"- {int(r.anio_fuente)}: {int(r.regs)} regs | FOB {r.fob_usd:,.2f} US$ | {r.peso_kg:,.0f} kg")

# DBF por aduana x anio (para explicar caida)
p("\n### DBF: registros por aduana x anio")
adu = dbf.groupby(["anio_fuente", "CADUANA", "ADUA_DESC"]).agg(
    regs=("fob", "size"), fob=("fob", "sum")).reset_index()
adu["ADUA_DESC"] = adu["ADUA_DESC"].str.strip()
for anio, g in adu.groupby("anio_fuente"):
    p(f"- {int(anio)}:")
    for _, r in g.iterrows():
        p(f"    {r.CADUANA} {str(r.ADUA_DESC)[:38]:38s} regs={int(r.regs):4d} FOB={r.fob:>15,.2f}")

# ---------------------------------------------------------------- XLS
def read_xls_report(path):
    """Parsea el formato reporte SUNAT: datos desde fila ~11, columnas ITEM..FOB."""
    df = pd.read_excel(path, header=None)
    # localizar encabezado de columnas (fila con 'ITEM' y 'FOB')
    hdr_i = None
    for i in range(len(df)):
        row = [str(x) for x in df.iloc[i].tolist()]
        if any("ITEM" in x for x in row) and any("FOB" in x for x in row):
            hdr_i = i
            break
    if hdr_i is None:
        return pd.DataFrame(), {}
    meta = {}
    for i in range(hdr_i):
        row = df.iloc[i].tolist()
        for j, v in enumerate(row):
            if pd.notna(v):
                meta.setdefault(str(v).strip()[:40], str(row[j + 1]).strip() if j + 1 < len(row) and pd.notna(row[j + 1]) else "")
    data = df.iloc[hdr_i + 1:].copy()
    # columnas: 1=ITEM,3=PARTIDA,5=ADUANA,9=PAIS,10=MES,13=FOB
    out = pd.DataFrame({
        "item": pd.to_numeric(data[1], errors="coerce"),
        "partida": data[3].astype(str).str.strip(),
        "aduana": data[5].astype(str).str.strip(),
        "pais": data[9].astype(str).str.strip(),
        "mes_txt": data[10].astype(str).str.strip(),
        "fob_txt": data[13].astype(str).str.strip(),
    })
    out["fob"] = pd.to_numeric(out["fob_txt"].str.replace(",", "", regex=False), errors="coerce")
    out = out.dropna(subset=["item"])
    year = int(re.search(r"(\d{4})", os.path.basename(path)).group(1))
    out["anio"] = year
    # pie 'Total de registros : N'
    last = df.iloc[-1].astype(str).str.cat(sep=" ")
    m = re.search(r"Total de registros\s*:\s*(\d+)", last)
    meta["total_declarado"] = int(m.group(1)) if m else None
    return out, meta

sec("\nXLS — Reporte Partida Exportador (agregados mensuales)")
xls_files = sorted(glob.glob(os.path.join(DATA, "Report de Partida Exportador", "*.xls")))
xls_parts, xls_meta = [], {}
for f in xls_files:
    d, meta = read_xls_report(f)
    xls_parts.append(d)
    y = int(re.search(r"(\d{4})", os.path.basename(f)).group(1))
    xls_meta[y] = meta
    p(f"- {os.path.basename(f)}: {len(d)} filas | total declarado={meta.get('total_declarado')} | "
      f"suma FOB calculada={d['fob'].sum():,.2f} | partidas={d['partida'].unique().tolist()}")
xls = pd.concat(xls_parts, ignore_index=True)
xls.to_pickle(os.path.join(OUT, "xls_all.pkl"))
p(f"\nTOTAL XLS: {len(xls)} filas")
p("Meses distintos:", sorted(xls["mes_txt"].unique()))
p("Aduanas:", xls["aduana"].value_counts().to_dict())
p("Paises:", xls["pais"].nunique(), "->", sorted(xls["pais"].unique()))
p("\n### XLS: FOB por anio")
for anio, g in xls.groupby("anio"):
    p(f"- {anio}: {len(g)} filas | FOB {g['fob'].sum():,.2f} US$")

# ---------------------------------------------------------------- G9
sec("\nG9 — Cuadro nacional por sector (2005-2025)")
g9 = pd.read_excel(os.path.join(DATA, "cdro_G9.xlsx"), sheet_name=None, header=None)
g9_parts = []
for sheet, d in g9.items():
    year = int(sheet)
    # datos reales: desde la fila con 'Total general' en col 2; cols: 2=item,3=subpartida,4=desc,5=tipo,6=sector,7=fob,8=pesoN,9=pesoB
    mask = d[2].astype(str).str.strip() == "Total general"
    start = mask.idxmax() if mask.any() else 7
    # la fila 'Total general' es un total; los datos empiezan despues del bloque de encabezados
    # buscar primera fila con item numerico despues de start+2
    sub = d.iloc[start + 3:].copy()
    rec = pd.DataFrame({
        "item": pd.to_numeric(sub[2], errors="coerce"),
        "subpartida_raw": sub[3],
        "subpartida_desc": sub[4].astype(str).str.strip(),
        "tipo": sub[5].astype(str).str.strip(),
        "sector": sub[6].astype(str).str.strip(),
        "fob": pd.to_numeric(sub[7], errors="coerce"),
        "peso_neto": pd.to_numeric(sub[8], errors="coerce"),
        "peso_bruto": pd.to_numeric(sub[9], errors="coerce"),
    }).dropna(subset=["item"])
    rec["anio"] = year
    g9_parts.append(rec)
g9df = pd.concat(g9_parts, ignore_index=True)
g9df.to_pickle(os.path.join(OUT, "g9_all.pkl"))
p(f"TOTAL G9: {len(g9df)} filas, {g9df['anio'].nunique()} anios ({g9df['anio'].min()}-{g9df['anio'].max()})")
p("dtype subpartida_raw:", g9df["subpartida_raw"].dtype, "| ejemplo:", g9df["subpartida_raw"].dropna().unique()[:5])
# partida objetivo
part = g9df[g9df["subpartida_raw"].astype(float).round().astype("Int64").astype(str).str.zfill(10) == "5105391000"]
p(f"\nFilas G9 partida 5105391000: {len(part)}")
for _, r in part.iterrows():
    p(f"- {int(r.anio)}: FOB={r.fob:,.2f} | PN={r.peso_neto:,.3f} t | PB={r.peso_bruto:,.3f} t | {r.sector} / {r.tipo}")
# tipos y sectores
p("\nTipos:", g9df["tipo"].value_counts().to_dict())
p("Sectores top:", g9df["sector"].value_counts().head(15).to_dict())

# ---------------------------------------------------------------- CRUCE
sec("\nCRUCE DE TOTALES FOB POR ANIO (US$)")
cmp_rows = []
for y in range(2016, 2026):
    d_fob = dbf.loc[dbf.anio_fuente == y, "fob"].sum()
    d_n = (dbf.anio_fuente == y).sum()
    x_fob = xls.loc[xls.anio == y, "fob"].sum()
    x_n = (xls.anio == y).sum()
    g = part[part.anio == y]
    g_fob = g["fob"].sum() if len(g) else np.nan
    cmp_rows.append((y, d_n, d_fob, x_n, x_fob, g_fob))
    p(f"- {y}: DBF n={d_n:4d} FOB={d_fob:>15,.2f} | XLS n={x_n:3d} FOB={x_fob:>15,.2f} | G9 FOB={g_fob:>15,.2f} | ratio DBF/G9={d_fob/g_fob if g_fob else float('nan'):.3f}")
pd.DataFrame(cmp_rows, columns=["anio", "dbf_regs", "dbf_fob", "xls_rows", "xls_fob", "g9_fob"]).to_csv(
    os.path.join(OUT, "totales_por_anio.csv"), index=False)

# ---------------------------------------------------------------- 2025 cutoff
sec("\nCORTE TEMPORAL 2025")
m2025 = xls[xls.anio == 2025]["mes_txt"].unique()
p("XLS 2025 meses:", sorted(m2025))
d2025 = dbf[dbf.anio_fuente == 2025]
if len(d2025):
    mx = pd.to_datetime(d2025["FEC_NUM"].astype("Int64").astype(str), format="%Y%m%d", errors="coerce").max()
    p("DBF 2025 max FEC_NUM:", mx.date() if pd.notna(mx) else "s/d")
g2025 = g9df[g9df.anio == 2025]
p("G9 hoja 2025 existe:", len(g2025) > 0, "| filas:", len(g2025))

with open(os.path.join(OUT, "profile_report.md"), "w") as fh:
    fh.write("# Perfilamiento de datos — Capitulo II (2.3 y 2.4)\n")
    fh.write("\n".join(report))

print("\n".join(report[-60:]))
print("\n>> Listo. Salidas en processed/:", os.listdir(OUT))
