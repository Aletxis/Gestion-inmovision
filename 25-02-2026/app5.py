import streamlit as st
import pandas as pd
import plotly.express as px

# Configuración de la página
st.set_page_config(page_title="Dashboard Gestión Inmovision 2026", layout="wide", page_icon="📊")

# --- SECCIÓN LATERAL: CONFIGURACIÓN DE LINKS ---
st.sidebar.header("⚙️ Configuración de Orígenes de Datos")

# Links por defecto (los que has estado usando)
default_sheet_cortes = "1XTwe17xvug4FN5jC0pFjVDQ6W61PKR1j"
default_sheet_contratos = "1HjDMAggJ5esJwqFEQ891MnPYhr7y-CAF"
default_sheet_ins = "19TJ6ljgBusN5EGxBOJYih1xmF7oIReJE"

with st.sidebar.expander("🔗 Editar IDs de Google Sheets"):
    sheet_id_cortes = st.text_input("ID Sheet Cortes:", default_sheet_cortes)
    sheet_id_contratos = st.text_input("ID Sheet Contratos:", default_sheet_contratos)
    sheet_id_ins = st.text_input("ID Sheet Instalaciones:", default_sheet_ins)

# --- FUNCIONES DE CARGA Y PROCESAMIENTO ---
@st.cache_data(ttl=300)
def load_raw_data(s_cortes, s_contratos, s_ins):
    url_cortes = f"https://docs.google.com/spreadsheets/d/{s_cortes}/gviz/tq?tqx=out:csv&sheet=CORTES%20(2)"
    
    gid_contratos = "494293159"
    url_contratos = f"https://docs.google.com/spreadsheets/d/{s_contratos}/export?format=csv&gid={gid_contratos}"
    
    URL_INS = f"https://docs.google.com/spreadsheets/d/{s_ins}/gviz/tq?tqx=out:csv&sheet=Hoja1"

    try:
        df_contratos = pd.read_csv(url_contratos)
        df_contratos['FechaActivacionContrato'] = pd.to_datetime(df_contratos['FechaActivacionContrato'], errors='coerce')
    except:
        df_contratos = None
        
    try:
        df_cortes_raw = pd.read_csv(url_cortes, header=None)
    except:
        df_cortes_raw = None

    try:
        df_ins = pd.read_csv(URL_INS)
        col_fecha = 'FECHA' if 'FECHA' in df_ins.columns else df_ins.columns[0]
        df_ins[col_fecha] = pd.to_datetime(df_ins[col_fecha], dayfirst=True, errors='coerce')
        df_ins = df_ins.dropna(subset=[col_fecha])
    except:
        df_ins = None

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
    temp_headers = [f"COL_{i}" for i in range(len(df_sub.columns))]
    df_sub.columns = temp_headers
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
    if len(df_res.columns) > 3:
        df_res = df_res.iloc[:, :-2]
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
    st.header(titulo)
    if df_plot is not None:
        df_sin_total = df_plot[~df_plot['MOTIVO'].astype(str).str.contains('TOTAL', case=False)].copy()
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.bar(df_sin_total, x='MOTIVO', y='TOTAL_REAL', title=f"Barras {titulo}", color_discrete_sequence=[color], text_auto=True), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df_sin_total, names='MOTIVO', values='TOTAL_REAL', title=f"Distribución {titulo}", hole=0.4), use_container_width=True)
        with st.expander(f"📥 Desplegar tabla detallada de {titulo}"):
            st.dataframe(df_plot, use_container_width=True, hide_index=True)

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
        fig.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="Contratos", yaxis_title=None, height=400)
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
    else:
        año_seleccionado = 2026

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
        df_r_m = df_r_anual[~df_r_anual['MOTIVO'].str.contains('TOTAL', case=False)] if df_r_anual is not None else None
        v_r = df_r_m['TOTAL_REAL'].sum() if df_r_m is not None else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Cortes Voluntarios", f"{int(v_c)}")
        m2.metric("Clientes Recuperados", f"{int(v_r)}")
        m3.metric("Neto Abandonos", f"{int(v_c - v_r)}", delta="Bajas Finales", delta_color="inverse")

        st.divider()
        st.subheader("🎯 Análisis de Motivos Anual")
        col_rank1, col_rank2 = st.columns(2)
        with col_rank1:
            if df_c_anual is not None: mostrar_ranking_motivos(df_c_anual, 'TOTAL_REAL', "Ranking Anual de Cortes", 'Reds')
        with col_rank2:
            if df_r_anual is not None: mostrar_ranking_motivos(df_r_anual, 'TOTAL_REAL', "Ranking Anual de Recuperaciones", 'Greens')

        st.divider()
        st.subheader("📈 Tendencia Mensual (Valores por punto)")
        fig_l = px.line(df_l, x='Mes', y=['Cortes', 'Recuperados', 'Neto'], markers=True, 
                        color_discrete_map={'Cortes': '#EF553B', 'Recuperados': '#00CC96', 'Neto': '#636EFA'})
        fig_l.update_traces(textposition="top center")
        for i, col in enumerate(['Cortes', 'Recuperados', 'Neto']):
            fig_l.data[i].text = df_l[col]
            fig_l.data[i].mode = 'lines+markers+text'
        st.plotly_chart(fig_l, use_container_width=True)

        st.divider()
        mostrar_graficas_seccion(df_c_anual, "Cortes Voluntarios", "#EF553B")
        st.divider()
        mostrar_graficas_seccion(df_r_anual, "Clientes Recuperados", "#00CC96")

    with tab2:
        st.header("📅 Seguimiento por Trimestre")
        df_c_tri = procesar_trimestral(df_c_anual)
        df_r_tri = procesar_trimestral(df_r_anual)
        
        if df_c_tri is not None and df_r_tri is not None:
            sel_tri = st.selectbox("Seleccionar Período (Motivos):", ['T1', 'T2', 'T3', 'T4'])
            periodos = {'T1':['ENERO','FEBRERO','MARZO'], 'T2':['ABRIL','MAYO','JUNIO'], 'T3':['JULIO','AGOSTO','SEPTIEMBRE'], 'T4':['OCTUBRE','NOVIEMBRE','DICIEMBRE']}
            df_tri_l = df_l[df_l['Mes'].isin(periodos[sel_tri])]
            
            fig_tri_l = px.line(df_tri_l, x='Mes', y=['Cortes', 'Recuperados', 'Neto'], title=f"Tendencia {sel_tri}", markers=True)
            for i, col in enumerate(['Cortes', 'Recuperados', 'Neto']):
                fig_tri_l.data[i].text = df_tri_l[col]
                fig_tri_l.data[i].mode = 'lines+markers+text'
                fig_tri_l.data[i].textposition = "top center"
            st.plotly_chart(fig_tri_l, use_container_width=True)
            
            st.divider()
            st.subheader(f"🎯 Análisis de Motivos en {sel_tri}")
            ct1, ct2 = st.columns(2)
            with ct1: mostrar_ranking_motivos(df_c_tri, sel_tri, f"Ranking de Cortes ({sel_tri})", 'Reds')
            with ct2: mostrar_ranking_motivos(df_r_tri, sel_tri, f"Ranking de Recuperaciones ({sel_tri})", 'Greens')

            st.divider()
            df_c_p_t = df_c_tri[['MOTIVO', sel_tri]].rename(columns={sel_tri: 'TOTAL_REAL'})
            df_r_p_t = df_r_tri[['MOTIVO', sel_tri]].rename(columns={sel_tri: 'TOTAL_REAL'})
            mostrar_graficas_seccion(df_c_p_t, f"Detalle Cortes {sel_tri}", "#EF553B")
            st.divider()
            mostrar_graficas_seccion(df_r_p_t, f"Detalle Recuperaciones {sel_tri}", "#00CC96")

    # --- LÓGICA DE DATOS PARA CONTRATOS ---
    base_n = [0]*12
    if data_ins is not None:
        df_ins_filtered = data_ins[data_ins[col_fecha_ins].dt.year == año_seleccionado].copy()
        servicios_validos = ['CROSSELLING', 'INSTALACIÓN CÁMARA', 'INSTALACION ESPECIAL', 'INSTALACIÓN NUEVA', 'SMART HOME']
        mask_nuevos = (df_ins_filtered['SERVICIO A REALIZAR'].astype(str).str.strip().str.upper().isin(servicios_validos)) & (df_ins_filtered['ESTADO'].astype(str).str.strip().str.upper() == 'INSTALADO')
        df_ins_filtered['M_NUM'] = df_ins_filtered[col_fecha_ins].dt.month
        n_counts = df_ins_filtered[mask_nuevos]['M_NUM'].value_counts()
        for m, v in n_counts.items():
            if 1 <= m <= 12: base_n[int(m)-1] = int(v)

    if data_contratos is not None:
        if not data_contratos.empty:
            df_c_counts = data_contratos.groupby(data_contratos['FechaActivacionContrato'].dt.month).size().reset_index(name='Total Contratos')
            df_c_counts['Mes'] = df_c_counts['FechaActivacionContrato'].map({i+1: m for i, m in enumerate(meses_list)})
            df_final = pd.merge(pd.DataFrame({'Mes': meses_list}), df_c_counts[['Mes', 'Total Contratos']], on='Mes', how='left').fillna(0)
            df_final['Nuevos Contratos'] = base_n
            df_final['Neto_Abandono'] = s_n
            df_final['Churn Rate (%)'] = df_final.apply(lambda x: (x['Neto_Abandono'] / x['Total Contratos'] * 100) if x['Total Contratos'] > 0 else 0, axis=1)
            df_final['Acquisition Rate (%)'] = df_final.apply(lambda x: (x['Nuevos Contratos'] / x['Total Contratos'] * 100) if x['Total Contratos'] > 0 else 0, axis=1)
            df_final['NROD (%)'] = df_final['Acquisition Rate (%)'] - df_final['Churn Rate (%)']

            with tab3:
                st.header(f"📉 Análisis Trimestral de Tasas de Contratos ({año_seleccionado})")
                sel_tri_c = st.selectbox("Seleccionar Trimestre (Contratos):", ['T1', 'T2', 'T3', 'T4'])
                periodos_c = {'T1':['ENERO','FEBRERO','MARZO'], 'T2':['ABRIL','MAYO','JUNIO'], 'T3':['JULIO','AGOSTO','SEPTIEMBRE'], 'T4':['OCTUBRE','NOVIEMBRE','DICIEMBRE']}
                periodos_num = {'T1':[1,2,3], 'T2':[4,5,6], 'T3':[7,8,9], 'T4':[10,11,12]}
                
                df_tri_filtered = df_final[df_final['Mes'].isin(periodos_c[sel_tri_c])].copy()
                df_contratos_tri = data_contratos[data_contratos['FechaActivacionContrato'].dt.month.isin(periodos_num[sel_tri_c])].copy()

                fig_tri_evo_c = px.line(df_tri_filtered, x='Mes', y=['Churn Rate (%)', 'Acquisition Rate (%)', 'NROD (%)'], 
                                        title=f"Evolución {sel_tri_c}: Churn vs Acquisition vs NROD", markers=True,
                                        color_discrete_map={'Churn Rate (%)': '#EF553B', 'Acquisition Rate (%)': '#00CC96', 'NROD (%)': '#636EFA'})
                fig_tri_evo_c.update_traces(textposition="top center", texttemplate='%{y:.1f}%', mode='lines+markers+text')
                st.plotly_chart(fig_tri_evo_c, use_container_width=True)

                st.subheader(f"📋 Métricas Consolidadas")
                df_t_show_c = df_tri_filtered[['Mes', 'Total Contratos', 'Neto_Abandono', 'Churn Rate (%)']].copy()
                df_t_show_c['Churn Rate (%)'] = df_t_show_c['Churn Rate (%)'].map('{:.2f}%'.format)
                st.table(df_t_show_c.set_index('Mes').T)

                st.subheader(f"🎯 Acquisition Rate")
                df_acq_t_c = df_tri_filtered[['Mes', 'Nuevos Contratos', 'Total Contratos', 'Acquisition Rate (%)']].copy()
                df_acq_t_c['Acquisition Rate (%)'] = df_acq_t_c['Acquisition Rate (%)'].map('{:.2f}%'.format)
                st.table(df_acq_t_c.set_index('Mes').T)

                st.subheader(f"📈 NROD ")
                df_nrod_t_c = df_tri_filtered[['Mes', 'Acquisition Rate (%)', 'Churn Rate (%)', 'NROD (%)']].copy()
                for col in ['Acquisition Rate (%)', 'Churn Rate (%)', 'NROD (%)']: df_nrod_t_c[col] = df_nrod_t_c[col].map('{:.2f}%'.format)
                st.table(df_nrod_t_c.set_index('Mes').T)

                st.divider()
                st.subheader(f"📊 Distribución de Contratos en {sel_tri_c}")
                plot_contract_distribution(df_contratos_tri, 'Elementos', f"Planes Contratados ({sel_tri_c})", '#AB63FA')
                col_c1, col_c2 = st.columns(2)
                with col_c1: plot_contract_distribution(df_contratos_tri, 'NombreFormaPago', f"Forma de Pago ({sel_tri_c})", '#636EFA')
                with col_c2: plot_contract_distribution(df_contratos_tri, 'NombreZona', f"Zonas ({sel_tri_c})", '#00CC96')

            with tab4:
                st.header(f"📈 Reporte Mensual de Contratos ({año_seleccionado})")
                fig_evo = px.line(df_final, x='Mes', y=['Churn Rate (%)', 'Acquisition Rate (%)', 'NROD (%)'], 
                                        title="Evolución Mensual: Churn vs Acquisition vs NROD", markers=True,
                                        color_discrete_map={'Churn Rate (%)': '#EF553B', 'Acquisition Rate (%)': '#00CC96', 'NROD (%)': '#636EFA'})
                fig_evo.update_traces(textposition="top center", texttemplate='%{y:.1f}%', mode='lines+markers+text')
                st.plotly_chart(fig_evo, use_container_width=True)

                st.subheader("📋 Consolidadas de Contratos")
                df_m_show = df_final[['Mes', 'Total Contratos', 'Neto_Abandono', 'Churn Rate (%)']].copy()
                df_m_show['Churn Rate (%)'] = df_m_show['Churn Rate (%)'].map('{:.2f}%'.format)
                st.table(df_m_show.set_index('Mes').T)

                st.subheader("🎯 Acquisition Rate")
                df_acq = df_final[['Mes', 'Nuevos Contratos', 'Total Contratos', 'Acquisition Rate (%)']].copy()
                df_acq['Acquisition Rate (%)'] = df_acq['Acquisition Rate (%)'].map('{:.2f}%'.format)
                st.table(df_acq.set_index('Mes').T)

                st.subheader("📈 NROD")
                df_nrod_m = df_final[['Mes', 'Acquisition Rate (%)', 'Churn Rate (%)', 'NROD (%)']].copy()
                for col in ['Acquisition Rate (%)', 'Churn Rate (%)', 'NROD (%)']: df_nrod_m[col] = df_nrod_m[col].map('{:.2f}%'.format)
                st.table(df_nrod_m.set_index('Mes').T)
                
                st.divider()
                plot_contract_distribution(data_contratos, 'Elementos', "Planes Contratados (Anual)", '#AB63FA')
                col1, col2 = st.columns(2)
                with col1: plot_contract_distribution(data_contratos, 'NombreFormaPago', "Forma de Pago (Anual)", '#636EFA')
                with col2: plot_contract_distribution(data_contratos, 'NombreZona', "Zonas (Anual)", '#00CC96')

except Exception as e:
    st.error(f"Error detectado: {e}")