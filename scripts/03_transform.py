#!/usr/bin/env python3
# 03_transform.py transformacion e integracion, genera tablas finales y tabla de validacion
import os

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "processed")

det = pd.read_pickle(os.path.join(OUT, "detalle_clean.pkl"))
mon = pd.read_pickle(os.path.join(OUT, "mensual_clean.pkl"))
sec = pd.read_pickle(os.path.join(OUT, "sector_clean.pkl"))

# exportaciones_mensual: XLS oficial + aduana_codigo mapeado
ALIAS_XLS = {"MARITIMA DEL CALLAO": "118", "AEREA DEL CALLAO": "235",
             "TACNA": "172", "PAITA": "046",
             "MOLLENDO - MATARANI": "154", "AREQUIPA": "154", "DESAGUADERO": "DES"}
mon["aduana_codigo"] = mon["aduana_nombre_xls"].map(ALIAS_XLS)
mon = mon.rename(columns={"pais_nombre_xls": "pais_nombre_origen",
                          "aduana_nombre_xls": "aduana_nombre",
                          "fob_usd": "valor_fob_usd"})
mon["valor_fob_usd"] = mon["valor_fob_usd"].round(2)
mon = mon[["partida_arancelaria", "aduana_codigo", "aduana_nombre",
           "pais_nombre_origen", "mes_texto", "mes_num", "anio",
           "valor_fob_usd", "item"]]
mon.to_pickle(os.path.join(OUT, "final_mensual.pkl"))

# sector: orden de columnas final
sec = sec[["partida_arancelaria", "anio", "item_ranking", "subpartida_descripcion",
           "tipo_producto", "sector_economico", "fob_usd", "peso_neto_kg",
           "peso_bruto_kg"]]
sec.to_pickle(os.path.join(OUT, "final_sector.pkl"))

# val_dbf_vs_xls: cobertura por anio
rows = []
for y in range(2016, 2026):
    d = det[det.anio_archivo == y]
    x = mon[mon.anio == y]
    g = sec[(sec.anio == y) & (sec.partida_arancelaria == "5105391000")]
    d_fob, x_fob = d.fob_usd.sum(), x.valor_fob_usd.sum()
    g_fob = g.fob_usd.sum() if len(g) else np.nan
    rows.append({
        "anio": y,
        "dbf_registros": len(d), "dbf_fob_usd": round(d_fob, 2),
        "xls_filas": len(x), "xls_fob_usd": round(x_fob, 2),
        "g9_fob_usd": round(g_fob, 2) if pd.notna(g_fob) else None,
        "cobertura_dbf_vs_xls_pct": round(d_fob / x_fob * 100, 2) if x_fob else None,
        "diferencia_xls_vs_g9_pct": round((x_fob - g_fob) / g_fob * 100, 3) if pd.notna(g_fob) and g_fob else None,
    })
val = pd.DataFrame(rows)
val.to_pickle(os.path.join(OUT, "val_dbf_vs_xls.pkl"))
print(val.to_string(index=False))

# exportaciones_mensual consolidada (agrupacion 2.6) para analisis
agg = mon.groupby(["anio", "mes_num", "pais_nombre_origen", "aduana_codigo"],
                  as_index=False)["valor_fob_usd"].sum()
agg.to_pickle(os.path.join(OUT, "mensual_agregado.pkl"))

det.to_pickle(os.path.join(OUT, "final_detalle.pkl"))
print("\nListo:", os.listdir(OUT))
