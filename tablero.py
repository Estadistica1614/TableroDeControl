import streamlit as st
import pandas as pd
import re
import os

st.set_page_config(page_title="Validador de Partes", page_icon="🕵️‍♂️", layout="wide")

import base64

def get_image_base64(ruta):
    with open(ruta, "rb") as f:
        return base64.b64encode(f.read()).decode()

ruta_imagen = r"C:\Users\ignac\Downloads\DGIC.png"

if os.path.exists(ruta_imagen):
    img_b64 = get_image_base64(ruta_imagen)
    # Flexbox se asegura de que la imagen y el título convivan exactamente en el mismo centro horizontal y vertical
    html_header = f"""
    <div style="display: flex; align-items: center; justify-content: flex-start; gap: 20px; margin-bottom: 20px;">
        <img src="data:image/png;base64,{img_b64}" width="90">
        <h1 style="margin: 0; padding: 0;">SISTEMA DE CORRECIÓN DE PARTES OPERATIVOS</h1>
    </div>
    """
    st.markdown(html_header, unsafe_allow_html=True)
else:
    st.markdown("<h1 style='margin-bottom: 20px;'>SISTEMA DE CORRECIÓN DE PARTES OPERATIVOS</h1>", unsafe_allow_html=True)

    
st.markdown("Subí el archivo Excel para detectar directamente **en qué celda está el error**.")

archivo_subido = st.file_uploader("Arrastrá tu archivo Excel acá", type=["xlsx"])

# Función para convertir número de columna a Letra (1->A, 2->B, 27->AA)
def col_letter(n):
    string = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        string = chr(65 + remainder) + string
    return string

