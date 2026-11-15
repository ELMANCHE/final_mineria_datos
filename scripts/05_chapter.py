#!/usr/bin/env python3
# 05_chapter.py genera el documento del Capitulo II en Markdown con datos reales
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "processed")
DOC = os.path.join(BASE, "Capitulo_II_Obtencion_Preparacion_Modelado.md")
load_dotenv(os.path.join(BASE, ".env"))
engine = create_engine(os.environ["DATABASE_URL"])

det = pd.read_pickle(os.path.join(OUT, "final_detalle.pkl"))
mon = pd.read_pickle(os.path.join(OUT, "final_mensual.pkl"))
sec = pd.read_pickle(os.path.join(OUT, "final_sector.pkl"))
val = pd.read_pickle(os.path.join(OUT, "val_dbf_vs_xls.pkl"))
dimp = pd.read_pickle(os.path.join(OUT, "dim_pais.pkl"))
prof = open(os.path.join(OUT, "profile_report.md")).read()

L = []
def w(s=""): L.append(s)
def table(df, floatfmt="{:,.2f}"):
    cols = list(df.columns)
    w("| " + " | ".join(cols) + " |")
    w("|" + "---|" * len(cols))
    for _, r in df.iterrows():
        w("| " + " | ".join(str(v) for v in r.tolist()) + " |")

w("# CAPÍTULO II. OBTENCIÓN, PREPARACIÓN Y MODELADO DE DATOS\n")
w("Proyecto: Exportaciones peruanas de pelo fino cardado/peinado (subpartida nacional 5105391000)\n")
w("Fuentes: declaraciones aduaneras SUNAT (DBF), Reporte de Partida Exportador (XLS) y Cuadro G9 INEI/SUNAT.\n")

