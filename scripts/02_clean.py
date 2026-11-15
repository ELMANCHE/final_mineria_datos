#!/usr/bin/env python3
# 02_clean.py limpieza y normalizacion, genera detalle/mensual/sector clean y dimensiones
import os
import re

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "processed")

# DBF
dbf = pd.read_pickle(os.path.join(OUT, "dbf_all.pkl"))

RENAME = {
    "CNAN": "partida_arancelaria", "DESCRIP": "descripcion_partida",
    "FECHA": "fecha_embarque", "CADUANA": "aduana_codigo",
    "ADUA_DESC": "aduana_nombre", "CPAIS": "pais_codigo_iso2",
    "PAIS_DESC": "pais_nombre_origen", "FOB_DOLPOL": "fob_usd",
    "PESO_NETO": "peso_neto_kg", "PESO_BRUTO": "peso_bruto_kg",
    "UNID_FIQTY": "cantidad_unidades", "UNID_FIDES": "unidad_cantidad",
    "TIPO_DOCU": "tipo_documento", "NRO_DOCU": "ruc_exportador",
    "PUER_EMBAR": "puerto_embarque_sunat", "EXPORTADOR": "exportador_nombre",
    "PUER_DESC": "puerto_embarque_locode", "DESC_COM": "descripcion_comercial",
    "DESC_ADIC": "descripcion_adicional", "FEC_NUM": "fec_num",
    "FEC_REG": "fec_reg", "NDCL": "ndcl", "NDCLREG": "ndcl_registro",
    "NUME_SERIE": "nume_serie", "VIA_TRANSP": "via_transporte",
    "VIAT_DESC": "via_transporte_nombre", "CAGE": "agente_aduana_codigo",
    "CAGE_DESC": "agente_aduana_nombre", "CEMPTRA": "empresa_transporte_codigo",
    "CEMPT_DESC": "empresa_transporte_nombre", "CADUMANIF": "aduana_manifiesto",
    "ANN_MANIF": "anio_manifiesto", "NUM_MANIF": "numero_manifiesto",
    "anio_fuente": "anio_archivo",
}
det = dbf.rename(columns=RENAME).copy()

# tipos nativos
det["partida_arancelaria"] = det["partida_arancelaria"].astype(str).str.strip()
for c in ["fob_usd", "peso_neto_kg", "peso_bruto_kg", "cantidad_unidades"]:
    det[c] = pd.to_numeric(det[c], errors="coerce")
det["fob_usd"] = det["fob_usd"].round(2)

# fechas yyyymmdd -> date (0/NaT -> NaT)
def ymd_to_date(s):
    d = pd.to_datetime(s.astype("Int64").astype("string").str.strip(),
                       format="%Y%m%d", errors="coerce")
    return d.dt.date
for c in ["fecha_embarque", "fec_num", "fec_reg"]:
    det[c] = ymd_to_date(det[c])

# strings: trim, vacio -> None estandarizado solo donde aplica
for c in det.columns:
    if det[c].dtype == object and c not in ("fecha_embarque", "fec_num", "fec_reg"):
        det[c] = det[c].astype(str).str.strip().replace({"": np.nan, "None": np.nan})

# derivadas (2.6)
det["anio_numeracion"] = det["fec_num"].apply(lambda x: x.year if pd.notna(x) else np.nan).astype("Int64")
det["mes_numeracion"] = det["fec_num"].apply(lambda x: x.month if pd.notna(x) else np.nan).astype("Int64")
det["periodo_completo_detalle"] = det["anio_archivo"].between(2016, 2019)
det["peso_cero"] = det["peso_neto_kg"] == 0
det["fob_cero"] = det["fob_usd"] == 0
det["es_muestra"] = det["tipo_documento"].isin(["-"]) | det["peso_cero"] | det["fob_cero"]
det["es_exportacion_definitiva"] = det["tipo_documento"] == "4"

# empresa transporte: trim + estandarizar
det["empresa_transporte_codigo"] = det["empresa_transporte_codigo"].str.strip()
_emp = det["empresa_transporte_codigo"]
det.loc[_emp.str.startswith(" ", na=False), "empresa_transporte_codigo"] = \
    _emp[_emp.str.startswith(" ", na=False)].str.strip()