if archivo_subido is not None:
    try:
        df = pd.read_excel(archivo_subido, engine="openpyxl")
        
        # Mapeamos las columnas originales a su letra de Excel ANTES de agregar nuevas
        excel_col_mapping = {}
        for i, col in enumerate(df.columns):
            excel_col_mapping[col] = col_letter(i + 1)
            
        if "ERRORES_VALIDACION" not in df.columns:
            df.insert(0, "ERRORES_VALIDACION", "")
        else:
            df["ERRORES_VALIDACION"] = ""
            
        if "CELDA_DEL_ERROR" not in df.columns:
            df.insert(1, "CELDA_DEL_ERROR", "")
        else:
            df["CELDA_DEL_ERROR"] = ""

        # El índice de pandas empieza en 0. En Excel, la fila 1 es el encabezado y los datos empiezan en la 2.
        df["_ROW_EXCEL"] = df.index + 2

        def es_vacio(serie):
            return pd.isna(serie) | (serie.astype(str).str.strip() == "") | (serie.astype(str).str.strip() == "-")

        def registrar_error(mask, mensaje, nombre_columna):
            if not mask.any(): return
            
            # Anotar el error
            df.loc[mask, "ERRORES_VALIDACION"] += mensaje + " | "
            
            # Anotar la celda (Columna + Fila)
            if nombre_columna and nombre_columna in excel_col_mapping:
                letra = excel_col_mapping[nombre_columna]
                celdas = letra + df.loc[mask, "_ROW_EXCEL"].astype(str)
                df.loc[mask, "CELDA_DEL_ERROR"] += celdas + ", "

        # -------------------------------------------------------------------
        # REGLAS DE VALIDACIÓN
        # -------------------------------------------------------------------
        cols_obligatorias = {
            "COD_DEPENDENCIA": "Falta Dependencia",
            "FECHA": "Falta Fecha",
            "HORA": "Falta Hora",
            "DELITO NRO. 1": "Falta Delito 1",
            "COORDENADAS": "Faltan Coordenadas"
        }
        for col, msg in cols_obligatorias.items():
            if col in df.columns:
                registrar_error(es_vacio(df[col]), msg, col)

        if "TIPO DE INTERVENCION POLICIAL" in df.columns:
            intervencion = df["TIPO DE INTERVENCION POLICIAL"].astype(str).str.strip().str.upper()
            mask_otra = intervencion == "OTRA"
            registrar_error(mask_otra, "Intervención es 'OTRA'", "TIPO DE INTERVENCION POLICIAL")
            
            # Nueva Regla: Evaluaciones Periciales no debe tener incautación
            mask_pericial = (intervencion == "EVALUACIONES PERICIALES")
            # Buscamos si hay algo de incautación (basado en la posterior validación de drogas o incautacion general)
            if "INCAUTACION" in df.columns:
                mask_incaut_pos = ~es_vacio(df["INCAUTACION"]) & ~df["INCAUTACION"].astype(str).str.strip().str.upper().isin(["NO", "N/A", "0"])
                registrar_error(mask_pericial & mask_incaut_pos, "Evaluaciones Periciales no debería tener Elementos Secuestrados", "INCAUTACION")

        if "FECHA" in df.columns:
            mask_ok = df["FECHA"].astype(str).str.strip().str.match(r"^\d{4}-\d{2}-\d{2}$")
            mask_mal = ~es_vacio(df["FECHA"]) & ~mask_ok
            registrar_error(mask_mal, "Formato de FECHA inválido", "FECHA")

        if "COORDENADAS" in df.columns:
            mask_sin_menos = ~es_vacio(df["COORDENADAS"]) & ~df["COORDENADAS"].astype(str).str.strip().str.startswith("-")
            registrar_error(mask_sin_menos, "Coordenada no empieza con (-)", "COORDENADAS")

        if "APELLIDO" in df.columns and "SITUACION PROCESAL" in df.columns:
            mask = ~es_vacio(df["APELLIDO"]) & es_vacio(df["SITUACION PROCESAL"])
            registrar_error(mask, "Falta SITUACION PROCESAL", "SITUACION PROCESAL")

        if "INCAUTACION" in df.columns:
            mask = df["INCAUTACION"].astype(str).str.strip().str.upper().isin(["OTROS", "OTRA", "OTRAS", "OTRO"])
            registrar_error(mask, "Incautación es 'OTROS'", "INCAUTACION")

        if "TIPO DE MEDICION ELEMENTO" in df.columns:
            mask = df["TIPO DE MEDICION ELEMENTO"].astype(str).str.strip().str.upper().isin(["OTRAS", "OTROS", "OTRA", "OTRO"])
            registrar_error(mask, "TIPO DE MEDICION es 'OTRAS'", "TIPO DE MEDICION ELEMENTO")

        # Regla: Reemplazar 'ARGENTINO' por 'ARGENTINA'
        for col_nac in ["NACIONALIDAD", "NACIONALIDAD VICTIMA"]:
            if col_nac in df.columns:
                mask = df[col_nac].astype(str).str.strip().str.upper() == "ARGENTINO"
                registrar_error(mask, "Nacionalidad debe decir ARGENTINA", col_nac)

        # Regla: Sexo/Género debe usar MASCULINO/FEMENINO en vez de HOMBRE/MUJER
        for col_gen in ["SEXO/GENERO", "SEXO/GENERO VICTIMA"]:
            if col_gen in df.columns:
                val = df[col_gen].astype(str).str.strip().str.upper()
                # Chequea si el texto contiene la palabra HOMBRE o MUJER en cualquier parte
                mask = val.str.contains("HOMBRE|MUJER", na=False, regex=True)
                registrar_error(mask, "Género: usar MASCULINO o FEMENINO", col_gen)

        # Nueva Regla: LP 1111 Alert
        if "LP" in df.columns:
            mask_lp = df["LP"].astype(str).str.strip() == "1111"
            registrar_error(mask_lp, "Alerta: Verificando Legajo 1111", "LP")

        # Nueva Regla: Captura Revisar Causa
        if "DELITO NRO. 1" in df.columns and "CAUSA" in df.columns:
            mask_captura = (df["DELITO NRO. 1"].astype(str).str.strip().str.upper() == "CAPTURA") & \
                           (df["CAUSA"].astype(str).str.strip() == "-")
            registrar_error(mask_captura, "REVISAR CAUSA! (Captura sin causa detallada)", "DELITO NRO. 1")

        # -------------------------------------------------------------------
        # NUEVAS REGLAS CRUZADAS Y TEMPORALES DE PARTE OPERATIVO
        # -------------------------------------------------------------------

        # Criterio 1: El año del parte tiene que ser obligatoriamente 2026
        if "PARTE OPERATIVO" in df.columns:
            po_text = df["PARTE OPERATIVO"].astype(str).str.strip()
            # Marcamos todo lo que NO termine en 2026 (y que no esté vacío)
            mask_bad_year = (~es_vacio(po_text)) & (~po_text.str.endswith("2026"))
            registrar_error(mask_bad_year, "Año del Parte no es 2026", "PARTE OPERATIVO")

        # Criterio 2: Coincidencia del prefijo de Dependencia con el Parte Operativo
        if "COD_DEPENDENCIA" in df.columns and "PARTE OPERATIVO" in df.columns:
            # Extrae el número base inicial (ej. "122") de "122 - COMISARIA VECINAL 6 B" o similares
            prefijo_dep = df["COD_DEPENDENCIA"].astype(str).str.extract(r"^(\d+)", expand=False)
            
            # Extrae el número antes de "PO" (ej. "122") de "122-PO-131-2026"
            prefijo_po = df["PARTE OPERATIVO"].astype(str).str.extract(r"^(\d+)-?\s*PO", expand=False)
            
            # Chequeamos si son distintos (solo cuando ambos campos trajeron números analizables)
            mask_mismatch = pd.notna(prefijo_dep) & pd.notna(prefijo_po) & (prefijo_dep != prefijo_po)
            registrar_error(mask_mismatch, "El código Dependencia NO coincide con el Parte", "PARTE OPERATIVO")

        df["ERRORES_DROGAS"] = ""
        df["CELDA_DROGAS"] = ""
        
        def registrar_droga(mask, mensaje, nombre_columna):
            if not mask.any(): return
            df.loc[mask, "ERRORES_DROGAS"] += mensaje + " | "
            if nombre_columna and nombre_columna in excel_col_mapping:
                letra = excel_col_mapping[nombre_columna]
                celdas = letra + df.loc[mask, "_ROW_EXCEL"].astype(str)
                df.loc[mask, "CELDA_DROGAS"] += celdas + ", "

        # Validaciones de Drogas
        # Buscador super-agresivo (Wildcards) pero con filtros de exclusión explícita
        def encontrar_col_agresiva(palabras_clave, prohibidas=[]):
            for c in df.columns:
                n = c.strip().upper()
                if any(p in n for p in palabras_clave) and not any(proh in n for proh in prohibidas):
                    return c
            return None

        # Evitamos agarrar columnas de Armamento
        c_droga   = encontrar_col_agresiva(["DROGA", "ESTUPEFACIENTE"])
        c_cant    = encontrar_col_agresiva(["CANTIDAD_DRO", "PESO", "CANT_D", "CANTIDAD DE DRO", "CANTIDAD DRO"], prohibidas=["ARMAR", "ARMA", "MUNICION"])
        if not c_cant: c_cant = encontrar_col_agresiva(["CANTIDAD", "CANT"], prohibidas=["ARMA", "ARMAR", "MUNI", "TIPO"])
        
        c_medida  = encontrar_col_agresiva(["MEDICION", "MEDIDA", "UNIDAD", "TIPO_MEDICION"], prohibidas=["ARMA", "ARMAR", "MUNI"])

        hay_columnas_drogas = bool(c_droga and c_cant and c_medida)

        if hay_columnas_drogas:
            tipo = df[c_droga].astype(str).str.strip().str.upper()
            cant = pd.to_numeric(df[c_cant], errors='coerce').fillna(-1)
            med = df[c_medida].astype(str).str.strip().str.upper()

            # Máscara de control: ignoramos por completo si el campo droga dice literalmente "-" o está vacío
            mask_droga_valida = (tipo != "-") & (~tipo.isin(["", "NAN", "NULL", "NONE"]))

            # Nueva Regla: Fármacos alert
            mask_farmaco = tipo.str.contains("FÁRMACO|FARMACO", na=False)
            registrar_droga(mask_droga_valida & mask_farmaco, "Alerta: Fármaco detectado como droga", c_droga)

            # 1. Ningun tipo de droga puede tener cantidad 0 (solo si la droga es válida)
            registrar_droga(mask_droga_valida & (cant == 0), "Alerta: Cantidad es 0", c_cant)

            # 2. Si es KILOGRAMO debe alertar (a excepción de HOJAS DE COCA)
            mask_kilo = mask_droga_valida & med.str.contains("KILOGRAMO") & (tipo != "HOJAS DE COCA")
            registrar_droga(mask_kilo, "Pesaje en KILOGRAMOS (Permitido solo para Hojas de Coca)", c_medida)

            # 3. COCAINA y MARIHUANA debe ser inferior a 100 gramos
            mask_dura = mask_droga_valida & tipo.isin(["COCAINA", "MARIHUANA"]) & med.str.contains("GRAMO") & (cant >= 100)
            registrar_droga(mask_dura, "Excede/Iguala límite (Permitido inferior a 100 gramos)", c_cant)

            # 4. EXTASIS debe alertar únicamente cuando son más de 10 unidades
            mask_ext = mask_droga_valida & (tipo == "EXTASIS") & med.str.contains("UNIDAD") & (cant > 10)
            registrar_droga(mask_ext, "Excede límite permitido (>10 unidades)", c_cant)

        # Limpiamos remanentes de las cadenas unidas
        df["ERRORES_VALIDACION"] = df["ERRORES_VALIDACION"].str.strip(" | ")
        df["CELDA_DEL_ERROR"] = df["CELDA_DEL_ERROR"].str.strip(", ")
        df["ERRORES_DROGAS"] = df["ERRORES_DROGAS"].str.strip(" | ")
        df["CELDA_DROGAS"] = df["CELDA_DROGAS"].str.strip(", ")

        # -------------------------------------------------------------------
        # GENERACIÓN DE TABLA FINAL
        # -------------------------------------------------------------------
        df_con_errores = df[df["ERRORES_VALIDACION"] != ""].copy()
        df_drogas_errores = df[df["ERRORES_DROGAS"] != ""].copy()
        
        st.markdown("---")
        
        # Rendereado métrico dinámico dependiendo si el Excel tiene o no data de drogas
        if hay_columnas_drogas:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total de filas analizadas", len(df))
            col2.metric("Anomalías Generales", len(df_con_errores))
            col3.metric("Anomalías Drogas", len(df_drogas_errores))
        else:
            col1, col2 = st.columns(2)
            col1.metric("Total de filas analizadas", len(df))
            col2.metric("Filas con anomalías", len(df_con_errores))
            # Mostramos advertencia visual para que el usuario sepa por qué no está la tabla extra
            st.warning("⚠️ El sistema no está evaluando drogas: El Excel subido no posee columnas legibles con palabras como 'DROGA', 'CANTIDAD' y 'MEDICIÓN'.")

        if len(df_con_errores) == 0:
            st.success("¡Todo perfecto con las reglas básicas! Ninguna fila rompe validaciones generales.")
        else:
            st.info(f"Atención: Se identificaron anomalías en {len(df_con_errores)} filas.", icon="ℹ️")
            
            # Recortamos el Dataframe
            cols_finales = ["ERRORES_VALIDACION"]
            if "PARTE OPERATIVO" in df.columns:
                cols_finales.append("PARTE OPERATIVO")
            cols_finales.append("CELDA_DEL_ERROR")
            
            df_final = df_con_errores[cols_finales].copy()
            
            # Pintamos el dataframe de azul profundo con letras blancas
            def bg_color_azul(row):
                return ['background-color: #004B87; color: #FFFFFF; font-weight: bold;'] * len(row)
            
            st.markdown("### ℹ️ Detalle de Correcciones")
            st.dataframe(df_final.style.apply(bg_color_azul, axis=1), use_container_width=True)

        if hay_columnas_drogas:
            st.markdown("### 💊 Revisión de Drogas")
            if len(df_drogas_errores) > 0:
                st.markdown("*(Se detectaron alertas en pesajes y clasificaciones)*")
                
                # Atrapamos absolutamente todas las columnas relacionadas sin importar su escritura exacta
                posibles_keys = [c_droga, c_cant, c_medida, "PARTE OPERATIVO", "CELDA_DROGAS", "ERRORES_DROGAS"]
                cols_req = [c for c in df_drogas_errores.columns if c in posibles_keys]
                
                df_d_final = df_drogas_errores[cols_req].copy()
                
                # Formateador visual para limitar la cantidad a solo 2 decimales (o ninguno si es un número entero)
                if c_cant in df_d_final.columns:
                    def formatear_decimales(val):
                        try:
                            num = float(val)
                            # Si no tiene decimales reales, se imprime como entero, sino con tope de 2
                            if num.is_integer():
                                return f"{int(num)}"
                            else:
                                return f"{num:.2f}"
                        except:
                            return val # Si por error contiene texto u otra cosa, se deja intacto
                            
                    df_d_final[c_cant] = df_d_final[c_cant].apply(formatear_decimales)
                
                # Tonalidad distinta para que se destaque del resto de validaciones
                def bg_color_droga(row):
                    return ['background-color: #2F1A4A; color: #DFCAFD; font-weight: bold; border-bottom: 1px solid #6A4C93;'] * len(row)
                    
                st.dataframe(df_d_final.style.apply(bg_color_droga, axis=1), use_container_width=True)
            else:
                st.success("¡Droga en regla! No se encontró ninguna irregularidad de pesajes o cantidades.", icon="✅")

    except Exception as e:
        # Aislado el error de sistema, lo dejamos rojo para diferencias de las validaciones de datos
        st.error(f"Ocurrió un error general al procesar el archivo: {e}")

# Footer inferior. Usamos el equivalente literal en HTML a la tipografía "st.title" de Streamlit
st.markdown("<br><br><br><h1 style='text-align: center; color: white;'>DESARROLLO - DEC</h1>", unsafe_allow_html=True)