# 2.3
w("\n## 2.3. Diccionario de datos\n")
w("### 2.3.1 Tabla `exportaciones_detalle` (fuente: DBF Variables Específicas, 2016–2025)\n")
w("Grano: un registro por ítem de declaración aduanera (DAM/DUA) de la partida 5105391000.\n")
w("| Campo | Descripción | Tipo origen | Tipo Postgres | Unidad | Formato | Valores posibles / tratamiento |")
w("|---|---|---|---|---|---|---|")
det_dict = [
 ("id","Identificador surrogate","-","BIGSERIAL","-","entero","Generado en carga"),
 ("partida_arancelaria","Subpartida nacional","CNAN C(10)","CHAR(10)","-","10 dígitos","5105391000 en el 100% de los registros"),
 ("descripcion_partida","Descripción de la partida","DESCRIP C(85)","VARCHAR(200)","-","texto","'- - - De alpaca o de llama'"),
 ("fecha_embarque","Fecha de embarque","FECHA N(8)","DATE","-","yyyymmdd→DD/MM/YYYY","2016–2025"),
 ("aduana_codigo","Código de aduana","CADUANA C(3)","VARCHAR(10)","-","3 dígitos","118,235,046,172,154"),
 ("aduana_nombre","Nombre de aduana","ADUA_DESC C(55)","VARCHAR(120)","-","texto","5 valores únicos"),
 ("pais_codigo_iso2","Código ISO-2 del país destino","CPAIS C(2)","CHAR(2)","-","ISO 3166-1 alpha-2","34 países"),
 ("pais_nombre_origen","Nombre país (inglés) origen","PAIS_DESC C(55)","VARCHAR(120)","-","texto","Se normaliza vía dim_pais"),
 ("fob_usd","Valor FOB en dólares","FOB_DOLPOL N(11)","NUMERIC(14,2)","US$","entero→2 decimales","Min 1, máx 663,046"),
 ("peso_neto_kg","Peso neto","PESO_NETO N(14)","NUMERIC(14,3)","kg","entero","4 ceros detectados (bandera peso_cero)"),
 ("peso_bruto_kg","Peso bruto","PESO_BRUTO N(14)","NUMERIC(14,3)","kg","entero","3 ceros"),
 ("cantidad_unidades","Cantidad","UNID_FIQTY N(14)","NUMERIC(14,3)"," según UNID_FIDES","entero","Coincide con peso_neto_kg en este dataset"),
 ("unidad_cantidad","Unidad de cantidad","UNID_FIDES C(3)","CHAR(3)","-","código","'KG' en la totalidad"),
 ("tipo_documento","Tipo de documento","TIPO_DOCU C(1)","VARCHAR(30)","-","código","'4'=exportación definitiva; '-'→NO_ESPECIFICADO (3 regs)"),
 ("ruc_exportador","RUC del exportador","NRO_DOCU C(11)","VARCHAR(11)","-","11 dígitos","23 exportadores únicos"),
 ("puerto_embarque_sunat","Código puerto SUNAT","PUER_EMBAR C(5)","VARCHAR(10)","-","código","Mayormente vacío"),
 ("exportador_nombre","Razón social exportador","EXPORTADOR C(150)","VARCHAR(200)","-","texto","-"),
 ("puerto_embarque_locode","Código UN/LOCODE puerto","PUER_DESC C(32)","VARCHAR(20)","-","5 caracteres","101 códigos; '0000'→NO_ESPECIFICADO"),
 ("descripcion_comercial","Descripción comercial","DESC_COM C(100)","VARCHAR(150)","-","texto","-"),
 ("descripcion_adicional","Descripción adicional","DESC_ADIC C(150)","VARCHAR(200)","-","texto","-"),
 ("fec_num","Fecha de numeración DAM","FEC_NUM N(8)","DATE","-","yyyymmdd→DD/MM/YYYY","Fecha principal de análisis"),
 ("fec_reg","Fecha de registro","FEC_REG N(8)","DATE","-","yyyymmdd→DD/MM/YYYY","Metadato"),
 ("ndcl","Número de declaración","NDCL C(6)","VARCHAR(10)","-","6 dígitos","Parte de la llave única"),
 ("ndcl_registro","NDCL de registro","NDCLREG C(6)","VARCHAR(10)","-","6 dígitos","Metadato"),
 ("nume_serie","Ítem dentro de la declaración","NUME_SERIE C(4)","VARCHAR(10)","-","numérico","Parte de la llave única"),
 ("via_transporte","Vía de transporte","VIA_TRANSP C(1)","CHAR(2)","-","código","1,4,7"),
 ("via_transporte_nombre","Nombre vía","VIAT_DESC C(40)","VARCHAR(60)","-","texto","Marítima/Aérea/etc."),
 ("agente_aduana_codigo","Código agente de aduana","CAGE C(4)","VARCHAR(10)","-","4 dígitos","29 agentes"),
 ("agente_aduana_nombre","Nombre agente","CAGE_DESC C(60)","VARCHAR(200)","-","texto","-"),
 ("empresa_transporte_codigo","Empresa de transporte","CEMPTRA C(4)","VARCHAR(20)","-","código","Trim; ''/'ZZ'→NO_ESPECIFICADO"),
 ("empresa_transporte_nombre","Nombre transporte","CEMPT_DESC C(60)","VARCHAR(200)","-","texto","-"),
 ("aduana_manifiesto","Aduana del manifiesto","CADUMANIF C(3)","VARCHAR(10)","-","3 dígitos","-"),
 ("anio_manifiesto","Año del manifiesto","ANN_MANIF C(4)","INT","-","aaaa","-"),
 ("numero_manifiesto","Número de manifiesto","NUM_MANIF C(5)","VARCHAR(10)","-","5 dígitos","-"),
 ("anio_archivo","Año del archivo fuente","-","INT","-","aaaa","2016–2025; trazabilidad"),
 ("anio_numeracion","Año de fec_num","-","INT","-","aaaa","Derivada de fec_num"),
 ("mes_numeracion","Mes de fec_num","-","INT","-","1–12","Derivada de fec_num"),
 ("periodo_completo_detalle","Cobertura completa del detalle","-","BOOLEAN","-","TRUE/FALSE","TRUE=2016–2019, FALSE=2020–2025"),
 ("peso_cero","Peso neto = 0","-","BOOLEAN","-","TRUE/FALSE","4 registros"),
 ("fob_cero","FOB = 0","-","BOOLEAN","-","TRUE/FALSE","0 registros"),
 ("es_muestra","Posible muestra/anulación","-","BOOLEAN","-","TRUE/FALSE","tipo_documento='-' o peso_cero"),
 ("es_exportacion_definitiva","Régimen definitivo","-","BOOLEAN","-","TRUE/FALSE","tipo_documento='4' (99.9%)"),
]
for r in det_dict: w("| " + " | ".join(r) + " |")

