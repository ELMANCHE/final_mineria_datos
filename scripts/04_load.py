#!/usr/bin/env python3
"""04_load.py — Carga a NeonDB (Postgres) y validacion 2.9.

Tablas: dim_pais, dim_aduana, dim_puerto, exportaciones_detalle,
        exportaciones_mensual, exportaciones_sector, val_dbf_vs_xls
"""
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "processed")
load_dotenv(os.path.join(BASE, ".env"))
URL = os.environ["DATABASE_URL"]
engine = create_engine(URL)

DDL = """
DROP TABLE IF EXISTS val_dbf_vs_xls, exportaciones_sector, exportaciones_mensual,
  exportaciones_detalle, dim_puerto, dim_aduana, dim_pais CASCADE;

CREATE TABLE dim_pais (
  pais_id SERIAL PRIMARY KEY,
  pais_codigo_iso2 VARCHAR(2),
  pais_nombre_origen VARCHAR(120),
  pais_iso3 CHAR(3),
  pais_nombre_es VARCHAR(120),
  UNIQUE (pais_nombre_origen)
);

CREATE TABLE dim_aduana (
  aduana_id SERIAL PRIMARY KEY,
  aduana_codigo VARCHAR(10) NOT NULL,
  aduana_nombre VARCHAR(120) NOT NULL,
  UNIQUE (aduana_codigo)
);

CREATE TABLE dim_puerto (
  puerto_id SERIAL PRIMARY KEY,
  puerto_locode VARCHAR(20) NOT NULL,
  puerto_nombre VARCHAR(200),
  pais_iso2 CHAR(2),
  UNIQUE (puerto_locode)
);

CREATE TABLE exportaciones_detalle (
  id BIGSERIAL PRIMARY KEY,
  partida_arancelaria CHAR(10) NOT NULL,
  descripcion_partida VARCHAR(200),
  fecha_embarque DATE,
  aduana_codigo VARCHAR(10),
  aduana_nombre VARCHAR(120),
  pais_codigo_iso2 CHAR(2),
  pais_nombre_origen VARCHAR(120),
  fob_usd NUMERIC(14,2),
  peso_neto_kg NUMERIC(14,3),
  peso_bruto_kg NUMERIC(14,3),
  cantidad_unidades NUMERIC(14,3),
  unidad_cantidad CHAR(3),
  tipo_documento VARCHAR(30),
  ruc_exportador VARCHAR(11),
  puerto_embarque_sunat VARCHAR(10),
  exportador_nombre VARCHAR(200),
  puerto_embarque_locode VARCHAR(20),
  descripcion_comercial VARCHAR(150),
  descripcion_adicional VARCHAR(200),
  fec_num DATE,
  fec_reg DATE,
  ndcl VARCHAR(10),
  ndcl_registro VARCHAR(10),
  nume_serie VARCHAR(10),
  via_transporte CHAR(2),
  via_transporte_nombre VARCHAR(60),
  agente_aduana_codigo VARCHAR(10),
  agente_aduana_nombre VARCHAR(200),
  empresa_transporte_codigo VARCHAR(20),
  empresa_transporte_nombre VARCHAR(200),
  aduana_manifiesto VARCHAR(10),
  anio_manifiesto INT,
  numero_manifiesto VARCHAR(10),
  anio_archivo INT,
  anio_numeracion INT,
  mes_numeracion INT,
  periodo_completo_detalle BOOLEAN,
  peso_cero BOOLEAN,
  fob_cero BOOLEAN,
  es_muestra BOOLEAN,
  es_exportacion_definitiva BOOLEAN,
  UNIQUE (ndcl, nume_serie, aduana_codigo, pais_codigo_iso2, fec_num)
);
CREATE INDEX idx_det_pais ON exportaciones_detalle(pais_codigo_iso2);
CREATE INDEX idx_det_fecha ON exportaciones_detalle(fec_num);
CREATE INDEX idx_det_aduana ON exportaciones_detalle(aduana_codigo);
CREATE INDEX idx_det_periodo ON exportaciones_detalle(periodo_completo_detalle);

CREATE TABLE exportaciones_mensual (
  id SERIAL PRIMARY KEY,
  partida_arancelaria CHAR(10) NOT NULL,
  aduana_codigo VARCHAR(10),
  aduana_nombre VARCHAR(120),
  pais_nombre_origen VARCHAR(120),
  mes_texto VARCHAR(30),
  mes_num INT,
  anio INT,
  valor_fob_usd NUMERIC(14,2),
  item INT,
  UNIQUE (partida_arancelaria, aduana_nombre, pais_nombre_origen, anio, mes_num)
);
CREATE INDEX idx_men_anio ON exportaciones_mensual(anio);
CREATE INDEX idx_men_pais ON exportaciones_mensual(pais_nombre_origen);

CREATE TABLE exportaciones_sector (
  partida_arancelaria CHAR(10) NOT NULL,
  anio INT NOT NULL,
  item_ranking NUMERIC,
  subpartida_descripcion VARCHAR(250),
  tipo_producto VARCHAR(40),
  sector_economico VARCHAR(60),
  fob_usd NUMERIC(20,2),
  peso_neto_kg NUMERIC(20,3),
  peso_bruto_kg NUMERIC(20,3),
  PRIMARY KEY (anio, partida_arancelaria)
);

CREATE TABLE val_dbf_vs_xls (
  anio INT PRIMARY KEY,
  dbf_registros INT,
  dbf_fob_usd NUMERIC(20,2),
  xls_filas INT,
  xls_fob_usd NUMERIC(20,2),
  g9_fob_usd NUMERIC(20,2),
  cobertura_dbf_vs_xls_pct NUMERIC(6,2),
  diferencia_xls_vs_g9_pct NUMERIC(8,3)
);
"""

with engine.begin() as conn:
    for stmt in DDL.split(";"):
        if stmt.strip():
            conn.execute(text(stmt))

jobs = [
    ("dim_pais", "dim_pais.pkl", "pais_id"),
    ("dim_aduana", "dim_aduana.pkl", "aduana_id"),
    ("dim_puerto", "dim_puerto.pkl", "puerto_id"),
    ("exportaciones_detalle", "final_detalle.pkl", "id"),
    ("exportaciones_mensual", "final_mensual.pkl", "id"),
    ("exportaciones_sector", "final_sector.pkl", None),
    ("val_dbf_vs_xls", "val_dbf_vs_xls.pkl", "anio"),
]
for table, pkl, idx_col in jobs:
    df = pd.read_pickle(os.path.join(OUT, pkl))
    df.to_sql(table, engine, if_exists="append", index=False)
    print(f"{table}: {len(df)} filas cargadas")

# verificacion 2.9: conteos en BD
with engine.connect() as conn:
    for t in ["dim_pais", "dim_aduana", "dim_puerto", "exportaciones_detalle",
              "exportaciones_mensual", "exportaciones_sector", "val_dbf_vs_xls"]:
        n = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
        print(f"BD {t}: {n}")
print("Carga completa.")
