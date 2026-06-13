import os
import json
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from dotenv import load_dotenv
from supabase import create_client, Client
from models.poisson_model import PoissonModel

# ── 1. Configuração e Estilo Premium ──
st.set_page_config(page_title="Football AI Predictor Pro", page_icon="🔮", layout="wide")

st.markdown("""
<style>
    /* Estilo Premium Dark */
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    .metric-card {
        background-color: #1E212B;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #00ff88;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        margin-bottom: 20px;
    }
    .value-bet {
        color: #00ff88 !important;
        font-weight: bold;
    }
    .danger-bet {
        color: #ff4b4b !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🔮 Football AI Predictor - Pro Dashboard")
st.markdown("*Plataforma avançada de análise preditiva e odds matemáticas baseada em Distribuição de Poisson.*")

# ── 2. Inicializar Supabase ──
@st.cache_resource
def init_supabase():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env.local")
    load_dotenv(dotenv_path=env_path)
    
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        try:
            url = st.secrets["NEXT_PUBLIC_SUPABASE_URL"]
            key = st.secrets["SUPABASE_ANON_KEY"]
        except Exception:
            st.error("Credenciais do Supabase não encontradas.")
            return None
            
    return create_client(url, key)

supabase_client = init_supabase()

# ── 3. Carregar Dados ──
@st.cache_data(ttl=3600)
def load_matches():
    if not supabase_client:
        return pd.DataFrame()
        
    all_data = []
    limit = 1000
    offset = 0
    
    while True:
        try:
            response = supabase_client.table("matches").select("*").range(offset, offset + limit - 1).execute()
            rows = response.data
            if not rows:
                break
            all_data.extend(rows)
            if len(rows) < limit:
                break
            offset += limit
        except Exception as e:
            st.error(f"Erro ao carregar dados do Supabase: {e}")
            break
            
    if not all_data:
        return pd.DataFrame()
        
    df = pd.DataFrame(all_data)
    
    # Mapear as colunas do padrão Postgres snake_case para o camelCase/Padrão que o modelo/dashboard espera
    column_mapping = {
        "fixture_id": "fixtureId",
        "league_id": "leagueId",
        "league_name": "leagueName",
        "season": "season",
        "date": "date_raw",
        "timestamp": "timestamp",
        "status": "status",
        "home_team_id": "homeTeamId",
        "home_team_name": "homeTeamName",
        "away_team_id": "awayTeamId",
        "away_team_name": "awayTeamName",
        "goals_home": "goalsHome",
        "goals_away": "goalsAway",
        "score_ht_home": "scoreHtHome",
        "score_ht_away": "scoreHtAway",
        "score_ft_home": "scoreFtHome",
        "score_ft_away": "scoreFtAway"
    }
    df = df.rename(columns=column_mapping)
    
    # Adicionar as colunas adicionais para o Poisson caso precise usá-las (cantos, cartões, etc.)
    if 'home_corners' in df.columns:
        df['homeCorners'] = df['home_corners']
        df['awayCorners'] = df['away_corners']
    if 'home_yellow_cards' in df.columns:
        df['homeYellowCards'] = df['home_yellow_cards']
        df['awayYellowCards'] = df['away_yellow_cards']
        df['homeRedCards'] = df['home_red_cards']
        df['awayRedCards'] = df['away_red_cards']
        
    if not df.empty and 'timestamp' in df.columns:
        df['date'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
        df = df.sort_values('date')
        
    return df

with st.spinner("Sincronizando banco de dados de inteligência..."):
    df_all = load_matches()

if df_all.empty:
    st.warning("Nenhum jogo encontrado no Supabase.")
    st.stop()

# ── 4. Filtros Globais (Sidebar) ──
st.sidebar.header("⚙️ Configurações Globais")

# Filtro de Data do Histórico (Treinamento do Modelo)
# Pega a data mínima real do banco de dados
if not df_all.empty and 'date' in df_all.columns:
    valid_dates = df_all['date'].dropna()
    min_date = valid_dates.min().date() if not valid_dates.empty else datetime(2022, 1, 1).date()
    max_date = valid_dates.max().date() if not valid_dates.empty else datetime.now().date()
else:
    min_date = datetime(2022, 1, 1).date()
    max_date = datetime.now().date()

st.sidebar.subheader("Janela de Treinamento (Passado)")
hist_start_date = st.sidebar.date_input("Usar histórico a partir de:", min_date,
    min_value=min_date, max_value=max_date)
hist_end_date = st.sidebar.date_input("Usar histórico até:", max_date,
    min_value=min_date, max_value=max_date)

# Filtrar o DataFrame de Treinamento
df_filtered_history = df_all[
    (df_all['date'].dt.date >= hist_start_date) &
    (df_all['date'].dt.date <= hist_end_date)
]
df_finished_all = df_filtered_history[df_filtered_history['status'].isin(['FT', 'AET', 'PEN'])]

# Jogos NS/TBD (não iniciados) - todos os disponíveis no banco
# O plano gratuito da API só tem até 2024, então mostramos todos os NS/TBD encontrados
st.sidebar.subheader("Filtro da Rodada")
df_all_ns = df_all[df_all['status'].isin(['NS', 'TBD'])]

if not df_all_ns.empty:
    ns_dates = df_all_ns['date'].dropna()
    ns_min = ns_dates.min().date() if not ns_dates.empty else min_date
    ns_max = ns_dates.max().date() if not ns_dates.empty else max_date
    rodada_start = st.sidebar.date_input("Rodada de:", ns_min, min_value=ns_min, max_value=ns_max)
    rodada_end = st.sidebar.date_input("Rodada até:", ns_max, min_value=ns_min, max_value=ns_max)
    df_upcoming_all = df_all_ns[
        (df_all_ns['date'].dt.date >= rodada_start) &
        (df_all_ns['date'].dt.date <= rodada_end)
    ]
else:
    df_upcoming_all = pd.DataFrame()
    st.sidebar.info("Não há jogos futuros no banco.")

st.sidebar.divider()
st.sidebar.subheader("🏆 Filtro de Liga")

all_leagues = sorted(df_all['leagueName'].dropna().unique().tolist())
selected_leagues = st.sidebar.multiselect(
    "Selecione as ligas:", 
    options=all_leagues,
    default=all_leagues,
    placeholder="Escolha as ligas..."
)

# Aplica o filtro de liga em ambos os DataFrames
if selected_leagues:
    df_finished_all = df_finished_all[df_finished_all['leagueName'].isin(selected_leagues)]
    if not df_upcoming_all.empty and 'leagueName' in df_upcoming_all.columns:
        df_upcoming_all = df_upcoming_all[df_upcoming_all['leagueName'].isin(selected_leagues)]

st.sidebar.divider()
st.sidebar.metric("Jogos no Banco de Dados", len(df_all))
st.sidebar.metric("Jogos Usados no Treinamento", len(df_finished_all))
st.sidebar.metric("Jogos para Previsão", len(df_upcoming_all))

# ── 5. Estrutura de Abas (Tabs) ──
tab1, tab2, tab3 = st.tabs(["🌍 Radar Global (Value Bets)", "📊 Análise por Liga", "🔗 Construtor de Múltiplas"])

# ==========================================
# ABA 1: RADAR GLOBAL
# ==========================================
with tab1:
    st.header("Radar de Apostas de Valor")
    st.markdown("O algoritmo vasculhou **todas as ligas** e encontrou as melhores oportunidades matemáticas.")
    
    if df_upcoming_all.empty:
        st.info("Não há jogos NS/TBD disponíveis para o período selecionado na sidebar.")
    else:
        with st.spinner("Processando IA Global..."):
            all_predictions = []
            
            # Agrupar histórico por liga para criar modelos individuais
            leagues = df_upcoming_all['leagueName'].unique()
            for league in leagues:
                df_hist_league = df_finished_all[df_finished_all['leagueName'] == league]
                if df_hist_league.empty: continue
                
                model = PoissonModel(df_hist_league)
                df_up_league = df_upcoming_all[df_upcoming_all['leagueName'] == league]
                
                for _, match in df_up_league.iterrows():
                    home = match.get('homeTeamName', 'Unknown')
                    away = match.get('awayTeamName', 'Unknown')
                    date_str = str(match.get('date', 'Data TBD'))[:10]
                    
                    pred = model.predict_match(home, away)
                    pred['Liga'] = league
                    pred['Data'] = date_str
                    pred['Confronto'] = f"{home} vs {away}"
                    all_predictions.append(pred)
            
            if all_predictions:
                df_preds = pd.DataFrame(all_predictions)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🔥 Top 5 Favoritos (Match Odds)")
                    # Filtra times com maior chance de vitória
                    df_favs = df_preds.copy()
                    df_favs['Max Win %'] = df_favs[['Home Win %', 'Away Win %']].max(axis=1)
                    df_favs['Pick'] = np.where(df_favs['Home Win %'] > df_favs['Away Win %'], 'Casa', 'Fora')
                    df_favs['Fair Odd'] = np.where(df_favs['Pick'] == 'Casa', df_favs['Home Odd'], df_favs['Away Odd'])
                    
                    top_favs = df_favs.sort_values(by='Max Win %', ascending=False).head(5)
                    st.dataframe(top_favs[['Liga', 'Data', 'Confronto', 'Pick', 'Max Win %', 'Fair Odd']], hide_index=True)
                
                with col2:
                    st.subheader("⚽ Top 5 Jogos para Gols (Over 2.5)")
                    top_goals = df_preds.sort_values(by='Over 2.5 %', ascending=False).head(5)
                    st.dataframe(top_goals[['Liga', 'Data', 'Confronto', 'Over 2.5 %', 'Over 2.5 Odd', 'BTTS %']], hide_index=True)


# ==========================================
# ABA 2: ANÁLISE POR LIGA
# ==========================================
with tab2:
    available_leagues = df_finished_all['leagueName'].dropna().unique().tolist()
    if not available_leagues:
        st.warning("Sem histórico de jogos finalizados no período selecionado.")
    else:
        selected_league = st.selectbox("Selecione a Liga para análise detalhada:", available_leagues)
        
        df_league_hist = df_finished_all[df_finished_all['leagueName'] == selected_league].copy()
        
        # Filtra jogos não iniciados apenas se a coluna existir e o df não estiver vazio
        if not df_upcoming_all.empty and 'leagueName' in df_upcoming_all.columns:
            df_league_up = df_upcoming_all[df_upcoming_all['leagueName'] == selected_league]
        else:
            df_league_up = pd.DataFrame()
        
        st.markdown(f"### Histórico Matemático: {selected_league}")
        c1, c2 = st.columns(2)
        with c1:
            conditions = [
                (df_league_hist['goalsHome'] > df_league_hist['goalsAway']),
                (df_league_hist['goalsHome'] < df_league_hist['goalsAway'])
            ]
            df_league_hist['Resultado'] = np.select(conditions, ['Vitória Casa', 'Vitória Fora'], default='Empate')
            fig = px.pie(df_league_hist, names='Resultado', title="Vantagem de Casa (1X2)", hole=0.3)
            st.plotly_chart(fig, use_container_width=True)
        
        with c2:
            df_league_hist['Placar'] = df_league_hist['goalsHome'].astype(int).astype(str) + " x " + df_league_hist['goalsAway'].astype(int).astype(str)
            top_scores = df_league_hist['Placar'].value_counts().head(8).reset_index()
            top_scores.columns = ['Placar', 'Freq']
            fig2 = px.bar(top_scores, x='Placar', y='Freq', title="Placares mais Frequentes")
            st.plotly_chart(fig2, use_container_width=True)
            
        st.markdown("### Previsões e Odds Justas da Rodada")
        if not df_league_up.empty and not df_league_hist.empty:
            league_model = PoissonModel(df_league_hist)
            preds = []
            for _, match in df_league_up.iterrows():
                home = match.get('homeTeamName', 'Unknown')
                away = match.get('awayTeamName', 'Unknown')
                date_str = str(match.get('date', 'Data TBD'))[:10]
                p = league_model.predict_match(home, away)
                preds.append({
                    "Data": date_str,
                    "Jogo": f"{home} x {away}",
                    "Casa %": p['Home Win %'], "Odd Casa": p['Home Odd'],
                    "Empate %": p['Draw %'], "Odd Empate": p['Draw Odd'],
                    "Fora %": p['Away Win %'], "Odd Fora": p['Away Odd'],
                    "O2.5 %": p['Over 2.5 %'], "Odd O2.5": p['Over 2.5 Odd']
                })
            st.dataframe(pd.DataFrame(preds), hide_index=True, use_container_width=True)
        else:
            st.info("ℹ️ Não há jogos NS/TBD nesta liga. Para ver previsões de todos os confrontos históricos, selecione uma janela de datas na barra lateral.")

# ==========================================
# ABA 3: CONSTRUTOR DE MÚLTIPLAS
# ==========================================
with tab3:
    st.header("Construtor de Múltiplas (Parlay Builder)")
    st.markdown("Selecione vários eventos para calcular a Probabilidade Acumulada e a Odd Justa Final.")
    
    if df_upcoming_all.empty:
        st.warning("Não há jogos disponíveis para montar múltiplas.")
    else:
        # Puxa o mesmo all_predictions gerado no Radar
        if 'df_preds' in locals():
            st.write("Escolha as seleções que deseja colocar no seu Bilhete:")
            
            selected_picks = []
            
            for idx, row in df_preds.iterrows():
                with st.expander(f"{row['Data']} | {row['Liga']} | {row['Confronto']}"):
                    col_a, col_b, col_c, col_d = st.columns(4)
                    with col_a:
                        if st.checkbox(f"Casa (Odd {row['Home Odd']})", key=f"h_{idx}"):
                            selected_picks.append({"Jogo": row['Confronto'], "Mercado": "Vitória Casa", "Prob": row['Home Win %'], "Odd": row['Home Odd']})
                    with col_b:
                        if st.checkbox(f"Empate (Odd {row['Draw Odd']})", key=f"d_{idx}"):
                            selected_picks.append({"Jogo": row['Confronto'], "Mercado": "Empate", "Prob": row['Draw %'], "Odd": row['Draw Odd']})
                    with col_c:
                        if st.checkbox(f"Fora (Odd {row['Away Odd']})", key=f"a_{idx}"):
                            selected_picks.append({"Jogo": row['Confronto'], "Mercado": "Vitória Fora", "Prob": row['Away Win %'], "Odd": row['Away Odd']})
                    with col_d:
                        if st.checkbox(f"Over 2.5 (Odd {row['Over 2.5 Odd']})", key=f"o_{idx}"):
                            selected_picks.append({"Jogo": row['Confronto'], "Mercado": "Mais de 2.5 Gols", "Prob": row['Over 2.5 %'], "Odd": row['Over 2.5 Odd']})
            
            if selected_picks:
                st.divider()
                st.subheader("🧾 O Seu Bilhete")
                df_bilhete = pd.DataFrame(selected_picks)
                st.dataframe(df_bilhete, hide_index=True)
                
                # Cálculo da Múltipla
                prob_acumulada = 1.0
                odd_acumulada = 1.0
                for p in selected_picks:
                    prob_acumulada *= (p['Prob'] / 100)
                    odd_acumulada *= p['Odd']
                
                st.markdown(f"""
                <div class="metric-card">
                    <h3>Resumo da Múltipla</h3>
                    <p><b>Probabilidade Matemática Acumulada:</b> {round(prob_acumulada * 100, 2)}%</p>
                    <p><b>ODD JUSTA FINAL:</b> <span class="value-bet">{round(odd_acumulada, 2)}</span></p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Nenhuma previsão processada.")