w("\n### 2.3.2 Tabla `exportaciones_mensual` (fuente: Reporte Partida Exportador XLS)\n")
w("Grano: partida × aduana × país × mes × año. Fuente oficial completa 2016–2025.\n")
w("| Campo | Descripción | Tipo Postgres | Unidad | Formato | Tratamiento |")
w("|---|---|---|---|---|---|")
for r in [
 ("partida_arancelaria","Subpartida","CHAR(10)","-","10 dígitos","5105391000"),
 ("aduana_codigo","Código aduana","VARCHAR(10)","-","código","Mapeado desde nombre XLS"),
 ("aduana_nombre","Aduana","VARCHAR(120)","-","texto","Nombres XLS normalizados"),
 ("pais_nombre_origen","País destino","VARCHAR(120)","-","inglés mayúsculas","Join a dim_pais"),
 ("mes_texto","Mes original","VARCHAR(30)","-","'Febrero 2016'","Se conserva"),
 ("mes_num","Mes numérico","INT","-","1–12","Derivado de mes_texto"),
 ("anio","Año","INT","-","2016–2025","Del nombre de archivo"),
 ("valor_fob_usd","Valor FOB","NUMERIC(14,2)","US$","2 decimales","Comas de miles eliminadas"),
 ("item","Correlativo","INT","-","entero","Orden del reporte"),
]: w("| " + " | ".join(r) + " |")

w("\n### 2.3.3 Tabla `exportaciones_sector` (fuente: Cuadro G9 INEI/SUNAT)\n")
w("Grano: subpartida nacional × año (21 años: 2005–2025).\n")
w("| Campo | Descripción | Tipo Postgres | Unidad | Tratamiento |")
w("|---|---|---|---|---|")
for r in [
 ("partida_arancelaria","Subpartida","CHAR(10)","-","float→int→texto 10 dígitos (zfill)"),
 ("anio","Año","INT","-","Nombre de hoja"),
 ("item_ranking","Posición por FOB","NUMERIC","-","-"),
 ("subpartida_descripcion","Descripción partida","VARCHAR(250)","-","-"),
 ("tipo_producto","Tradicional/No tradicional","VARCHAR(40)","-","-"),
 ("sector_economico","Sector","VARCHAR(60)","-","-"),
 ("fob_usd","Valor FOB","NUMERIC(20,2)","US$","Cabecera decía 'miles de US$' pero valores son US$ completos (verificado vs total nacional)"),
 ("peso_neto_kg","Peso neto","NUMERIC(20,3)","kg","Cabecera decía 'toneladas' pero valores cuadran en kg con el detalle DBF"),
 ("peso_bruto_kg","Peso bruto","NUMERIC(20,3)","kg","Igual que peso_neto_kg"),
]: w("| " + " | ".join(r) + " |")

w("\n### 2.3.4 Tablas de dimensiones\n")
w("- `dim_pais` (38 filas): pais_codigo_iso2, pais_nombre_origen, pais_iso3, pais_nombre_es — une los 34 países del DBF y los 37 del XLS.")
w("- `dim_aduana` (6 filas): aduana_codigo + aduana_nombre — 5 aduanas del DBF + DESAGUADERO presente solo en XLS.")
w("- `dim_puerto` (101 filas): puerto_locode UN/LOCODE + nombre real del puerto + pais_iso2; 'NO_ESPECIFICADO' para códigos '0000'/vacíos.")

