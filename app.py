import os
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from models.poisson_model import PoissonModel

# ── 1. Configuração da Página ──
st.set_page_config(page_title="Football AI Predictor", page_icon="⚽", layout="wide")
st.title("⚽ Football AI Predictor - Dashboard Preditivo")
st.markdown("Bem-vindo ao motor de inteligência que analisa o passado para prever a próxima rodada.")

# ── 2. Inicializar Firebase ──
@st.cache_resource
def init_firebase():
    # 1. Tenta carregar do .env.local (ambiente local)
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env.local")
    load_dotenv(dotenv_path=env_path)
    
    cert_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    
    # 2. Se não encontrar (ambiente de Produção / Streamlit Cloud), busca nos Secrets
    if not cert_json:
        try:
            cert_json = st.secrets["FIREBASE_SERVICE_ACCOUNT"]
        except Exception:
            st.error("Credenciais do Firebase não encontradas.")
            return None

    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(cert_json))
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

# ── 3. Carregar Dados ──
@st.cache_data(ttl=3600)
def load_matches():
    if not db:
        return pd.DataFrame()
    docs = db.collection("real_matches").get()
    data = [doc.to_dict() for doc in docs]
    df = pd.DataFrame(data)
    
    if not df.empty and 'timestamp' in df.columns:
        df['date'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
        df = df.sort_values('date')
    return df

with st.spinner("Carregando milhares de jogos do Firebase..."):
    df_all = load_matches()

if df_all.empty:
    st.warning("Nenhum jogo encontrado no Firebase.")
    st.stop()

# ── 4. Filtros Laterais ──
st.sidebar.header("Filtros de Análise")
leagues = df_all['leagueName'].dropna().unique().tolist()
selected_league = st.sidebar.selectbox("Selecione a Liga:", leagues)

df_league = df_all[df_all['leagueName'] == selected_league]

# Separa jogos finalizados de jogos futuros
df_finished = df_league[df_league['status'].isin(['FT', 'AET', 'PEN'])]
df_upcoming = df_league[df_league['status'].isin(['NS', 'TBD'])]

st.sidebar.metric("Jogos Analisados", len(df_finished))
st.sidebar.metric("Próximos Jogos", len(df_upcoming))

# ── 5. Inteligência Artificial (Poisson) ──
if not df_finished.empty:
    model = PoissonModel(df_finished)
else:
    model = None

# ── 6. Visualização do Histórico ──
st.subheader(f"📊 Análise Histórica: {selected_league}")
col1, col2 = st.columns(2)

with col1:
    if not df_finished.empty:
        # Gráfico de Vitórias
        conditions = [
            (df_finished['goalsHome'] > df_finished['goalsAway']),
            (df_finished['goalsHome'] < df_finished['goalsAway'])
        ]
        choices = ['Vitória Casa', 'Vitória Fora']
        df_finished['Resultado'] = np.select(conditions, choices, default='Empate')
        
        fig = px.pie(df_finished, names='Resultado', title="Distribuição de Resultados (Vantagem de Casa)", color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig, use_container_width=True)

with col2:
    if not df_finished.empty:
        # Gráfico de Placares Comuns
        df_finished['Placar'] = df_finished['goalsHome'].astype(int).astype(str) + " x " + df_finished['goalsAway'].astype(int).astype(str)
        top_scores = df_finished['Placar'].value_counts().head(10).reset_index()
        top_scores.columns = ['Placar', 'Frequência']
        
        fig2 = px.bar(top_scores, x='Placar', y='Frequência', title="Top 10 Placares Mais Comuns", text='Frequência')
        st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── 7. Previsões da Próxima Rodada ──
st.subheader("🔮 Previsões da Inteligência Artificial (Próxima Rodada)")
st.markdown("Com base no histórico matemático (Distribuição de Poisson), aqui estão as probabilidades exatas para os próximos jogos desta liga.")

if df_upcoming.empty:
    st.info("Não há jogos futuros mapeados no banco para esta liga no momento.")
elif model is None:
    st.warning("Não há histórico suficiente para calcular probabilidades.")
else:
    predictions = []
    
    # Processa apenas os próximos 10 jogos para não poluir a tela
    for _, match in df_upcoming.head(10).iterrows():
        home = match.get('homeTeamName', 'Unknown')
        away = match.get('awayTeamName', 'Unknown')
        date_str = match.get('date', 'Data TBD')
        
        pred = model.predict_match(home, away)
        
        # Identificar apostas de valor (Value Bets) visualmente
        value_alert = ""
        if pred["Home Win"] > 60:
            value_alert = "🔥 Favorito Claro (Casa)"
        elif pred["Away Win"] > 60:
            value_alert = "🔥 Favorito Claro (Fora)"
        elif pred["Over 2.5"] > 60:
            value_alert = "⚽ Tendência Over 2.5 Gols"
            
        predictions.append({
            "Data": str(date_str)[:10],
            "Confronto": f"{home} vs {away}",
            "Vitória Casa": f"{pred['Home Win']}%",
            "Empate": f"{pred['Draw']}%",
            "Vitória Fora": f"{pred['Away Win']}%",
            "Ambos Marcam": f"{pred['BTTS (Ambos Marcam)']}%",
            "Mais 2.5 Gols": f"{pred['Over 2.5']}%",
            "Placar xG": pred['Most Likely Score'],
            "Alerta": value_alert
        })
        
    df_preds = pd.DataFrame(predictions)
    st.dataframe(df_preds, use_container_width=True, hide_index=True)
    
    st.caption("A fórmula de Poisson calcula as Expectativas de Gols (xG) baseada no ataque e defesa dos dois times ao longo das últimas temporadas armazenadas no Firebase.")
