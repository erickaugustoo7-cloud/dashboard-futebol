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
tab1, tab2, tab3, tab4 = st.tabs([
    "🌍 Radar Global (Value Bets)",
    "📊 Análise por Liga",
    "🔗 Construtor de Múltiplas",
    "🧪 Sanity Dashboard"
])

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


# ==========================================
# ABA 4: SANITY DASHBOARD
# ==========================================

@st.cache_data(ttl=900)  # Refresca a cada 15 minutos
def load_audit_data():
    """Carrega predições resolvidas da view v_audit_predictions."""
    if not supabase_client:
        return pd.DataFrame()
    try:
        # Busca todas as predições com aposta resolvida
        response = supabase_client.table("predictions") \
            .select(
                "id,fixture_id,confidence_score,confidence_level,"
                "suggested_bet,fair_odd,bookmaker_odd,stake,"
                "actual_result,profit_loss,bet_resolved,resolved_at,"
                "home_win_prob,draw_prob,away_win_prob,over25_prob,btts_prob,"
                "model_version,created_at"
            ) \
            .eq("bet_resolved", True) \
            .not_.is_("profit_loss", "null") \
            .order("resolved_at", desc=False) \
            .execute()
        df = pd.DataFrame(response.data or [])
        if not df.empty:
            df["profit_loss"]    = pd.to_numeric(df["profit_loss"],    errors="coerce").fillna(0)
            df["confidence_score"] = pd.to_numeric(df["confidence_score"], errors="coerce").fillna(0)
            df["bookmaker_odd"]  = pd.to_numeric(df["bookmaker_odd"],  errors="coerce")
            df["resolved_at"]    = pd.to_datetime(df["resolved_at"],   errors="coerce", utc=True)
            df["created_at"]     = pd.to_datetime(df["created_at"],    errors="coerce", utc=True)
            df["is_win"]         = df["profit_loss"] > 0
            # Faixa de confiança para a Matriz de Calibração
            bins   = [0, 60, 70, 80, 90, 101]
            labels = ["<60", "60-70", "70-80", "80-90", "90+"]
            df["confidence_band"] = pd.cut(
                df["confidence_score"], bins=bins, labels=labels, right=False
            )
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados de auditoria: {e}")
        return pd.DataFrame()