# 2.4
w("\n## 2.4. Perfilamiento\n")
w("### 2.4.1 Volumen por fuente\n")
tot = pd.DataFrame([
 ("DBF detalle","10 archivos","4,021","33 campos","0","0"),
 ("XLS mensual","10 archivos","1,115","9 campos","0","0 (total declarado = filas)"),
 ("G9 sector","1 archivo (21 hojas)","97,657","9 campos","0","0"),
], columns=["Fuente","Archivos","Registros","Campos","Duplicados","Observación"])
table(tot)
w("\n### 2.4.2 Valores nulos (DBF)\nSin valores nulos en ninguna de las 33 columnas originales.\n")
w("### 2.4.3 Duplicados\n")
w("- Filas completamente idénticas: **0**.")
w("- `NRO_DOCU` (RUC exportador) se repite: solo 23 valores únicos → no es llave; es atributo del exportador.")
w("- Llave natural validada `ndcl+nume_serie+aduana_codigo+pais_codigo_iso2+fec_num`: **0 duplicados, 4,021 únicos** → grano = ítem de declaración.")
w("\n### 2.4.4 Formatos inconsistentes detectados\n")
for r in [
 "CNAN en DBF viene completo ('5105391000'); en G9 la subpartida es float64 (5.105391e+09) → normalizada a texto de 10 dígitos.",
 "Fechas DBF como entero yyyymmdd → DATE. FEC_REG contiene valores 0 → NaT.",
 "CEMPTRA con espacios ('  LA'), 'ZZ' y vacíos → NO_ESPECIFICADO.",
 "PUER_DESC='0000' y vacíos → NO_ESPECIFICADO en dim_puerto.",
 "G9: encabezados en 2 filas, columna de subpartida flotante, 'Total general' como fila resumen.",
 "XLS: encabezado SUNAT de ~11 filas antes de los datos; FOB con comas de miles; mes como texto ('Febrero 2016').",
 "Países: DBF usa ISO-2+nombre inglés; XLS usa nombre inglés en mayúsculas; G9 no tiene país.",
 "Aduanas: DBF código 3 dígitos+nombre; XLS solo nombre ('MOLLENDO - MATARANI' ≠ 'MOLLENDO - AGENCIA ADUANERA DE AREQUIPA').",
]: w(f"- {r}")
w("\n### 2.4.5 Valores atípicos\n")
for r in [
 "FOB_DOLPOL: mín 1 US$, máx 663,046 US$; 0 registros en cero.",
 "PESO_NETO/PESO_BRUTO: 4 y 3 ceros respectivamente → bandera peso_cero.",
 "UNID_FIQTY coincide exactamente con PESO_NETO (unidad KG) en todo el dataset.",
 "TIPO_DOCU='-' en 3 registros → NO_ESPECIFICADO + es_muestra.",
 "PUER_EMBAR (código SUNAT) vacío en la práctica; el dato real está en PUER_DESC (UN/LOCODE).",
 "Registros con fec_num en dic-2015 dentro del archivo 2016 (cruce de año).",
]: w(f"- {r}")

# 2.5
w("\n## 2.5. Limpieza\n")
w("| Regla | Campo(s) | Antes | Después |")
w("|---|---|---|---|")
for r in [
 ("Nombres de campo","todos","CNAN, FOB_DOLPOL, NRO_DOCU...","snake_case: partida_arancelaria, fob_usd, ruc_exportador..."),
 ("Fechas","FECHA/FEC_NUM/FEC_REG","yyyymmdd entero","DATE; formato DD/MM/YYYY en reportes"),
 ("Moneda","FOB_DOLPOL / FOB XLS / FOB G9","US$ (G9 mal rotulado 'miles')","NUMERIC(14,2) US$ exactos, sin multiplicar"),
 ("Pesos","PESO_NETO/BRUTO DBF, G9","kg (G9 mal rotulado 'toneladas')","NUMERIC kg en las 3 tablas; sin conversión"),
 ("Códigos país","CPAIS / país XLS","ISO-2 / inglés mayúsculas","dim_pais unificado con nombre en español e ISO-3"),
 ("Códigos aduana","CADUANA / nombre XLS","3 dígitos / texto","dim_aduana + alias XLS→código"),
 ("Puertos","PUER_DESC","UN/LOCODE + '0000'","dim_puerto con nombre real; '0000'→NO_ESPECIFICADO"),
 ("Nulos/duplicados","todos","sin nulos, sin duplicados","no se eliminó ningún registro; banderas documentan casos especiales"),
 ("Subpartida G9","col 3","float64","CHAR(10) zfill — evita pérdida de dígitos"),
]: w("| " + " | ".join(r) + " |")
w("\nTratamiento de nulos y duplicados: **no se borró ni imputó ningún registro**. Los casos especiales (muestras, pesos en cero, códigos no especificados) se conservan con columnas bandera para trazabilidad total.")

# 2.6
w("\n## 2.6. Transformación\n")
w("- **Filtros**: ninguno destructivo. Se derivaron banderas: `periodo_completo_detalle` (2016–2019=TRUE), `es_muestra`, `peso_cero`, `fob_cero`, `es_exportacion_definitiva`.")
w("- **Columnas derivadas**: `anio_numeracion`, `mes_numeracion` (desde fec_num); `aduana_codigo` en mensual (alias XLS); `partida_arancelaria` texto en G9.")
w("- **Agrupaciones**: `mensual_agregado` (año×mes×país×aduana×FOB) para análisis sin perder el grano detalle.")
w("- **Consolidación anual/mensual**: mensual desde XLS (fuente completa); anual disponible por SUM en SQL sobre las 3 tablas.")
w("- **Cálculos**: cobertura DBF vs XLS por año (`val_dbf_vs_xls`), diferencias XLS vs G9.")

