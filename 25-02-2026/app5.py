import streamlit as st
import pandas as pd
import plotly.express as px
import re

# Configuración de la página
st.set_page_config(page_title="Dashboard Gestión Inmovision 2026", layout="wide", page_icon="📊")

# --- ESTILO PARA ELIMINAR DECIMALES INNECESARIOS EN TABLAS ---
st.markdown("""
    <style>
    [data-testid="stTable"] td { text-align: right !important; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIÓN PARA EXTRAER ID DEL LINK ---
def extraer_id(link, default):
    if not link: return default
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", link)
    return match.group(1) if match else link

# --- SECCIÓN LATERAL ---
st.sidebar.header("⚙️ Configuración de Datos")
def_link_cortes = "https://docs.google.com/spreadsheets/d/1XTwe17xvug4FN5jC0pFjVDQ6W61PKR1j"
def_link_contratos = "https://docs.google.com/spreadsheets/d/1HjDMAggJ5esJwqFEQ891MnPYhr7y-CAF"
def_link_ins = "https://docs.google.com/spreadsheets/d/19TJ6ljgBusN5EGxBOJYih1xmF7oIReJE"

with st.sidebar.expander("🔗 Pegar Links de Google Sheets", expanded=True):
    url_cortes = st.text_input("Link Sheet Cortes:", def_link_cortes)
    url_contratos = st.text_input("Link Sheet Contratos:", def_link_contratos)
    url_ins = st.text_input("Link Sheet Instalaciones:", def_link_ins)

sheet_id_cortes = extraer_id(url_cortes, "1XTwe17xvug4FN5jC0pFjVDQ6W61PKR1j")
sheet_id_contratos = extraer_id(url_contratos, "1HjDMAggJ5esJwqFEQ891MnPYhr7y-CAF")
sheet_id_ins = extraer_id(url_ins, "19TJ6ljgBusN5EGxBOJYih1xmF7oIReJE")

# --- FUNCIONES DE CARGA Y PROCESAMIENTO ---
@st.cache_data(ttl=300)
def load_raw_data(s_cortes, s_contratos, s_ins):
    url_c = f"https://docs.google.com/spreadsheets/d/{s_cortes}/gviz/tq?tqx=out:csv&sheet=CORTES%20(2)"
    url_con = f"https://docs.google.com/spreadsheets/d/{s_contratos}/export?format=csv&gid=494293159"
    url_i = f"https://docs.google.com/spreadsheets/d/{s_ins}/gviz/tq?tqx=out:csv&sheet=Hoja1"
    try:
        df_contratos = pd.read_csv(url_con)
        df_contratos['FechaActivacionContrato'] = pd.to_datetime(df_contratos['FechaActivacionContrato'], errors='coerce')
    except: df_contratos = None
    try: df_cortes_raw = pd.read_csv(url_c, header=None)
    except: df_cortes_raw = None
    try:
        df_ins = pd.read_csv(url_i)
        df_ins.columns = df_ins.columns.str.strip()
        col_f = 'FECHA' if 'FECHA' in df_ins.columns else df_ins.columns[0]
        df_ins[col_f] = pd.to_datetime(df_ins[col_f], dayfirst=True, errors='coerce')
        df_ins = df_ins.dropna(subset=[col_f])
    except: df_ins = None
    return df_cortes_raw, df_contratos, df_ins

def extract_smart_table(df_raw, title_keyword):
    if df_raw is None: return None
    start_idx = -1
    for i, row in df_raw.iterrows():
        if row.astype(str).str.contains(title_keyword, case=False, na=False).any():
            start_idx = i
            break
    if start_idx == -1: return None
    header_row = -1
    for i in range(start_idx, start_idx + 6):
        row_str = df_raw.iloc[i].astype(str).str.upper().values
        if any(x in str(row_str) for x in ['ENERO', 'MOTIVO', 'CORTADOS', 'RECUPERADOS']):
            header_row = i
            break
    if header_row == -1: return None
    df_sub = df_raw.iloc[header_row + 1:].copy()
    df_sub.columns = [f"COL_{i}" for i in range(len(df_sub.columns))]
    final_rows = []
    for _, row in df_sub.iterrows():
        if row.isnull().all(): break
        first_val = str(row.dropna().iloc[0]).upper() if not row.dropna().empty else ""
        if "RESUMEN" in first_val or first_val == "" or "ABANDONO" in first_val: break
        final_rows.append(row)
        if "TOTAL" in first_val: break
    if not final_rows: return None
    df_res = pd.DataFrame(final_rows).dropna(axis=1, how='all')
    for col in df_res.columns[1:]:
        df_res[col] = pd.to_numeric(df_res[col], errors='coerce').fillna(0)
    if len(df_res.columns) > 3: df_res = df_res.iloc[:, :-2]
    meses_nombres = ['MOTIVO', 'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 
                     'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
    df_res.columns = [meses_nombres[i] if i < len(meses_nombres) else col for i, col in enumerate(df_res.columns)]
    cols_num = df_res.select_dtypes(include=['number']).columns
    df_res['TOTAL_REAL'] = df_res[cols_num].sum(axis=1)
    return df_res

def mostrar_ranking_motivos(df, columna_valor, titulo_grafica, escala_color='Reds'):
    df_m = df[~df['MOTIVO'].str.contains('TOTAL', case=False)].copy()
    total_periodo = df_m[columna_valor].sum()
    if total_periodo > 0:
        df_m['Porcentaje'] = (df_m[columna_valor] / total_periodo) * 100
        df_m = df_m.sort_values(by=columna_valor, ascending=True)
        fig = px.bar(df_m, x=columna_valor, y='MOTIVO', orientation='h', title=titulo_grafica,
                    text=df_m['Porcentaje'].apply(lambda x: f'{x:.1f}%'),
                    color=columna_valor, color_continuous_scale=escala_color)
        fig.update_traces(textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

def mostrar_graficas_seccion(df_plot, titulo, color='#636EFA'):
    st.subheader(titulo)
    if df_plot is not None:
        df_sin_total = df_plot[~df_plot['MOTIVO'].astype(str).str.contains('TOTAL', case=False)].copy()
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df_sin_total, x='MOTIVO', y='TOTAL_REAL', title=f"Barras: {titulo}", color_discrete_sequence=[color], text_auto=True), use_container_width=True)
        with c2: st.plotly_chart(px.pie(df_sin_total, names='MOTIVO', values='TOTAL_REAL', title=f"Distribución: {titulo}", hole=0.4), use_container_width=True)
        with st.expander(f"📥 Ver tabla detallada"):
            st.dataframe(df_plot.style.format(precision=0), use_container_width=True, hide_index=True)

def procesar_trimestral(df):
    if df is None: return None
    df_d = df[~df['MOTIVO'].astype(str).str.contains('TOTAL', case=False)].copy()
    mapa = {'T1': ['ENERO', 'FEBRERO', 'MARZO'], 'T2': ['ABRIL', 'MAYO', 'JUNIO'], 
            'T3': ['JULIO', 'AGOSTO', 'SEPTIEMBRE'], 'T4': ['OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']}
    df_tri = df_d[['MOTIVO']].copy()
    for tri, meses in mapa.items():
        existentes = [m for m in meses if m in df_d.columns]
        df_tri[tri] = df_d[existentes].sum(axis=1) if existentes else 0
    return df_tri

def plot_contract_distribution(df, columna, titulo, color_hex):
    if df is None or columna not in df.columns: return
    df_grouped = df.groupby(columna).size().reset_index(name='Cantidad')
    df_grouped = df_grouped.sort_values(by='Cantidad', ascending=False).head(10)
    if not df_grouped.empty:
        fig = px.bar(df_grouped, x='Cantidad', y=columna, orientation='h', title=f"{titulo} (Top 10)", text='Cantidad', color_discrete_sequence=[color_hex])
        fig.update_layout(yaxis={'categoryorder':'total ascending'}, height=400)
        st.plotly_chart(fig, use_container_width=True)

# --- FLUJO PRINCIPAL ---
try:
    data_cortes, data_contratos, data_ins = load_raw_data(sheet_id_cortes, sheet_id_contratos, sheet_id_ins)
    df_c_anual = extract_smart_table(data_cortes, "CORTES VOLUNTARIOS")
    df_r_anual = extract_smart_table(data_cortes, "RECUPERADO")

    st.sidebar.header("Filtros Temporales")
    if data_ins is not None:
        col_fecha_ins = 'FECHA' if 'FECHA' in data_ins.columns else data_ins.columns[0]
        años_disponibles = sorted(data_ins[col_fecha_ins].dt.year.unique(), reverse=True)
        año_seleccionado = st.sidebar.selectbox("Seleccionar Año:", años_disponibles, index=0)
    else: año_seleccionado = 2026

    st.title("📊 Control de Gestión de Clientes Inmovision")
    tab1, tab2, tab3, tab4 = st.tabs(["📌 Resúmenes Anuales", "📉 Análisis Trimestral", "📉 Análisis Trimestral Contratos", "📈 Contratos por Mes"])

    meses_list = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']

    def get_vals(df):
        if df is None: return [0]*12
        f = df[df['MOTIVO'].str.contains('TOTAL', case=False)]
        return [int(f[m].iloc[0]) if m in f.columns else 0 for m in meses_list]

    s_c, s_r = get_vals(df_c_anual), get_vals(df_r_anual)
    s_n = [c - r for c, r in zip(s_c, s_r)]
    df_l = pd.DataFrame({'Mes': meses_list, 'Cortes': s_c, 'Recuperados': s_r, 'Neto': s_n})

    with tab1:
        v_c = df_c_anual[df_c_anual['MOTIVO'].str.contains('TOTAL', case=False)]['TOTAL_REAL'].iloc[0] if df_c_anual is not None else 0
        v_r = df_r_anual[df_r_anual['MOTIVO'].str.contains('TOTAL', case=False)]['TOTAL_REAL'].iloc[0] if df_r_anual is not None else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Cortes Voluntarios", f"{int(v_c):,}")
        m2.metric("Clientes Recuperados", f"{int(v_r):,}")
        m3.metric("Neto Abandonos", f"{int(v_c - v_r):,}", delta="Bajas Finales", delta_color="inverse")

        st.divider()
        # --- TENDENCIA ANUAL CON NÚMEROS ---
        fig_anual = px.line(df_l, x='Mes', y=['Cortes', 'Recuperados', 'Neto'], title="Tendencia Anual de Bajas y Recuperaciones", markers=True)
        # ESTA ES LA LÍNEA QUE DEBES CAMBIAR:
        fig_anual.update_traces(mode='lines+markers+text', textposition="top center", texttemplate='%{y}')
        st.plotly_chart(fig_anual, use_container_width=True)

        st.divider()
        col_rank1, col_rank2 = st.columns(2)
        with col_rank1: 
            if df_c_anual is not None: mostrar_ranking_motivos(df_c_anual, 'TOTAL_REAL', "Ranking Anual de Cortes", 'Reds')
        with col_rank2: 
            if df_r_anual is not None: mostrar_ranking_motivos(df_r_anual, 'TOTAL_REAL', "Ranking Anual de Recuperaciones", 'Greens')

        mostrar_graficas_seccion(df_c_anual, "Cortes Voluntarios (Anual)", "#EF553B")
        mostrar_graficas_seccion(df_r_anual, "Clientes Recuperados (Anual)", "#00CC96")

    with tab2:
        st.header("📅 Seguimiento por Trimestre (Cortes)")
        df_c_tri = procesar_trimestral(df_c_anual)
        df_r_tri = procesar_trimestral(df_r_anual)
        if df_c_tri is not None:
            sel_tri = st.selectbox("Seleccionar Período:", ['T1', 'T2', 'T3', 'T4'])
            # --- MÉTRICAS TRIMESTRALES ---
            v_c_tri = df_c_tri[sel_tri].sum()
            v_r_tri = df_r_tri[sel_tri].sum()
            
            c_m1, c_m2, c_m3 = st.columns(3)
            c_m1.metric("Cortes Voluntarios", f"{int(v_c_tri):,}")
            c_m2.metric("Clientes Recuperados", f"{int(v_r_tri):,}")
            c_m3.metric("Neto Abandonos", f"{int(v_c_tri - v_r_tri):,}", delta="Bajas Finales", delta_color="inverse")
            st.divider()
            # -----------------------------
            periodos = {'T1':['ENERO','FEBRERO','MARZO'], 'T2':['ABRIL','MAYO','JUNIO'], 'T3':['JULIO','AGOSTO','SEPTIEMBRE'], 'T4':['OCTUBRE','NOVIEMBRE','DICIEMBRE']}
            df_tri_l = df_l[df_l['Mes'].isin(periodos[sel_tri])]
            
            # --- TENDENCIA TRIMESTRAL CON NÚMEROS ---
            fig_t = px.line(df_tri_l, x='Mes', y=['Cortes', 'Recuperados', 'Neto'], title=f"Tendencia {sel_tri}", markers=True)
            fig_t.update_traces(mode='lines+markers+text', textposition="top center", texttemplate='%{y}')
            st.plotly_chart(fig_t, use_container_width=True)
            
            ct1, ct2 = st.columns(2)
            with ct1: mostrar_ranking_motivos(df_c_tri, sel_tri, f"Cortes en {sel_tri}", 'Reds')
            with ct2: mostrar_ranking_motivos(df_r_tri, sel_tri, f"Recuperaciones en {sel_tri}", 'Greens')

            st.divider()
            df_c_tri_p = df_c_tri[['MOTIVO', sel_tri]].rename(columns={sel_tri: 'TOTAL_REAL'})
            mostrar_graficas_seccion(df_c_tri_p, f"Detalle Cortes {sel_tri}", "#EF553B")
            st.divider()
            df_r_tri_p = df_r_tri[['MOTIVO', sel_tri]].rename(columns={sel_tri: 'TOTAL_REAL'})
            mostrar_graficas_seccion(df_r_tri_p, f"Detalle Recuperaciones {sel_tri}", "#00CC96")

    # --- LÓGICA DE CONTRATOS ---
    base_n = [0]*12
    if data_ins is not None:
        try:
            df_ins_filtered = data_ins[data_ins[col_fecha_ins].dt.year == año_seleccionado].copy()
            col_servicio = next((c for c in df_ins_filtered.columns if 'SERVICIO' in c.upper()), None)
            col_estado = next((c for c in df_ins_filtered.columns if 'ESTADO' in c.upper()), None)
            if col_servicio and col_estado:
                servicios_v = ['CROSSELLING', 'INSTALACIÓN CÁMARA', 'INSTALACION ESPECIAL', 'INSTALACIÓN NUEVA', 'SMART HOME']
                mask = (df_ins_filtered[col_servicio].astype(str).str.strip().str.upper().isin(servicios_v)) & (df_ins_filtered[col_estado].astype(str).str.strip().str.upper() == 'INSTALADO')
                n_counts = df_ins_filtered[mask][col_fecha_ins].dt.month.value_counts()
                for m, v in n_counts.items(): base_n[int(m)-1] = int(v)
        except: pass

    if data_contratos is not None:
        ultima_fecha = data_contratos['FechaActivacionContrato'].max()
        df_final = pd.DataFrame({'Mes': meses_list})
        totales_c, activaciones_r = [], []
        for mes in range(1, 13):
            fecha_ini = pd.Timestamp(year=año_seleccionado, month=mes, day=1)
            if fecha_ini > ultima_fecha: 
                totales_c.append(0); activaciones_r.append(0)
            else:
                fecha_c = min(fecha_ini + pd.offsets.MonthEnd(0), ultima_fecha)
                totales_c.append(data_contratos[data_contratos['FechaActivacionContrato'] <= fecha_c].shape[0])
                activaciones_r.append(data_contratos[(data_contratos['FechaActivacionContrato'].dt.month == mes) & (data_contratos['FechaActivacionContrato'].dt.year == año_seleccionado)].shape[0])
        
        df_final['Total Contratos'] = totales_c
        df_final['Nuevos Contratos'] = base_n
        df_final['Neto_Abandono'] = s_n
        df_final['Churn Rate (%)'] = df_final.apply(lambda x: (x['Neto_Abandono']/x['Total Contratos']*100) if x['Total Contratos']>0 else 0, axis=1)
        df_final['Acquisition Rate (%)'] = df_final.apply(lambda x: (x['Nuevos Contratos']/x['Total Contratos']*100) if x['Total Contratos']>0 else 0, axis=1)
        df_final['NROD (%)'] = df_final['Acquisition Rate (%)'] - df_final['Churn Rate (%)']

        with tab3:
            st.header(f"📉 Análisis Trimestral Contratos ({año_seleccionado})")
            sel_tri_c = st.selectbox("Trimestre:", ['T1', 'T2', 'T3', 'T4'], key='tri_c_k')
            p_c = {'T1':['ENERO','FEBRERO','MARZO'], 'T2':['ABRIL','MAYO','JUNIO'], 'T3':['JULIO','AGOSTO','SEPTIEMBRE'], 'T4':['OCTUBRE','NOVIEMBRE','DICIEMBRE']}
            df_tri_f = df_final[df_final['Mes'].isin(p_c[sel_tri_c])].copy()
            
            # --- TASAS TRIMESTRALES CON NÚMEROS (%) ---
            fig_tri_c = px.line(df_tri_f, x='Mes', y=['Churn Rate (%)', 'Acquisition Rate (%)', 'NROD (%)'], markers=True, title=f"Tasas {sel_tri_c}")
            fig_tri_c.update_traces(mode='lines+markers+text', textposition="top center", texttemplate='%{y:.1f}%')
            st.plotly_chart(fig_tri_c, use_container_width=True)

            st.subheader("📋 Métricas Consolidadas")
            # Tablas con formato corregido
            st.table(df_tri_f[['Mes', 'Total Contratos', 'Neto_Abandono', 'Churn Rate (%)']].set_index('Mes').T.style.format(lambda x: f"{int(x):,}" if x >= 100 else f"{x:.2f}%"))
            st.table(df_tri_f[['Mes', 'Nuevos Contratos', 'Total Contratos', 'Acquisition Rate (%)']].set_index('Mes').T.style.format(lambda x: f"{int(x):,}" if x >= 100 else f"{x:.2f}%"))
            st.table(df_tri_f[['Mes', 'Acquisition Rate (%)', 'Churn Rate (%)', 'NROD (%)']].set_index('Mes').T.style.format("{:.2f}%"))

            st.divider()
            p_num = {'T1':[1,2,3], 'T2':[4,5,6], 'T3':[7,8,9], 'T4':[10,11,12]}[sel_tri_c]
            df_c_tri_det = data_contratos[data_contratos['FechaActivacionContrato'].dt.month.isin(p_num)]
            plot_contract_distribution(df_c_tri_det, 'Elementos', f"Planes {sel_tri_c}", '#AB63FA')

        with tab4:
            st.header(f"📈 Reporte Mensual Completo ({año_seleccionado})")
            # --- TASAS MENSUALES CON NÚMEROS (%) ---
            fig_m = px.line(df_final[df_final['Total Contratos']>0], x='Mes', y=['Churn Rate (%)', 'Acquisition Rate (%)', 'NROD (%)'], markers=True)
            fig_m.update_traces(mode='lines+markers+text', textposition="top center", texttemplate='%{y:.1f}%')
            st.plotly_chart(fig_m, use_container_width=True)
            
            st.subheader("📋 Resumen Anual")
            st.table(df_final[['Mes', 'Total Contratos', 'Churn Rate (%)']].set_index('Mes').T.style.format(lambda x: f"{int(x):,}" if x >= 100 else f"{x:.2f}%"))
            st.table(df_final[['Mes', 'Nuevos Contratos', 'Acquisition Rate (%)']].set_index('Mes').T.style.format(lambda x: f"{int(x):,}" if x >= 100 else f"{x:.2f}%"))
            st.table(df_final[['Mes', 'NROD (%)']].set_index('Mes').T.style.format("{:.2f}%"))

            st.divider()
            c1, c2 = st.columns(2)
            with c1: plot_contract_distribution(data_contratos, 'NombreFormaPago', "Formas de Pago", '#636EFA')
            with c2: plot_contract_distribution(data_contratos, 'NombreZona', "Zonas", '#00CC96')

except Exception as e: st.error(f"Error detectado: {e}")
