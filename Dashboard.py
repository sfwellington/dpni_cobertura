import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# Função para formatar números no padrão brasileiro
def formatar_numero_br(valor):
    """Formata número com separador de milhares no padrão brasileiro"""
    if pd.isna(valor):
        return "-"
    return f"{int(valor):,.0f}".replace(",", ".")

st.set_page_config(
    layout="wide",
    initial_sidebar_state="expanded"
)


st.title("Coberturas vacinais 💉")

# Adicionar CSS para bordas nas colunas
st.markdown("""
    <style>
    [data-testid="column"] {
        border: 2px solid #e0e0e0;
        padding: 15px;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# Carregar dados do arquivo ZIP
data = pd.read_csv("dados/residencia.zip", sep=';', compression='zip')

# Carregar tabela de estados
estados_df = pd.read_csv("dados/estados_brasil.csv", dtype=str)

# Carregar tabela de municípios
municipios_df = pd.read_csv("dados/municipio.csv", sep=';', dtype=str)

# Agrupar dados
colunas_agrupamento = ['TP_COBERTURA', 'DS_COBERTURA', 'CO_IBGE', 'NU_ANO', 'NU_MES', 'NU_IDADE']
# Verificar se todas as colunas existem
colunas_existentes = [col for col in colunas_agrupamento if col in data.columns]

if len(colunas_existentes) == len(colunas_agrupamento):
    # Encontrar uma coluna para contar que não esteja no agrupamento
    coluna_contagem = [col for col in data.columns if col not in colunas_agrupamento][0]
    
    # Contar registros por grupo e somar colunas numéricas
    agg_dict = {coluna_contagem: 'count'}
    agg_dict.update({col: 'sum' for col in data.select_dtypes(include=['number']).columns if col not in colunas_agrupamento})
    
    data_agrupado = data.groupby(colunas_agrupamento).agg(agg_dict).reset_index()
    data_agrupado.rename(columns={coluna_contagem: 'qt_registros'}, inplace=True)
    
    # Criar campos de região e UF a partir do código IBGE
    if 'CO_IBGE' in data_agrupado.columns:
        data_agrupado['CO_IBGE'] = data_agrupado['CO_IBGE'].astype(str)
        data_agrupado['CO_REGIAO'] = data_agrupado['CO_IBGE'].str[0]
        data_agrupado['CO_UF'] = data_agrupado['CO_IBGE'].str[:2].str.zfill(2)

        # Adicionar nome do município a partir do CSV de municípios
        if {'co_municipio_ibge', 'no_municipio'}.issubset(municipios_df.columns):
            municipios_df['co_municipio_ibge'] = municipios_df['co_municipio_ibge'].astype(str).str.zfill(6)
            data_agrupado['CO_IBGE'] = data_agrupado['CO_IBGE'].str.zfill(6)
            data_agrupado = data_agrupado.merge(
                municipios_df[['co_municipio_ibge', 'no_municipio']],
                left_on='CO_IBGE',
                right_on='co_municipio_ibge',
                how='left'
            ).drop(columns=['co_municipio_ibge'])

        # Adicionar nome e sigla da UF a partir do CSV de estados
        if {'co_uf', 'no_uf', 'sg_uf'}.issubset(estados_df.columns):
            estados_df['co_uf'] = estados_df['co_uf'].astype(str).str.zfill(2)
            data_agrupado = data_agrupado.merge(
                estados_df[['co_uf', 'no_uf', 'sg_uf']],
                left_on='CO_UF',
                right_on='co_uf',
                how='left'
            ).drop(columns=['co_uf'])
        
        # Mapear código de região para nome da região
        mapa_regiao = {
            '1': 'Norte',
            '2': 'Nordeste',
            '3': 'Sudeste',
            '4': 'Sul',
            '5': 'Centro-Oeste'
        }
        data_agrupado['REGIAO'] = data_agrupado['CO_REGIAO'].map(mapa_regiao)
else:
    data_agrupado = data
    st.warning(f"Colunas de agrupamento não encontradas. Colunas disponíveis: {data.columns.tolist()}")

st.sidebar.title("Filtros")
# Filtro de ano
if 'NU_ANO' in data_agrupado.columns:
    anos_disponiveis = sorted(data_agrupado['NU_ANO'].unique())
    ano_selecionado = st.sidebar.selectbox("Selecione o Ano", anos_disponiveis, index=anos_disponiveis.index(2025) if 2025 in anos_disponiveis else 0)
    # Guardar cópia antes de filtrar por ano (para usar no gráfico de evolução mensal)
    data_todos_anos = data_agrupado.copy()
    data_agrupado = data_agrupado[data_agrupado['NU_ANO'] == ano_selecionado]
    
# Filtro de dados geográficos
with st.sidebar.expander("Dados Geográficos", expanded=True):
    # Filtro de região
    if 'REGIAO' in data_agrupado.columns:
        ordem_regioes = ['Norte', 'Nordeste', 'Sudeste', 'Sul', 'Centro-Oeste']
        regioes_validas = [r for r in data_agrupado['REGIAO'].unique() if pd.notna(r)]
        regioes_ordenadas = [r for r in ordem_regioes if r in regioes_validas]
        regioes_disponiveis = ['Todas'] + regioes_ordenadas
        regiao_selecionada = st.selectbox("Região", regioes_disponiveis)
        if regiao_selecionada != 'Todas':
            data_agrupado = data_agrupado[data_agrupado['REGIAO'] == regiao_selecionada]

    # Filtro de estado (UF)
    if 'sg_uf' in data_agrupado.columns:
        ufs_disponiveis = ['Todos'] + sorted([uf for uf in data_agrupado['sg_uf'].unique() if pd.notna(uf)])
        uf_selecionado = st.selectbox("Estado (UF)", ufs_disponiveis)
        if uf_selecionado != 'Todos':
            data_agrupado = data_agrupado[data_agrupado['sg_uf'] == uf_selecionado]

    # Filtro de município
    if 'no_municipio' in data_agrupado.columns:
        municipios_disponiveis = ['Todos'] + sorted([m for m in data_agrupado['no_municipio'].unique() if pd.notna(m)])
        municipio_selecionado = st.selectbox("Município", municipios_disponiveis)
        if municipio_selecionado != 'Todos':
            data_agrupado = data_agrupado[data_agrupado['no_municipio'] == municipio_selecionado]

# Filtro de descrição de cobertura
if 'DS_COBERTURA' in data_agrupado.columns:
    descricoes_cobertura = ['Todos'] + sorted(data_agrupado['DS_COBERTURA'].unique().tolist())
    descricao_selecionada = st.sidebar.selectbox("Descrição da Cobertura", descricoes_cobertura)
    if descricao_selecionada != 'Todos':
        data_agrupado = data_agrupado[data_agrupado['DS_COBERTURA'] == descricao_selecionada]
else:
    descricao_selecionada = 'Todos'

# Definir variáveis para uso no texto de filtros
tipo_selecionado = 'Todos'
idade_selecionada = 'Todas'


## Visualização no streamlit

# Criar texto com filtros selecionados
filtros_texto = []
if 'NU_ANO' in data_agrupado.columns:
    filtros_texto.append(f"Ano: {ano_selecionado}")
if 'REGIAO' in data_agrupado.columns and regiao_selecionada != 'Todas':
    filtros_texto.append(f"Região: {regiao_selecionada}")
if 'sg_uf' in data_agrupado.columns and uf_selecionado != 'Todos':
    filtros_texto.append(f"UF: {uf_selecionado}")
if 'no_municipio' in data_agrupado.columns and municipio_selecionado != 'Todos':
    filtros_texto.append(f"Município: {municipio_selecionado}")
if 'TP_COBERTURA' in data_agrupado.columns and tipo_selecionado != 'Todos':
    filtros_texto.append(f"Tipo: {tipo_selecionado}")
if 'DS_COBERTURA' in data_agrupado.columns and descricao_selecionada != 'Todos':
    filtros_texto.append(f"Cobertura: {descricao_selecionada}")
if 'NU_IDADE' in data_agrupado.columns and idade_selecionada != 'Todas':
    filtros_texto.append(f"Idade: {idade_selecionada}")

filtros_str = " | ".join(filtros_texto) if filtros_texto else "Todos os dados"

aba1, aba2, aba3, aba4 = st.tabs(["Coberturas Vacinais", "Mapa", "Tabelas", "Dashboards"])
with aba1:
    st.header(f"Análise de Coberturas Vacinais")
    st.subheader(f"📊 Filtros: {filtros_str}")
    
    # Obter lista de coberturas disponíveis
    coberturas_disponiveis = sorted(data_agrupado['DS_COBERTURA'].unique().tolist())
    
    # Criar objeto de coberturas com metas
    coberturas_com_meta = []
    for cobertura in coberturas_disponiveis:
        if cobertura in   ['BCG','Rotavírus']:
            coberturas_com_meta.append({
                'nome': cobertura,
                'meta': 90.0,  # Meta específica para BCG e Rotavírus
                'cor_muito_critico': '#790E18',  # Rubi: 0-20%
                'cor_critico': '#ff4444',  # Vermelho: 21-40%
                'cor_baixo': '#ff9900',    # Laranja: 41-60%
                'cor_moderado': '#ffdd00', # Amarelo: 61-80%
                'cor_excelente': '#44dd44', # Verde: >80%
                'cor_otima': '#000099'     # Azul: Meta ótima (90%)
            })      
        elif cobertura in   ['Hepatite B (< 30 dias)',  'Hepatite B',   'Hepatite A Infantil',  
                             'DTP', 'Febre Amarela', 'Polio Injetável (VIP)', 
                             'Pneumo 10', 'Meningo C', 'Penta (DTP/HepB/Hib)', 
                             'COVID', 'DTP (1° Reforço)', 
                             'Tríplice Viral - 1° Dose', 'Tríplice Viral - 2° Dose', 
                             'Pneumo 10 (1° Reforço)', 'Polio Injetável (VIP)(Reforço)', 
                             'Varicela', 'Meningocócica Conjugada (1° Reforço)',
                             'dTpa Adulto - Gestantes']:
            coberturas_com_meta.append({
                'nome': cobertura,
                'meta': 95.0,  # Meta padrão de 95% para todas as coberturas
                'cor_muito_critico': '#790E18',  # Rubi: 0-20%
                'cor_critico': '#ff4444',  # Vermelho: 21-40%
                'cor_baixo': '#ff9900',    # Laranja: 41-60%
                'cor_moderado': '#ffdd00', # Amarelo: 61-80%
                'cor_excelente': '#44dd44', # Verde: >80%
                'cor_otima': '#000099'     # Azul: Meta ótima (95%)
            })
        
    # Função helper para buscar cobertura exata na lista
    def buscar_cobertura(lista_coberturas, nome_procurado):
        return nome_procurado if nome_procurado in lista_coberturas else None
    
    # Função para buscar meta de uma cobertura
    def get_meta_cobertura(nome_cobertura):
        meta_info = next((item for item in coberturas_com_meta if item['nome'] == nome_cobertura), None)
        return meta_info['meta'] if meta_info else 95.0
    
    # Função para buscar meta e determinar cor baseada na meta específica
    def get_cor_por_meta(nome_cobertura, percentual):
        # Buscar a meta específica da cobertura
        meta_info = next((item for item in coberturas_com_meta if item['nome'] == nome_cobertura), None)
        
        if meta_info:
            meta = meta_info['meta']
            if percentual <= 20:
                return meta_info['cor_muito_critico']
            elif percentual <= 40:
                return meta_info['cor_critico']
            elif percentual <= 60:
                return meta_info['cor_baixo']
            elif percentual <= 80:
                return meta_info['cor_moderado']
            elif percentual >= meta:
                return meta_info['cor_otima']  # Azul quando atinge a meta
            else:
                return meta_info['cor_excelente']
        else:
            # Cores padrão se não encontrar a meta
            if percentual <= 20:
                return "#790E18"
            elif percentual <= 40:
                return "#ff4444"
            elif percentual <= 60:
                return "#ff9900"
            elif percentual <= 80:
                return "#ffdd00"
            elif percentual >= 95:
                return "#000099"
            else:
                return "#44dd44"
    
    # Função para criar gráfico de cobertura por estado
    def criar_grafico_cobertura_estado(df, nome_cobertura, meta):
        # Filtrar dados para a cobertura específica
        df_cobertura = df[df['DS_COBERTURA'] == nome_cobertura]
        
        if len(df_cobertura) == 0:
            return None
        
        # Agrupar por estado e calcular cobertura
        df_por_estado = df_cobertura.groupby('sg_uf').agg({
            'QT_DOSES': 'sum',
            'QT_POPULACAO': 'sum'
        }).reset_index()
        
        # Calcular percentual de cobertura
        df_por_estado['COBERTURA'] = (df_por_estado['QT_DOSES'] / df_por_estado['QT_POPULACAO']) * 100
        
        # Ordenar por cobertura decrescente
        df_por_estado = df_por_estado.sort_values('COBERTURA', ascending=True)
        
        # Criar o gráfico de barras
        fig = px.bar(
            df_por_estado,
            x='COBERTURA',
            y='sg_uf',
            orientation='h',
            title=f'Cobertura de {nome_cobertura} por Estado',
            labels={'COBERTURA': 'Cobertura (%)', 'sg_uf': 'Estado'},
            color='COBERTURA',
            color_continuous_scale=[
                [0, '#790E18'],    # Rubi (0%)
                [0.2, '#ff4444'],  # Vermelho (20%)
                [0.4, '#ff9900'],  # Laranja (40%)
                [0.6, '#ffdd00'],  # Amarelo (60%)
                [0.8, '#44dd44'],  # Verde (80%)
                [1, '#000099']     # Azul (100%/meta)
            ],
            range_color=[0, 100]
        )
        
        # Adicionar linha vertical da meta
        fig.add_vline(
            x=meta,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Meta: {meta:.1f}%",
            annotation_position="top right"
        )
        
        # Ajustar layout
        fig.update_layout(
            height=400,
            showlegend=False,
            xaxis=dict(range=[0, 110]),
            coloraxis_showscale=False
        )
        
        return fig
    
    # Expander 1: Ao nascer
    with st.expander("Ao Nascer", expanded=True):
        # Função para calcular cobertura
        def calcular_cobertura(df, cobertura):
            df_cobertura = df[df['DS_COBERTURA'] == cobertura]
            if len(df_cobertura) > 0:
                soma_doses = df_cobertura['QT_DOSES'].sum() if 'QT_DOSES' in df_cobertura.columns else 0
                soma_populacao = df_cobertura['QT_POPULACAO'].sum() if 'QT_POPULACAO' in df_cobertura.columns else 1
                if soma_populacao > 0:
                    return (soma_doses / soma_populacao) * 100
            return 0
        
        # Função para determinar cor baseada no percentual
        def get_cor_card(percentual):
            if percentual <= 20:
                return "#790E18"  # Rubi
            elif percentual <= 40:
                return "#ff4444"  # Vermelho
            elif percentual <= 60:
                return "#ff9900"  # Laranja
            elif percentual <= 80:
                return "#ffdd00"  # Amarelo
            elif percentual >= 95:
                return "#000099"  # Azul (meta ótima)
            else:
                return "#44dd44"  # Verde
        
        # Definir as coberturas buscando da lista disponível
        cobertura_bcg_nome = buscar_cobertura(coberturas_disponiveis, 'BCG')
        cobertura_hb30_nome = buscar_cobertura(coberturas_disponiveis, 'Hepatite B (< 30 dias)')
        
        # Calcular coberturas
        cobertura_bcg = calcular_cobertura(data_agrupado, cobertura_bcg_nome)
        cobertura_hb30 = calcular_cobertura(data_agrupado, cobertura_hb30_nome)
        
        # Criar cards centralizados
        col1, col2, col3, col4 = st.columns(4)
        
        with col2:
            cor_bcg = get_cor_por_meta(cobertura_bcg_nome, cobertura_bcg)
            meta_bcg = get_meta_cobertura(cobertura_bcg_nome)
            hint_bcg = f"A meta ótima de cobertura dessa vacina é de {f'{meta_bcg:.1f}'.replace('.', ',')}%\n{cobertura_bcg_nome}: {f'{cobertura_bcg:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_bcg}" style='background-color: {cor_bcg}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_bcg_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_bcg:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col3:
            cor_hb30 = get_cor_por_meta(cobertura_hb30_nome, cobertura_hb30)
            meta_hb30 = get_meta_cobertura(cobertura_hb30_nome)
            hint_hb30 = f"A meta ótima de cobertura dessa vacina é de {f'{meta_hb30:.1f}'.replace('.', ',')}%\n{cobertura_hb30_nome}: {f'{cobertura_hb30:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_hb30}" style='background-color: {cor_hb30}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_hb30_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_hb30:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)
    
        st.write("")
        
    # Expander 2: Menores de 1 ano de idade
    with st.expander("Menores de 1 Ano de Idade", expanded=True):
        # Função para calcular cobertura
        def calcular_cobertura(df, cobertura):
            df_cobertura = df[df['DS_COBERTURA'] == cobertura]
            if len(df_cobertura) > 0:
                soma_doses = df_cobertura['QT_DOSES'].sum() if 'QT_DOSES' in df_cobertura.columns else 0
                soma_populacao = df_cobertura['QT_POPULACAO'].sum() if 'QT_POPULACAO' in df_cobertura.columns else 1
                if soma_populacao > 0:
                    return (soma_doses / soma_populacao) * 100
            return 0
        
        # Função para determinar cor baseada no percentual
        def get_cor_card_menor1(percentual):
            if percentual <= 40:
                return "#ff4444"  # Vermelho
            elif percentual <= 70:
                return "#ff9900"  # Laranja
            elif percentual <= 95:
                return "#ffdd00"  # Amarelo
            else:
                return "#44dd44"  # Verde
        
        # Definir as coberturas buscando da lista disponível
        cobertura_fa_nome = buscar_cobertura(coberturas_disponiveis, 'Febre Amarela')
        cobertura_vip_nome = buscar_cobertura(coberturas_disponiveis, 'Polio Injetável (VIP)')
        cobertura_pneumo_nome = buscar_cobertura(coberturas_disponiveis, 'Pneumo 10')
        cobertura_meningo_nome = buscar_cobertura(coberturas_disponiveis, 'Meningo C')
        cobertura_penta_nome = buscar_cobertura(coberturas_disponiveis, 'Penta (DTP/HepB/Hib)')
        cobertura_rota_nome = buscar_cobertura(coberturas_disponiveis, 'Rotavírus')

        
        # Calcular coberturas
        cobertura_fa = calcular_cobertura(data_agrupado, cobertura_fa_nome)
        cobertura_vip = calcular_cobertura(data_agrupado, cobertura_vip_nome)
        cobertura_pneumo = calcular_cobertura(data_agrupado, cobertura_pneumo_nome)
        cobertura_meningo = calcular_cobertura(data_agrupado, cobertura_meningo_nome)
        cobertura_penta = calcular_cobertura(data_agrupado, cobertura_penta_nome)
        cobertura_rota = calcular_cobertura(data_agrupado, cobertura_rota_nome)

        
        # Linha 1: 4 colunas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            cor_fa = get_cor_por_meta(cobertura_fa_nome, cobertura_fa)
            meta_fa = get_meta_cobertura(cobertura_fa_nome)
            hint_fa = f"A meta ótima de cobertura dessa vacina é de {f'{meta_fa:.1f}'.replace('.', ',')}%\n{cobertura_fa_nome}: {f'{cobertura_fa:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_fa}" style='background-color: {cor_fa}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_fa_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_fa:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)

        with col2:
            cor_vip = get_cor_por_meta(cobertura_vip_nome, cobertura_vip)
            meta_vip = get_meta_cobertura(cobertura_vip_nome)
            hint_vip = f"A meta ótima de cobertura dessa vacina é de {f'{meta_vip:.1f}'.replace('.', ',')}%\n{cobertura_vip_nome}: {f'{cobertura_vip:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_vip}" style='background-color: {cor_vip}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_vip_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_vip:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)        
        with col3:
            cor_pneumo = get_cor_por_meta(cobertura_pneumo_nome, cobertura_pneumo)
            meta_pneumo = get_meta_cobertura(cobertura_pneumo_nome)
            hint_pneumo = f"A meta ótima de cobertura dessa vacina é de {f'{meta_pneumo:.1f}'.replace('.', ',')}%\n{cobertura_pneumo_nome}: {f'{cobertura_pneumo:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_pneumo}" style='background-color: {cor_pneumo}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_pneumo_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_pneumo:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)
       
        with col4:
            cor_meningo = get_cor_por_meta(cobertura_meningo_nome, cobertura_meningo)
            meta_meningo = get_meta_cobertura(cobertura_meningo_nome)
            hint_meningo = f"A meta ótima de cobertura dessa vacina é de {f'{meta_meningo:.1f}'.replace('.', ',')}%\n{cobertura_meningo_nome}: {f'{cobertura_meningo:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_meningo}" style='background-color: {cor_meningo}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_meningo_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_meningo:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)

        st.write("")
        # Linha 2: 4 colunas
        col5, col6, col7, col8 = st.columns(4)
        
        with col6:
            cor_penta = get_cor_por_meta(cobertura_penta_nome, cobertura_penta)
            meta_penta = get_meta_cobertura(cobertura_penta_nome)
            hint_penta = f"A meta ótima de cobertura dessa vacina é de {f'{meta_penta:.1f}'.replace('.', ',')}%\n{cobertura_penta_nome}: {f'{cobertura_penta:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_penta}" style='background-color: {cor_penta}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_penta_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_penta:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col7:
            cor_rota = get_cor_por_meta(cobertura_rota_nome, cobertura_rota)
            meta_rota = get_meta_cobertura(cobertura_rota_nome)
            hint_rota = f"A meta ótima de cobertura dessa vacina é de {f'{meta_rota:.1f}'.replace('.', ',')}%\n{cobertura_rota_nome}: {f'{cobertura_rota:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_rota}" style='background-color: {cor_rota}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_rota_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_rota:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)
            
        st.write("")
    
    # Expander 3: 1 ano de idade
    with st.expander("1 Ano de Idade", expanded=True):
        # Função para calcular cobertura
        def calcular_cobertura_1ano(df, cobertura):
            df_cobertura = df[df['DS_COBERTURA'] == cobertura]
            if len(df_cobertura) > 0:
                soma_doses = df_cobertura['QT_DOSES'].sum() if 'QT_DOSES' in df_cobertura.columns else 0
                soma_populacao = df_cobertura['QT_POPULACAO'].sum() if 'QT_POPULACAO' in df_cobertura.columns else 1
                if soma_populacao > 0:
                    return (soma_doses / soma_populacao) * 100
            return 0
        
        # Função para determinar cor baseada no percentual
        def get_cor_card_1ano(percentual):
            if percentual <= 40:
                return "#ff4444"  # Vermelho
            elif percentual <= 70:
                return "#ff9900"  # Laranja
            elif percentual <= 95:
                return "#ffdd00"  # Amarelo
            else:
                return "#44dd44"  # Verde
        
        # Definir as coberturas buscando da lista disponível
        cobertura_hepa_nome = buscar_cobertura(coberturas_disponiveis, 'Hepatite A Infantil')
        cobertura_dtp_ref_nome = buscar_cobertura(coberturas_disponiveis, 'DTP (1° Reforço)')
        cobertura_triplice1_nome = buscar_cobertura(coberturas_disponiveis, 'Tríplice Viral - 1° Dose')
        cobertura_triplice2_nome = buscar_cobertura(coberturas_disponiveis, 'Tríplice Viral - 2° Dose')
        cobertura_pneumo_ref_nome = buscar_cobertura(coberturas_disponiveis, 'Pneumo 10 (1° Reforço)')
        cobertura_vip_ref_nome = buscar_cobertura(coberturas_disponiveis, 'Polio Injetável (VIP)(Reforço)')
        cobertura_varicela_nome = buscar_cobertura(coberturas_disponiveis, 'Varicela')
        cobertura_meningo_ref_nome = buscar_cobertura(coberturas_disponiveis, 'Meningocócica Conjugada (1° Reforço)')
        
        # Calcular coberturas
        cobertura_hepa = calcular_cobertura_1ano(data_agrupado, cobertura_hepa_nome)
        cobertura_dtp_ref = calcular_cobertura_1ano(data_agrupado, cobertura_dtp_ref_nome)
        cobertura_triplice1 = calcular_cobertura_1ano(data_agrupado, cobertura_triplice1_nome)
        cobertura_triplice2 = calcular_cobertura_1ano(data_agrupado, cobertura_triplice2_nome)
        cobertura_pneumo_ref = calcular_cobertura_1ano(data_agrupado, cobertura_pneumo_ref_nome)
        cobertura_vip_ref = calcular_cobertura_1ano(data_agrupado, cobertura_vip_ref_nome)
        cobertura_varicela = calcular_cobertura_1ano(data_agrupado, cobertura_varicela_nome)
        cobertura_meningo_ref = calcular_cobertura_1ano(data_agrupado, cobertura_meningo_ref_nome)
        
        # Linha 1: 4 colunas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            cor_hepa = get_cor_por_meta(cobertura_hepa_nome, cobertura_hepa)
            meta_hepa = get_meta_cobertura(cobertura_hepa_nome)
            hint_hepa = f"A meta ótima de cobertura dessa vacina é de {f'{meta_hepa:.1f}'.replace('.', ',')}%\n{cobertura_hepa_nome}: {f'{cobertura_hepa:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_hepa}" style='background-color: {cor_hepa}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_hepa_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_hepa:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col2:
            cor_dtp_ref = get_cor_por_meta(cobertura_dtp_ref_nome, cobertura_dtp_ref)
            meta_dtp_ref = get_meta_cobertura(cobertura_dtp_ref_nome)
            hint_dtp_ref = f"A meta ótima de cobertura dessa vacina é de {f'{meta_dtp_ref:.1f}'.replace('.', ',')}%\n{cobertura_dtp_ref_nome}: {f'{cobertura_dtp_ref:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_dtp_ref}" style='background-color: {cor_dtp_ref}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_dtp_ref_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_dtp_ref:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col3:
            cor_triplice1 = get_cor_por_meta(cobertura_triplice1_nome, cobertura_triplice1)
            meta_triplice1 = get_meta_cobertura(cobertura_triplice1_nome)
            hint_triplice1 = f"A meta ótima de cobertura dessa vacina é de {f'{meta_triplice1:.1f}'.replace('.', ',')}%\n{cobertura_triplice1_nome}: {f'{cobertura_triplice1:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_triplice1}" style='background-color: {cor_triplice1}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_triplice1_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_triplice1:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col4:
            cor_triplice2 = get_cor_por_meta(cobertura_triplice2_nome, cobertura_triplice2)
            meta_triplice2 = get_meta_cobertura(cobertura_triplice2_nome)
            hint_triplice2 = f"A meta ótima de cobertura dessa vacina é de {f'{meta_triplice2:.1f}'.replace('.', ',')}%\n{cobertura_triplice2_nome}: {f'{cobertura_triplice2:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_triplice2}" style='background-color: {cor_triplice2}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_triplice2_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_triplice2:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)
        st.write("")
        # Linha 2: 4 colunas
        col5, col6, col7, col8 = st.columns(4)
        
        with col5:
            cor_pneumo_ref = get_cor_por_meta(cobertura_pneumo_ref_nome, cobertura_pneumo_ref)
            meta_pneumo_ref = get_meta_cobertura(cobertura_pneumo_ref_nome)
            hint_pneumo_ref = f"A meta ótima de cobertura dessa vacina é de {f'{meta_pneumo_ref:.1f}'.replace('.', ',')}%\n{cobertura_pneumo_ref_nome}: {f'{cobertura_pneumo_ref:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_pneumo_ref}" style='background-color: {cor_pneumo_ref}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_pneumo_ref_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_pneumo_ref:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col6:
            cor_vip_ref = get_cor_por_meta(cobertura_vip_ref_nome, cobertura_vip_ref)
            meta_vip_ref = get_meta_cobertura(cobertura_vip_ref_nome)
            hint_vip_ref = f"A meta ótima de cobertura dessa vacina é de {f'{meta_vip_ref:.1f}'.replace('.', ',')}%\n{cobertura_vip_ref_nome}: {f'{cobertura_vip_ref:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_vip_ref}" style='background-color: {cor_vip_ref}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_vip_ref_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_vip_ref:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col7:
            cor_varicela = get_cor_por_meta(cobertura_varicela_nome, cobertura_varicela)
            meta_varicela = get_meta_cobertura(cobertura_varicela_nome)
            hint_varicela = f"A meta ótima de cobertura dessa vacina é de {f'{meta_varicela:.1f}'.replace('.', ',')}%\n{cobertura_varicela_nome}: {f'{cobertura_varicela:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_varicela}" style='background-color: {cor_varicela}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_varicela_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_varicela:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col8:
            cor_meningo_ref = get_cor_por_meta(cobertura_meningo_ref_nome, cobertura_meningo_ref)
            meta_meningo_ref = get_meta_cobertura(cobertura_meningo_ref_nome)
            hint_meningo_ref = f"A meta ótima de cobertura dessa vacina é de {f'{meta_meningo_ref:.1f}'.replace('.', ',')}%\n{cobertura_meningo_ref_nome}: {f'{cobertura_meningo_ref:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_meningo_ref}" style='background-color: {cor_meningo_ref}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_meningo_ref_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_meningo_ref:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)
        
        st.write("")

    
    # Expander 4: Adulto
    with st.expander("Adulto", expanded=True):
        # Função para calcular cobertura
        def calcular_cobertura_adulto(df, cobertura):
            df_cobertura = df[df['DS_COBERTURA'] == cobertura]
            if len(df_cobertura) > 0:
                soma_doses = df_cobertura['QT_DOSES'].sum() if 'QT_DOSES' in df_cobertura.columns else 0
                soma_populacao = df_cobertura['QT_POPULACAO'].sum() if 'QT_POPULACAO' in df_cobertura.columns else 1
                if soma_populacao > 0:
                    return (soma_doses / soma_populacao) * 100
            return 0
        
        # Função para determinar cor baseada no percentual
        def get_cor_card_adulto(percentual):
            if percentual <= 40:
                return "#ff4444"  # Vermelho
            elif percentual <= 70:
                return "#ff9900"  # Laranja
            elif percentual <= 95:
                return "#ffdd00"  # Amarelo
            else:
                return "#44dd44"  # Verde
        
        # Definir as coberturas buscando da lista disponível
        cobertura_dtpa_nome = buscar_cobertura(coberturas_disponiveis, 'dTpa Adulto - Gestantes')
        
        # Calcular coberturas
        cobertura_dtpa = calcular_cobertura_adulto(data_agrupado, cobertura_dtpa_nome)
        
        # Criar card centralizado
        col_esq, col_centro, col_dir = st.columns([1.5, 1, 1.5])
        
        with col_centro:
            cor_dtpa = get_cor_por_meta(cobertura_dtpa_nome, cobertura_dtpa)
            meta_dtpa = get_meta_cobertura(cobertura_dtpa_nome)
            hint_dtpa = f"A meta ótima de cobertura dessa vacina é de {f'{meta_dtpa:.1f}'.replace('.', ',')}%\n{cobertura_dtpa_nome}: {f'{cobertura_dtpa:.2f}'.replace('.', ',')}%"
            st.markdown(f"""
                <div title="{hint_dtpa}" style='background-color: {cor_dtpa}; padding: 12px; border-radius: 8px; text-align: center; cursor: help;'>
                    <h4 style='color: white; margin: 0; font-size: 13px;'>{cobertura_dtpa_nome}</h4>
                    <p style='color: white; font-size: 20px; font-weight: bold; margin: 6px 0;'>{f'{cobertura_dtpa:.2f}'.replace('.', ',')}%</p>
                </div>
            """, unsafe_allow_html=True)
        
        st.write("")
    
    # Legenda de cores
    st.markdown("---")
    st.subheader("Legenda de Cobertura")
    col_leg1, col_leg2, col_leg3, col_leg4, col_leg5, col_leg6 = st.columns(6)
    
    with col_leg1:
        st.markdown("""
            <div style='background-color: #790E18; padding: 15px; border-radius: 8px; text-align: center;'>
                <p style='color: white; font-weight: bold; margin: 0;'>0 - 20%</p>
                <p style='color: white; font-size: 12px; margin: 5px 0;'>Muito Crítico</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col_leg2:
        st.markdown("""
            <div style='background-color: #ff4444; padding: 15px; border-radius: 8px; text-align: center;'>
                <p style='color: white; font-weight: bold; margin: 0;'>21 - 40%</p>
                <p style='color: white; font-size: 12px; margin: 5px 0;'>Crítico</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col_leg3:
        st.markdown("""
            <div style='background-color: #ff9900; padding: 15px; border-radius: 8px; text-align: center;'>
                <p style='color: white; font-weight: bold; margin: 0;'>41 - 60%</p>
                <p style='color: white; font-size: 12px; margin: 5px 0;'>Baixo</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col_leg4:
        st.markdown("""
            <div style='background-color: #ffdd00; padding: 15px; border-radius: 8px; text-align: center;'>
                <p style='color: black; font-weight: bold; margin: 0;'>61 - 80%</p>
                <p style='color: black; font-size: 12px; margin: 5px 0;'>Moderado</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col_leg5:
        st.markdown("""
            <div style='background-color: #44dd44; padding: 15px; border-radius: 8px; text-align: center;'>
                <p style='color: white; font-weight: bold; margin: 0;'>> 80%</p>
                <p style='color: white; font-size: 12px; margin: 5px 0;'>Excelente</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col_leg6:
        st.markdown("""
            <div style='background-color: #000099; padding: 15px; border-radius: 8px; text-align: center;'>
                <p style='color: white; font-weight: bold; margin: 0;'>Meta Ótima</p>
                <p style='color: white; font-size: 12px; margin: 5px 0;'>≥ 90% ou 95%</p>
            </div>
        """, unsafe_allow_html=True)

with aba2:
    st.header("Mapa de Cobertura Vacinal por Estado")
    st.subheader(f"📊 Filtros: {filtros_str}")
    
    # Seleção de vacina para visualizar no mapa
    if 'DS_COBERTURA' in data_agrupado.columns:
        coberturas_para_mapa = sorted(data_agrupado['DS_COBERTURA'].unique().tolist())
        cobertura_selecionada_mapa = st.selectbox("Selecione a vacina para visualizar no mapa:", coberturas_para_mapa)
        
        # Filtrar dados para a cobertura selecionada
        df_mapa = data_agrupado[data_agrupado['DS_COBERTURA'] == cobertura_selecionada_mapa].copy()
        
        if len(df_mapa) > 0 and 'sg_uf' in df_mapa.columns:
            # Agrupar por estado
            df_por_uf = df_mapa.groupby('sg_uf').agg({
                'QT_DOSES': 'sum',
                'QT_POPULACAO': 'sum'
            }).reset_index()
            
            # Calcular cobertura
            df_por_uf['COBERTURA'] = (df_por_uf['QT_DOSES'] / df_por_uf['QT_POPULACAO']) * 100
            df_por_uf['COBERTURA'] = df_por_uf['COBERTURA'].round(2)
            
            # Adicionar nome completo do estado
            if 'sg_uf' in estados_df.columns:
                df_por_uf = df_por_uf.merge(
                    estados_df[['sg_uf', 'no_uf']],
                    on='sg_uf',
                    how='left'
                )
            
            # Buscar a meta da cobertura selecionada
            meta_mapa = get_meta_cobertura(cobertura_selecionada_mapa)
            
            # Criar mapa coroplético do Brasil
            fig_mapa = px.choropleth(
                df_por_uf,
                locations='sg_uf',
                locationmode='geojson-id',
                color='COBERTURA',
                hover_name='no_uf' if 'no_uf' in df_por_uf.columns else 'sg_uf',
                hover_data={
                    'COBERTURA': ':.2f',
                    'QT_DOSES': ':,.0f',
                    'QT_POPULACAO': ':,.0f',
                    'sg_uf': False
                },
                labels={
                    'COBERTURA': 'Cobertura (%)',
                    'QT_DOSES': 'Doses Aplicadas',
                    'QT_POPULACAO': 'População'
                },
                color_continuous_scale=[
                    [0, '#790E18'],      # Rubi (0%)
                    [0.2, '#ff4444'],    # Vermelho (20%)
                    [0.4, '#ff9900'],    # Laranja (40%)
                    [0.6, '#ffdd00'],    # Amarelo (60%)
                    [0.8, '#44dd44'],    # Verde (80%)
                    [meta_mapa/100, '#000099'],  # Azul (meta)
                    [1, '#000099']       # Azul (100%)
                ],
                range_color=[0, 110],
                geojson="https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson",
                featureidkey="properties.sigla",
                title=f"Cobertura de {cobertura_selecionada_mapa} por Estado - Meta: {meta_mapa:.1f}%"
            )
            
            fig_mapa.update_geos(
                fitbounds="locations",
                visible=False
            )
            
            fig_mapa.update_layout(
                height=600,
                margin={"r":0,"t":50,"l":0,"b":0}
            )
            
            st.plotly_chart(fig_mapa, width='stretch')
            
            # Adicionar tabela com dados por estado
            st.subheader("Dados por Estado")
            df_tabela_mapa = df_por_uf.copy()
            if 'no_uf' in df_tabela_mapa.columns:
                df_tabela_mapa = df_tabela_mapa[['sg_uf', 'no_uf', 'COBERTURA', 'QT_DOSES', 'QT_POPULACAO']]
                df_tabela_mapa.columns = ['UF', 'Estado', 'Cobertura (%)', 'Doses Aplicadas', 'População']
            else:
                df_tabela_mapa = df_tabela_mapa[['sg_uf', 'COBERTURA', 'QT_DOSES', 'QT_POPULACAO']]
                df_tabela_mapa.columns = ['UF', 'Cobertura (%)', 'Doses Aplicadas', 'População']
            
            df_tabela_mapa = df_tabela_mapa.sort_values('Cobertura (%)', ascending=False)
            st.dataframe(df_tabela_mapa, width='stretch', hide_index=True)
            
        else:
            st.warning("Não há dados disponíveis para a cobertura selecionada com os filtros aplicados.")
    else:
        st.warning("Coluna DS_COBERTURA não encontrada nos dados.")

with aba3:
    st.header("Tabelas de Dados")
    st.subheader(f"📊 Filtros: {filtros_str}")
    
    # Configuração da paginação
    linhas_por_pagina = st.selectbox("Linhas por página", [10, 25, 50, 100, 500], index=2)
    total_paginas = (len(data_agrupado) - 1) // linhas_por_pagina + 1

    # Ajustar página atual quando total de páginas diminuir
    if "pagina_atual" not in st.session_state:
        st.session_state.pagina_atual = 1
    if st.session_state.pagina_atual > total_paginas:
        st.session_state.pagina_atual = total_paginas
    
    # Controles de navegação
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("⬅️ Anterior", disabled=("pagina_atual" not in st.session_state or st.session_state.pagina_atual == 1)):
            st.session_state.pagina_atual -= 1
            st.rerun()
    
    with col2:
        pagina_atual = st.number_input(
            "Página", 
            min_value=1, 
            max_value=total_paginas, 
            value=st.session_state.get("pagina_atual", 1),
            key="input_pagina"
        )
        if pagina_atual != st.session_state.get("pagina_atual", 1):
            st.session_state.pagina_atual = pagina_atual
            st.rerun()
        
        st.write(f"Total: {total_paginas} páginas ({len(data_agrupado):,} registros)")
    
    with col3:
        if st.button("Próxima ➡️", disabled=("pagina_atual" not in st.session_state or st.session_state.pagina_atual == total_paginas)):
            st.session_state.pagina_atual += 1
            st.rerun()
    
    # Calcular índices da página atual
    inicio = (st.session_state.pagina_atual - 1) * linhas_por_pagina
    fim = inicio + linhas_por_pagina
    
    # Exibir dados da página atual
    st.dataframe(data_agrupado.iloc[inicio:fim], width='stretch')
    st.info(f"Mostrando registros {inicio + 1} a {min(fim, len(data_agrupado))} de {len(data_agrupado):,}")
    st.markdown("---")  
with aba4:
        
    
    # Gráfico de evolução mensal de todas as coberturas
    st.header("Gráficos de Cobertura por Estado")
    st.subheader(f"📊 Filtros: {filtros_str}")
    
    st.subheader("📈 Evolução Mensal da Cobertura Vacinal")
    
    # Selecionar cobertura para visualizar a evolução
    cobertura_evolucao = st.selectbox(
        "Selecione a vacina para visualizar a evolução mensal:",
        coberturas_disponiveis,
        key="select_cobertura_evolucao"
    )
    
    if cobertura_evolucao:
        # Filtrar dados por cobertura selecionada (usar data_todos_anos para pegar todos os anos)
        df_evolucao = data_todos_anos[data_todos_anos['DS_COBERTURA'] == cobertura_evolucao].copy()
        
        # Aplicar filtros geográficos se houver
        if regiao_selecionada != 'Todas' and 'REGIAO' in df_evolucao.columns:
            df_evolucao = df_evolucao[df_evolucao['REGIAO'] == regiao_selecionada]
        if uf_selecionado != 'Todos' and 'sg_uf' in df_evolucao.columns:
            df_evolucao = df_evolucao[df_evolucao['sg_uf'] == uf_selecionado]
        if municipio_selecionado != 'Todos' and 'no_municipio' in df_evolucao.columns:
            df_evolucao = df_evolucao[df_evolucao['no_municipio'] == municipio_selecionado]
        
        if len(df_evolucao) > 0 and 'NU_MES' in df_evolucao.columns and 'NU_ANO' in df_evolucao.columns:
            # Agrupar por ano e mês
            evolucao = df_evolucao.groupby(['NU_ANO', 'NU_MES']).agg({
                'QT_DOSES': 'sum',
                'QT_POPULACAO': 'sum'
            }).reset_index()
            
            # Ordenar por ano e mês
            evolucao = evolucao.sort_values(['NU_ANO', 'NU_MES'])
            
            # Calcular doses e população acumuladas POR ANO
            evolucao['QT_DOSES_ACUMULADAS'] = evolucao.groupby('NU_ANO')['QT_DOSES'].cumsum()
            evolucao['QT_POPULACAO_ACUMULADA'] = evolucao.groupby('NU_ANO')['QT_POPULACAO'].cumsum()
            
            # Calcular cobertura (doses acumuladas / população acumulada)
            evolucao['COBERTURA'] = (evolucao['QT_DOSES_ACUMULADAS'] / evolucao['QT_POPULACAO_ACUMULADA']) * 100
            
            # Criar nome do mês
            meses_nomes = {
                1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun',
                7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
            }
            evolucao['MES_NOME'] = evolucao['NU_MES'].map(meses_nomes)
            
            # Criar coluna de ano como string para o gráfico
            evolucao['ANO_STR'] = evolucao['NU_ANO'].astype(str)
            
            # Ordem dos meses
            ordem_meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
            
            # Buscar meta da cobertura
            meta_evolucao = get_meta_cobertura(cobertura_evolucao)
            
            # Criar gráfico de linhas com uma linha para cada ano
            fig_evolucao = px.line(
                evolucao,
                x='MES_NOME',
                y='COBERTURA',
                color='ANO_STR',
                title=f'Evolução Mensal da Cobertura - {cobertura_evolucao} (Todos os Anos)',
                labels={'MES_NOME': 'Mês', 'COBERTURA': 'Cobertura (%)', 'ANO_STR': 'Ano'},
                markers=True,
                category_orders={'MES_NOME': ordem_meses}
            )
            
            # Adicionar linha horizontal da meta
            fig_evolucao.add_hline(
                y=meta_evolucao,
                line_dash="dash",
                line_color="red",
                annotation_text=f"Meta: {meta_evolucao:.1f}%",
                annotation_position="right"
            )
            
            # Configurar layout
            fig_evolucao.update_traces(
                line_width=3,
                marker=dict(size=8)
            )
            
            fig_evolucao.update_layout(
                height=500,
                xaxis_title='Mês',
                yaxis_title='Cobertura (%)',
                yaxis=dict(range=[0, max(110, meta_evolucao + 10)]),
                hovermode='x unified',
                showlegend=True,
                legend=dict(
                    title="Ano",
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02
                )
            )
            
            st.plotly_chart(fig_evolucao, width='stretch')
            
            # Mostrar estatísticas por ano
            anos_presentes = sorted(evolucao['NU_ANO'].unique())
            st.markdown("### 📊 Estatísticas por Ano")
            cols = st.columns(len(anos_presentes))
            for idx, ano in enumerate(anos_presentes):
                dados_ano = evolucao[evolucao['NU_ANO'] == ano]
                with cols[idx]:
                    st.metric(f"Ano {ano}", f"{dados_ano['COBERTURA'].max():.2f}%".replace('.', ','), 
                             help=f"Maior cobertura em {ano}")
            
            # Demonstração do cálculo
            st.markdown("---")
            st.subheader("📋 Demonstração do Cálculo da Evolução Mensal")
            
            # Criar tabela com os cálculos incluindo o ano
            tabela_calculo = evolucao[['NU_ANO', 'MES_NOME', 'QT_DOSES', 'QT_DOSES_ACUMULADAS', 'QT_POPULACAO', 'QT_POPULACAO_ACUMULADA', 'COBERTURA']].copy()
            tabela_calculo['COBERTURA_FORMATADA'] = tabela_calculo['COBERTURA'].apply(lambda x: f"{x:.2f}%".replace('.', ','))
            
            # Formatar números no padrão brasileiro
            tabela_calculo['QT_DOSES_FORMATADA'] = tabela_calculo['QT_DOSES'].apply(formatar_numero_br)
            tabela_calculo['QT_DOSES_ACUMULADAS_FORMATADA'] = tabela_calculo['QT_DOSES_ACUMULADAS'].apply(formatar_numero_br)
            tabela_calculo['QT_POPULACAO_FORMATADA'] = tabela_calculo['QT_POPULACAO'].apply(formatar_numero_br)
            tabela_calculo['QT_POPULACAO_ACUMULADA_FORMATADA'] = tabela_calculo['QT_POPULACAO_ACUMULADA'].apply(formatar_numero_br)
            
            # Renomear colunas
            tabela_calculo_display = tabela_calculo[['NU_ANO', 'MES_NOME', 'QT_DOSES_FORMATADA', 'QT_DOSES_ACUMULADAS_FORMATADA', 'QT_POPULACAO_FORMATADA', 'QT_POPULACAO_ACUMULADA_FORMATADA', 'COBERTURA_FORMATADA']].rename(
                columns={
                    'NU_ANO': 'Ano',
                    'MES_NOME': 'Mês',
                    'QT_DOSES_FORMATADA': 'Doses do Mês',
                    'QT_DOSES_ACUMULADAS_FORMATADA': 'Doses Acumuladas',
                    'QT_POPULACAO_FORMATADA': 'População do Mês',
                    'QT_POPULACAO_ACUMULADA_FORMATADA': 'População Acumulada',
                    'COBERTURA_FORMATADA': 'Cobertura (%)'
                }
            )
            
            st.dataframe(tabela_calculo_display, width='stretch', hide_index=True)
            
            # Explicação do cálculo
          #  st.info("""
          #  **Como o cálculo é feito:**
            
          #  - **Doses do Mês**: Quantidade de doses aplicadas no mês específico
          #  - **Doses Acumuladas**: Soma cumulativa das doses (Janeiro + Fevereiro + Março + ...)
          #  - **População do Mês**: População alvo do mês específico
          #  - **População Acumulada**: Soma cumulativa da população (Janeiro + Fevereiro + Março + ...)
          #  - **Cobertura (%)**: (Doses Acumuladas / População Acumulada) × 100
            
          #  **Exemplos:**
          #  - **Janeiro**: (Doses de Jan / População de Jan) × 100
          #  - **Fevereiro**: (Doses de Jan + Fev / População de Jan + Fev) × 100
          #  - **Março**: (Doses de Jan + Fev + Mar / População de Jan + Fev + Mar) × 100
          #  """)
        else:
            st.warning("Não há dados mensais disponíveis para esta cobertura com os filtros aplicados.")
    else:
        st.info("Selecione uma cobertura para visualizar a evolução mensal.")
    
    st.markdown("---")
    
    # Selecionar cobertura para visualizar
    cobertura_grafico = st.selectbox(
        "Selecione a cobertura vacinal",
        coberturas_disponiveis,
        key="select_cobertura_grafico"
    )
    
    if cobertura_grafico:
        # Filtrar dados por cobertura selecionada
        df_grafico = data_agrupado[data_agrupado['DS_COBERTURA'] == cobertura_grafico].copy()
        
        if len(df_grafico) > 0 and 'sg_uf' in df_grafico.columns:
            # Calcular cobertura por estado
            cobertura_por_estado = df_grafico.groupby('sg_uf').agg({
                'QT_DOSES': 'sum',
                'QT_POPULACAO': 'sum'
            }).reset_index()
            
            cobertura_por_estado['COBERTURA'] = (
                cobertura_por_estado['QT_DOSES'] / cobertura_por_estado['QT_POPULACAO']
            ) * 100
            
            # Ordenar por cobertura crescente (para exibir melhor no gráfico vertical)
            cobertura_por_estado = cobertura_por_estado.sort_values('COBERTURA', ascending=False)
            
            # Buscar meta da cobertura
            meta_valor = get_meta_cobertura(cobertura_grafico)
            
            # Criar gráfico de barras verticais
            fig = px.bar(
                cobertura_por_estado,
                x='sg_uf',
                y='COBERTURA',
                title=f'Cobertura de {cobertura_grafico} por Estado',
                labels={'COBERTURA': 'Cobertura (%)', 'sg_uf': 'Estado'},
                text='COBERTURA',
                color='COBERTURA',
                color_continuous_scale=[
                    [0, '#790E18'],      # Rubi para 0%
                    [0.2, '#ff4444'],    # Vermelho para 20%
                    [0.4, '#ff9900'],    # Laranja para 40%
                    [0.6, '#ffdd00'],    # Amarelo para 60%
                    [0.8, '#44dd44'],    # Verde para 80%
                    [meta_valor/100, '#000099'],  # Azul na meta
                    [1, '#000099']       # Azul acima da meta
                ],
                range_color=[0, 100]
            )
            
            # Adicionar linha horizontal da meta
            fig.add_hline(
                y=meta_valor,
                line_dash="dash",
                line_color="red",
                annotation_text=f"Meta: {f'{meta_valor:.1f}'.replace('.', ',')}%",
                annotation_position="top right"
            )
            
            # Formatar texto nas barras
            fig.update_traces(
                texttemplate='%{text:.2f}%',
                textposition='outside',
                textfont_size=10
            )
            
            # Configurar layout
            fig.update_layout(
                height=600,
                showlegend=False,
                xaxis=dict(
                    title='Estado'
                ),
                yaxis=dict(
                    title='Cobertura (%)',
                    range=[0, max(105, meta_valor + 10)]
                )
            )
            
            st.plotly_chart(fig, width='stretch')
            
            st.markdown("---")
            
            # Mostrar estatísticas
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Maior Cobertura", f"{cobertura_por_estado['COBERTURA'].max():.2f}%".replace('.', ','))
            
            with col2:
                st.metric("Menor Cobertura", f"{cobertura_por_estado['COBERTURA'].min():.2f}%".replace('.', ','))
            
            with col3:
                estados_acima_meta = len(cobertura_por_estado[cobertura_por_estado['COBERTURA'] > meta_valor])
                st.metric("Estados Acima da Meta", f"{estados_acima_meta} de {len(cobertura_por_estado)}")
            
            # Mostrar tabela de dados
            st.subheader("Dados por Estado")
            cobertura_display = cobertura_por_estado.copy()
            cobertura_display['COBERTURA'] = cobertura_display['COBERTURA'].apply(
                lambda x: f"{x:.2f}%".replace('.', ',')
            )
            cobertura_display['QT_DOSES_FORMATADA'] = cobertura_display['QT_DOSES'].apply(formatar_numero_br)
            cobertura_display['QT_POPULACAO_FORMATADA'] = cobertura_display['QT_POPULACAO'].apply(formatar_numero_br)
            cobertura_display = cobertura_display.sort_values('sg_uf')
            st.dataframe(
                cobertura_display[['sg_uf', 'QT_DOSES_FORMATADA', 'QT_POPULACAO_FORMATADA', 'COBERTURA']].rename(
                    columns={
                        'sg_uf': 'Estado',
                        'QT_DOSES_FORMATADA': 'Doses Aplicadas',
                        'QT_POPULACAO_FORMATADA': 'População',
                        'COBERTURA': 'Cobertura'
                    }
                ),
                width='stretch',
                hide_index=True
            )
        else:
            st.warning("Não há dados disponíveis para esta cobertura com os filtros aplicados.")