# 2.7
w("\n## 2.7. Integración\n")
w("- **Combinación de períodos**: los 10 DBF se concatenaron por `anio_archivo`; los 10 XLS por `anio`; las 21 hojas de G9 por nombre de hoja. No hubo solapamiento de períodos entre archivos del mismo tipo.")
w("- **Verificación de duplicación**: llave natural `ndcl+nume_serie+aduana_codigo+pais_codigo_iso2+fec_num` → 0 duplicados en el consolidado; UNIQUE constraint en Postgres.")
w("- **Verificación de pérdida**: conteos por archivo = filas cargadas en BD (4,021 / 1,115 / 97,657). Cada XLS declara 'Total de registros: N' que coincide con las filas parseadas.")
w("- **Cruce temporal**: `anio_archivo` vs `anio_numeracion` difieren solo en registros de fines de diciembre (fec_num dic-2015 en archivo 2016); ambos se conservan.")

# 2.8
w("\n## 2.8. Modelo de datos\n")
w("Modelo en estrella: tabla de hechos `exportaciones_detalle` + dimensiones `dim_pais`, `dim_aduana`, `dim_puerto`; más dos tablas de contexto `exportaciones_mensual` (agregado oficial) y `exportaciones_sector` (contexto nacional), y `val_dbf_vs_xls` (control de calidad).\n")
w("| Tabla | PK / UNIQUE | Relaciones |")
w("|---|---|---|")
w("| exportaciones_detalle | id BIGSERIAL; UNIQUE(ndcl,nume_serie,aduana_codigo,pais_codigo_iso2,fec_num) | pais_codigo_iso2→dim_pais; aduana_codigo→dim_aduana; puerto_embarque_locode→dim_puerto |")
w("| exportaciones_mensual | id SERIAL; UNIQUE(partida,aduana_nombre,pais,anio,mes_num) | pais_nombre_origen≈dim_pais.pais_nombre_origen; aduana_codigo→dim_aduana |")
w("| exportaciones_sector | (anio, partida_arentalaria) | partida_arancelaria compartida con detalle/mensual |")
w("| dim_pais / dim_aduana / dim_puerto | SERIAL PK; UNIQUE nombre/código | catálogos de referencia |")
w("| val_dbf_vs_xls | anio PK | resultado de validación |")
w("\nDiagrama: `exportaciones_detalle` (N) → dim_pais, dim_aduana, dim_puerto (1). `exportaciones_mensual` referencia los mismos catálogos por nombre/código. `exportaciones_sector` es independiente (contexto macro).\n")

# 2.9
w("\n## 2.9. Validación\n")
w("### 2.9.1 Cobertura DBF vs XLS vs G9 (FOB US$)\n")
v = val.copy()
v["cobertura_dbf_vs_xls_pct"] = v["cobertura_dbf_vs_xls_pct"].astype(str) + "%"
v["diferencia_xls_vs_g9_pct"] = v["diferencia_xls_vs_g9_pct"].astype(str) + "%"
table(v)
w("\n### 2.9.2 Interpretación\n")
for r in [
 "**2016–2019**: el detalle DBF cubre 95–99% del FOB oficial → el grano fino (exportador, puerto, país) es representativo en este tramo.",
 "**2020–2025**: cobertura DBF colapsa a 0.15–27% → los DBF recientes están incompletos; el análisis de detalle fino se restringe a 2016–2019 (`periodo_completo_detalle=TRUE`) y 2020–2025 se analiza con `exportaciones_mensual`/`exportaciones_sector`.",
 "**XLS vs G9**: diferencias entre -2.2% y +0.9% → fuentes oficiales consistentes; las pequeñas diferencias corresponden a criterios de numeración vs embarque.",
 "**Consistencia temporal**: sin meses faltantes en XLS 2025 (12/12) ni en G9 (año cerrado).",
 "**Registros vs fuente**: 4,021 DBF + 1,115 XLS + 97,657 G9 cargados = conteos exactos de origen; 0 pérdidas en la integración.",
]: w(f"- {r}")
w("\n*Fin del Capítulo II — datos generados por scripts 01_profile.py a 05_chapter.py.*\n")

open(DOC, "w").write("\n".join(L))
print("Documento:", DOC)