with tab4:
    st.header("🧪 Sanity Dashboard — Auditoria da Inteligência")
    st.markdown(
        "Painel de auditoria automática: **fecha o ciclo** entre a predição e o resultado real. "
        "Rode `python scripts/resolve_predictions.py` após os jogos encerrarem para popular os dados."
    )

    df_audit = load_audit_data()

    if df_audit.empty:
        st.info(
            "⏳ Nenhuma predição resolvida ainda. "
            "Execute `python scripts/generate_predictions.py` para gerar predições, "
            "aguarde os jogos e rode `python scripts/resolve_predictions.py` para resolver."
        )
    else:
        # ─────────────────────────────────────────────────────────────
        # MÉTRICAS GLOBAIS
        # ─────────────────────────────────────────────────────────────
        total_bets   = len(df_audit)
        total_greens = df_audit["is_win"].sum()
        total_reds   = total_bets - total_greens
        global_pnl   = df_audit["profit_loss"].sum()
        global_roi   = (global_pnl / total_bets * 100) if total_bets > 0 else 0
        win_rate     = (total_greens / total_bets * 100) if total_bets > 0 else 0

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("🎯 Apostas Resolvidas", f"{total_bets}")
        m2.metric("✅ Greens", f"{total_greens} ({win_rate:.1f}%)")
        m3.metric("❌ Reds",   f"{total_reds}")
        m4.metric("💰 P&L Total",  f"{global_pnl:+.2f}u",
                  delta=f"{global_pnl:+.2f}u",
                  delta_color="normal" if global_pnl >= 0 else "inverse")
        m5.metric("📈 ROI Global", f"{global_roi:+.1f}%",
                  delta=f"{global_roi:+.1f}%",
                  delta_color="normal" if global_roi >= 0 else "inverse")

        st.divider()

        # ─────────────────────────────────────────────────────────────
        # SEÇÃO 1: GRÁFICO DE PNL CUMULATIVO
        # ─────────────────────────────────────────────────────────────
        st.subheader("📉 Curva de Capital (P&L Cumulativo)")
        st.markdown(
            "*Cada ponto representa o saldo acumulado após resolver uma aposta. "
            "Uma curva ascendente indica edge real do modelo.*"
        )

        df_pnl = df_audit.sort_values("resolved_at").copy()
        df_pnl["pnl_cumulativo"] = df_pnl["profit_loss"].cumsum()
        df_pnl["aposta_n"]       = range(1, len(df_pnl) + 1)
        df_pnl["cor"] = df_pnl["pnl_cumulativo"].apply(
            lambda x: "#00ff88" if x >= 0 else "#ff4b4b"
        )

        fig_pnl = px.line(
            df_pnl,
            x="aposta_n",
            y="pnl_cumulativo",
            title="Curva de P&L Cumulativo (Unidades de Stake)",
            labels={"aposta_n": "Nº de Apostas Resolvidas", "pnl_cumulativo": "Saldo (unidades)"},
            color_discrete_sequence=["#00d4ff"],
            hover_data=["suggested_bet", "profit_loss", "confidence_score"]
        )
        fig_pnl.add_hline(y=0, line_dash="dash", line_color="#888", annotation_text="Break-even")
        fig_pnl.update_layout(
            template="plotly_dark",
            plot_bgcolor="#1E212B",
            paper_bgcolor="#1E212B",
            font_color="#FAFAFA"
        )
        st.plotly_chart(fig_pnl, use_container_width=True)

        st.divider()

        # ─────────────────────────────────────────────────────────────
        # SEÇÃO 2: MATRIZ DE CALIBRAÇÃO
        # ─────────────────────────────────────────────────────────────
        col_cal, col_por = st.columns([3, 2])

        with col_cal:
            st.subheader("🔬 Matriz de Calibração")
            st.markdown(
                "*Compara o **win rate esperado** (confidence score médio) vs "
                "o **win rate real** por faixa. Um modelo bem calibrado terá barras alinhadas.*"
            )

            df_cal = df_audit.dropna(subset=["confidence_band"]).copy()
            if not df_cal.empty:
                cal_grouped = df_cal.groupby("confidence_band", observed=True).agg(
                    total=("is_win", "count"),
                    greens=("is_win", "sum"),
                    conf_media=("confidence_score", "mean"),
                    pnl_total=("profit_loss", "sum")
                ).reset_index()
                cal_grouped["win_rate_real"]     = cal_grouped["greens"] / cal_grouped["total"] * 100
                cal_grouped["win_rate_esperado"] = cal_grouped["conf_media"]

                fig_cal = px.bar(
                    cal_grouped.melt(
                        id_vars=["confidence_band", "total"],
                        value_vars=["win_rate_esperado", "win_rate_real"],
                        var_name="Tipo",
                        value_name="Win Rate (%)"
                    ),
                    x="confidence_band",
                    y="Win Rate (%)",
                    color="Tipo",
                    barmode="group",
                    title="Win Rate Esperado vs Real por Faixa de Confiança",
                    labels={"confidence_band": "Faixa de Confiança"},
                    color_discrete_map={
                        "win_rate_esperado": "#00d4ff",
                        "win_rate_real":     "#00ff88"
                    },
                    text_auto=".0f"
                )
                fig_cal.update_layout(
                    template="plotly_dark",
                    plot_bgcolor="#1E212B",
                    paper_bgcolor="#1E212B",
                    font_color="#FAFAFA"
                )
                st.plotly_chart(fig_cal, use_container_width=True)

                # Tabela detalhada
                cal_grouped["win_rate_real"]     = cal_grouped["win_rate_real"].round(1)
                cal_grouped["win_rate_esperado"] = cal_grouped["win_rate_esperado"].round(1)
                cal_grouped["pnl_total"]         = cal_grouped["pnl_total"].round(2)
                st.dataframe(
                    cal_grouped[["confidence_band", "total", "greens",
                                 "win_rate_esperado", "win_rate_real", "pnl_total"]]
                    .rename(columns={
                        "confidence_band":  "Faixa",
                        "total":            "Total",
                        "greens":           "Acertos",
                        "win_rate_esperado": "WR Esperado (%)",
                        "win_rate_real":    "WR Real (%)",
                        "pnl_total":        "P&L (u)"
                    }),
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.info("Dados insuficientes para a Matriz de Calibração.")

        with col_por:
            st.subheader("📊 P&L por Mercado")
            df_por_mercado = df_audit.groupby("suggested_bet").agg(
                total=("is_win", "count"),
                greens=("is_win", "sum"),
                pnl=("profit_loss", "sum")
            ).reset_index()
            df_por_mercado["win_rate"] = (df_por_mercado["greens"] / df_por_mercado["total"] * 100).round(1)
            df_por_mercado["pnl"]     = df_por_mercado["pnl"].round(2)

            fig_m = px.bar(
                df_por_mercado,
                x="suggested_bet",
                y="pnl",
                color="pnl",
                color_continuous_scale=["#ff4b4b", "#888", "#00ff88"],
                title="P&L Total por Mercado",
                text_auto=".2f"
            )
            fig_m.update_layout(
                template="plotly_dark",
                plot_bgcolor="#1E212B",
                paper_bgcolor="#1E212B",
                font_color="#FAFAFA",
                coloraxis_showscale=False
            )
            st.plotly_chart(fig_m, use_container_width=True)

            st.dataframe(
                df_por_mercado[["suggested_bet", "total", "greens", "win_rate", "pnl"]]
                .rename(columns={
                    "suggested_bet": "Mercado",
                    "total":  "Total",
                    "greens": "Acertos",
                    "win_rate": "WR (%)",
                    "pnl":    "P&L (u)"
                }),
                hide_index=True,
                use_container_width=True
            )

        st.divider()

        # ─────────────────────────────────────────────────────────────
        # SEÇÃO 3: ALARME DE OVERFITTING
        # ─────────────────────────────────────────────────────────────
        st.subheader("🚨 Alarme de Overfitting")

        # Janela deslizante: últimas 30 predições resolvidas
        df_recent = df_audit.tail(30).copy()
        recent_pnl      = df_recent["profit_loss"].sum()
        recent_wins     = df_recent["is_win"].sum()
        recent_total    = len(df_recent)
        recent_win_rate = (recent_wins / recent_total * 100) if recent_total > 0 else 0
        avg_conf_recent = df_recent["confidence_score"].mean()

        alarm_col1, alarm_col2 = st.columns(2)

        with alarm_col1:
            st.markdown(f"""**Últimas {recent_total} apostas resolvidas:**""")
            st.markdown(f"- P&L: `{recent_pnl:+.2f}u`")
            st.markdown(f"- Win Rate Real: `{recent_win_rate:.1f}%`")
            st.markdown(f"- Confiança Média do Modelo: `{avg_conf_recent:.1f}%`")

        with alarm_col2:
            # Diagnóstico automático
            if recent_total < 10:
                st.info("⏳ Dados insuficientes para diagnóstico (mínimo: 10 apostas).")
            elif recent_pnl < -5 and avg_conf_recent > 70:
                st.error(
                    "⚠️ **ALERTA DE OVERFITTING DETECTADO!**\n\n"
                    f"O modelo diz confiança de **{avg_conf_recent:.0f}%** mas o P&L real está em "
                    f"**{recent_pnl:+.2f}u**. O modelo provavelmente **decorou os dados de treino** "
                    "e não está generalizando para partidas reais."
                )
            elif recent_pnl < -2:
                st.warning(
                    f"⚠️ P&L negativo nas últimas {recent_total} apostas ({recent_pnl:+.2f}u). "
                    "Monitore — pode ser variância ou indica overfitting emergente."
                )
            elif recent_pnl > 0 and recent_win_rate >= (avg_conf_recent * 0.8):
                st.success(
                    f"✅ **Modelo calibrado e com edge positivo!** "
                    f"Win rate real ({recent_win_rate:.1f}%) é compatível com a confiança média "
                    f"({avg_conf_recent:.0f}%). P&L: **{recent_pnl:+.2f}u**."
                )
            else:
                st.info(
                    f"Model em observação. P&L: {recent_pnl:+.2f}u | "
                    f"Win Rate: {recent_win_rate:.1f}% | Confiança média: {avg_conf_recent:.0f}%"
                )

        st.divider()

        # Tabela de histórico completo
        with st.expander("📃 Histórico Completo de Predições Resolvidas"):
            df_hist_display = df_audit[[
                "resolved_at", "suggested_bet", "actual_result",
                "confidence_score", "bookmaker_odd", "stake",
                "profit_loss", "is_win", "model_version"
            ]].copy()
            df_hist_display["resolved_at"] = df_hist_display["resolved_at"].dt.strftime("%Y-%m-%d %H:%M")
            df_hist_display["is_win"]      = df_hist_display["is_win"].map({True: "✅", False: "❌"})
            df_hist_display["profit_loss"] = df_hist_display["profit_loss"].apply(lambda x: f"{x:+.2f}u")
            df_hist_display = df_hist_display.rename(columns={
                "resolved_at":     "Data",
                "suggested_bet":   "Mercado",
                "actual_result":   "Resultado Real",
                "confidence_score": "Conf.",
                "bookmaker_odd":   "Odd",
                "stake":           "Stake",
                "profit_loss":     "P&L",
                "is_win":          "Status",
                "model_version":   "Versão"
            })
            st.dataframe(df_hist_display, hide_index=True, use_container_width=True)