det["empresa_transporte_codigo"] = det["empresa_transporte_codigo"].replace(
    {"": np.nan, "ZZ": "NO_ESPECIFICADO"})
det.loc[det["empresa_transporte_codigo"].isna(), "empresa_transporte_codigo"] = "NO_ESPECIFICADO"
det["tipo_documento"] = det["tipo_documento"].replace({"-": "NO_ESPECIFICADO"})
det.loc[det["puerto_embarque_locode"] == "0000", "puerto_embarque_locode"] = "NO_ESPECIFICADO"
det.loc[det["puerto_embarque_locode"].isna(), "puerto_embarque_locode"] = "NO_ESPECIFICADO"

det.to_pickle(os.path.join(OUT, "detalle_clean.pkl"))
print("detalle_clean:", det.shape)

# XLS
xls = pd.read_pickle(os.path.join(OUT, "xls_all.pkl"))
MESES = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6,
         "Julio": 7, "Agosto": 8, "Setiembre": 9, "Octubre": 10, "Noviembre": 11,
         "Diciembre": 12}
mon = xls.rename(columns={"aduana": "aduana_nombre_xls", "pais": "pais_nombre_xls",
                          "mes_txt": "mes_texto", "fob": "fob_usd"}).copy()
mon["mes_num"] = mon["mes_texto"].str.split().str[0].map(MESES).astype("Int64")
mon["partida_arancelaria"] = mon["partida"].str.strip()
mon["fob_usd"] = mon["fob_usd"].round(2)
for c in ["aduana_nombre_xls", "pais_nombre_xls", "mes_texto"]:
    mon[c] = mon[c].astype(str).str.strip()
mon = mon[["partida_arancelaria", "aduana_nombre_xls", "pais_nombre_xls",
           "mes_texto", "mes_num", "anio", "fob_usd", "item"]]
mon.to_pickle(os.path.join(OUT, "mensual_clean.pkl"))
print("mensual_clean:", mon.shape)

# G9
g9 = pd.read_pickle(os.path.join(OUT, "g9_all.pkl"))
sec = g9.rename(columns={"subpartida_raw": "subpartida_raw_float",
                         "subpartida_desc": "subpartida_descripcion",
                         "tipo": "tipo_producto", "sector": "sector_economico",
                         "fob": "fob_usd", "peso_neto": "peso_neto_kg",
                         "peso_bruto": "peso_bruto_kg", "anio": "anio",
                         "item": "item_ranking"}).copy()
sec["partida_arancelaria"] = (sec["subpartida_raw_float"].astype("Int64")
                              .astype(str).str.zfill(10))
sec["fob_usd"] = sec["fob_usd"].round(2)
sec = sec.drop(columns=["subpartida_raw_float"])
sec.to_pickle(os.path.join(OUT, "sector_clean.pkl"))
print("sector_clean:", sec.shape)

# DIM PAIS
# union de paises: DBF (iso2+desc) y XLS (nombre)
NOMBRE_ES = {
    "AUSTRALIA": ("AUS", "Australia"), "AUSTRIA": ("AUT", "Austria"),
    "BELGIUM": ("BEL", "Bélgica"), "BOLIVIA": ("BOL", "Bolivia"),
    "BOLIVIA, PLURINATIONAL STATE OF": ("BOL", "Bolivia"),
    "BULGARIA": ("BGR", "Bulgaria"), "CANADA": ("CAN", "Canadá"),
    "CHILE": ("CHL", "Chile"), "CHINA": ("CHN", "China"),
    "COLOMBIA": ("COL", "Colombia"), "DENMARK": ("DNK", "Dinamarca"),
    "ECUADOR": ("ECU", "Ecuador"), "EGYPT": ("EGY", "Egipto"),
    "FINLAND": ("FIN", "Finlandia"), "FRANCE": ("FRA", "Francia"),
    "GERMANY": ("DEU", "Alemania"), "HONG KONG": ("HKG", "Hong Kong"),
    "INDIA": ("IND", "India"), "INDONESIA": ("IDN", "Indonesia"),
    "ISRAEL": ("ISR", "Israel"), "ITALY": ("ITA", "Italia"),
    "JAPAN": ("JPN", "Japón"), "KOREA, REPUBLIC OF": ("KOR", "Corea del Sur"),
    "LITHUANIA": ("LTU", "Lituania"), "MEXICO": ("MEX", "México"),
    "NEPAL": ("NPL", "Nepal"), "NETHERLANDS": ("NLD", "Países Bajos"),
    "NEW ZEALAND": ("NZL", "Nueva Zelanda"), "NORWAY": ("NOR", "Noruega"),
    "ROMANIA": ("ROU", "Rumania"), "SOUTH AFRICA": ("ZAF", "Sudáfrica"),
    "SPAIN": ("ESP", "España"), "SWITZERLAND": ("CHE", "Suiza"),
    "TAIWAN, PROVINCE OF CHINA": ("TWN", "Taiwán"), "TURKEY": ("TUR", "Turquía"),
    "UNITED KINGDOM": ("GBR", "Reino Unido"), "UNITED STATES": ("USA", "Estados Unidos"),
    "URUGUAY": ("URY", "Uruguay"),
}
filas = []
for _, r in det[["pais_codigo_iso2", "pais_nombre_origen"]].drop_duplicates().iterrows():
    nombre = str(r.pais_nombre_origen).strip()
    iso3, esp = NOMBRE_ES.get(nombre, (None, nombre.title()))
    filas.append({"pais_codigo_iso2": r.pais_codigo_iso2, "pais_nombre_origen": nombre,
                  "pais_iso3": iso3, "pais_nombre_es": esp})
for nombre in sorted(set(mon["pais_nombre_xls"]) - {f["pais_nombre_origen"] for f in filas}):
    iso3, esp = NOMBRE_ES.get(nombre, (None, nombre.title()))
    filas.append({"pais_codigo_iso2": None, "pais_nombre_origen": nombre,
                  "pais_iso3": iso3, "pais_nombre_es": esp})
dimp = pd.DataFrame(filas).drop_duplicates()
dimp.to_pickle(os.path.join(OUT, "dim_pais.pkl"))
print("dim_pais:", dimp.shape)

# DIM ADUANA
# unifica codigos DBF con nombres XLS
ALIAS_XLS = {"MARITIMA DEL CALLAO": "118", "AEREA DEL CALLAO": "235",
             "TACNA": "172", "PAITA": "046",
             "MOLLENDO - MATARANI": "154", "AREQUIPA": "154", "DESAGUADERO": "DES"}
adu_rows = det[["aduana_codigo", "aduana_nombre"]].drop_duplicates()
adu = [{"aduana_codigo": r.aduana_codigo, "aduana_nombre": r.aduana_nombre}
       for _, r in adu_rows.iterrows()]
for nombre_xls, cod in ALIAS_XLS.items():
    if not any(a["aduana_codigo"] == cod for a in adu):
        adu.append({"aduana_codigo": cod, "aduana_nombre": nombre_xls})
dima = pd.DataFrame(adu)
dima.to_pickle(os.path.join(OUT, "dim_aduana.pkl"))
print("dim_aduana:", dima.to_dict("records"))

# DIM PUERTO
loc = pd.read_csv(os.path.join(OUT, "locode.csv"), dtype=str).fillna("")
loc["locode"] = loc["Country"] + loc["Location"]
loc = loc.drop_duplicates(subset=["locode"], keep="first")
loc_map = loc.set_index("locode")[["NameWoDiacritics", "Country"]].to_dict("index")
used = sorted(set(det["puerto_embarque_locode"]) - {"NO_ESPECIFICADO"})
prows = [{"puerto_locode": "NO_ESPECIFICADO", "puerto_nombre": "Puerto no declarado",
          "pais_iso2": None}]
for code in used:
    if code in loc_map:
        prows.append({"puerto_locode": code, "puerto_nombre": loc_map[code]["NameWoDiacritics"],
                      "pais_iso2": loc_map[code]["Country"]})
    else:
        prows.append({"puerto_locode": code, "puerto_nombre": f"No encontrado en UN/LOCODE",
                      "pais_iso2": code[:2]})
dimp2 = pd.DataFrame(prows)
dimp2.to_pickle(os.path.join(OUT, "dim_puerto.pkl"))
faltan = dimp2[dimp2.puerto_nombre == "No encontrado en UN/LOCODE"]
print("dim_puerto:", dimp2.shape, "| no encontrados:", faltan.puerto_locode.tolist())
