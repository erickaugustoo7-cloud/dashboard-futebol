# ARQUIVO LEGADO — NÃO USAR PARA FUTEBOL VIRTUAL
# ══════════════════════════════════════════════════════════════════════
# Este script foi criado para analisar dados do Brasileirão Real
# (API-Football) usando a coleção 'matches' do Firestore.
#
# Para Futebol Virtual Bet365, use o script correto em:
#   football-monitor/analysis/virtual_matches_analysis.py
# ══════════════════════════════════════════════════════════════════════

# analysis/firestore_analysis.py
"""
[LEGADO] Script de análise de dados de partidas de futebol REAL (Brasileirão).
Lê dados do Firestore (coleção 'matches'), limpa e calcula estatísticas com Pandas.

⚠️  ATENÇÃO: Este script NÃO é compatível com o pipeline de Futebol Virtual.
    Use football-monitor/analysis/virtual_matches_analysis.py para dados virtuais.

Dependências:
    pip install google-cloud-firestore pandas numpy python-dotenv

Variáveis de ambiente necessárias (arquivo .env.local):
    FIREBASE_SERVICE_ACCOUNT='{...json completo...}'
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from google.cloud import firestore
from google.oauth2 import service_account

# Carrega .env.local automaticamente (desenvolvimento local)
load_dotenv(".env.local")


# ─────────────────────────────────────────────
# 1. CONEXÃO COM FIRESTORE
# ─────────────────────────────────────────────

def get_firestore_client() -> firestore.Client:
    """
    Cria cliente Firestore a partir da variável de ambiente.
    Funciona tanto localmente (.env.local) quanto na nuvem (CI/CD).
    """
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if not raw:
        raise EnvironmentError(
            "Variável FIREBASE_SERVICE_ACCOUNT não encontrada.\n"
            "Crie um arquivo .env.local com o conteúdo do serviceAccountKey.json."
        )

    service_account_info = json.loads(raw)
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return firestore.Client(
        project=service_account_info["project_id"],
        credentials=credentials,
    )


# ─────────────────────────────────────────────
# 2. EXPORTAR COLEÇÃO PARA DATAFRAME
# ─────────────────────────────────────────────

def fetch_matches(
    client: firestore.Client,
    status_filter: str | None = None,
    season_filter: int | None = None,
) -> pd.DataFrame:
    """
    Exporta a coleção 'matches' para um DataFrame flat.

    Args:
        client: Cliente Firestore autenticado.
        status_filter: Filtrar por status (ex: 'FT', 'NS'). None = todos.
        season_filter: Filtrar por temporada (ex: 2025). None = todas.

    Returns:
        DataFrame com colunas achatadas (sem dicionários aninhados).
    """
    query = client.collection("matches")

    if status_filter:
        query = query.where("status", "==", status_filter)
    if season_filter:
        query = query.where("season", "==", season_filter)

    docs = query.stream()
    records = []

    for doc in docs:
        data = doc.to_dict()
        if not data:
            continue

        score      = data.get("score", {}) or {}
        halftime   = score.get("halftime", {}) or {}
        stats      = data.get("statistics", {}) or {}
        corners    = stats.get("corners", {}) or {}
        yellows    = stats.get("yellowCards", {}) or {}
        reds       = stats.get("redCards", {}) or {}
        shots      = stats.get("shotsOnTarget", {}) or {}
        possession = stats.get("possession", {}) or {}
        goals_raw  = data.get("goals", []) or []

        record = {
            # Identificação
            "match_id":   data.get("matchId"),
            "home_team":  data.get("homeTeam"),
            "away_team":  data.get("awayTeam"),
            "league":     data.get("leagueName"),
            "season":     data.get("season"),
            "status":     data.get("status"),
            "match_date": data.get("matchDate"),

            # Placar
            "score_home": score.get("home"),
            "score_away": score.get("away"),
            "ht_home":    halftime.get("home"),
            "ht_away":    halftime.get("away"),

            # Estatísticas
            "corners_home":    corners.get("home"),
            "corners_away":    corners.get("away"),
            "yellow_home":     yellows.get("home"),
            "yellow_away":     yellows.get("away"),
            "red_home":        reds.get("home"),
            "red_away":        reds.get("away"),
            "shots_home":      shots.get("home"),
            "shots_away":      shots.get("away"),
            "possession_home": possession.get("home"),
            "possession_away": possession.get("away"),

            # Gols
            "goals_count": len(goals_raw),
            "goals_raw":   goals_raw,
        }
        records.append(record)

    df = pd.DataFrame(records)

    if not df.empty and "match_date" in df.columns:
        df["match_date"] = df["match_date"].apply(
            lambda ts: ts.ToDatetime() if hasattr(ts, "ToDatetime") else ts
        )
        df["match_date"] = pd.to_datetime(df["match_date"], utc=True, errors="coerce")

    return df


# ─────────────────────────────────────────────
# 3. LIMPEZA DE DADOS
# ─────────────────────────────────────────────

def clean_matches(df: pd.DataFrame) -> pd.DataFrame:
    """
    Trata nulos, tipos incorretos e cria colunas derivadas.
    """
    if df.empty:
        return df

    df = df.copy()
    df = df.dropna(subset=["match_id"])

    stat_cols = [
        "corners_home", "corners_away",
        "yellow_home",  "yellow_away",
        "red_home",     "red_away",
        "shots_home",   "shots_away",
        "possession_home", "possession_away",
    ]
    df[stat_cols] = df[stat_cols].fillna(0).astype(int)

    score_cols = ["score_home", "score_away", "ht_home", "ht_away"]
    df[score_cols] = df[score_cols].fillna(0).astype(int)

    df["season"]      = df["season"].fillna(0).astype(int)
    df["goals_count"] = df["goals_count"].fillna(0).astype(int)

    df["result"] = df.apply(
        lambda r: "W" if r["score_home"] > r["score_away"]
        else ("D" if r["score_home"] == r["score_away"] else "L"),
        axis=1,
    )

    df["total_corners"] = df["corners_home"] + df["corners_away"]
    df["total_yellows"] = df["yellow_home"]  + df["yellow_away"]
    df["total_reds"]    = df["red_home"]     + df["red_away"]
    df["total_goals"]   = df["score_home"]   + df["score_away"]

    df["comeback"] = (
        (df["ht_home"] < df["ht_away"]) & (df["score_home"] > df["score_away"])
    ) | (
        (df["ht_home"] > df["ht_away"]) & (df["score_home"] < df["score_away"])
    )

    return df.reset_index(drop=True)


# ─────────────────────────────────────────────
# 4. DETECÇÃO DE OUTLIERS (IQR)
# ─────────────────────────────────────────────

def detect_outliers(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Detecta outliers usando o método IQR."""
    q1 = df[column].quantile(0.25)
    q3 = df[column].quantile(0.75)
    iqr = q3 - q1

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    outliers = df[(df[column] < lower) | (df[column] > upper)].copy()

    print(f"\n📊 Outliers em '{column}':")
    print(f"   Q1={q1:.1f} | Q3={q3:.1f} | IQR={iqr:.1f}")
    print(f"   Limite inferior: {lower:.1f} | Limite superior: {upper:.1f}")
    print(f"   {len(outliers)} outliers encontrados de {len(df)} partidas ({len(outliers)/len(df)*100:.1f}%)")

    return outliers


# ─────────────────────────────────────────────
# 5. ANÁLISE ESTATÍSTICA
# ─────────────────────────────────────────────

def run_analysis(df: pd.DataFrame) -> dict:
    """Calcula e exibe estatísticas básicas do Brasileirão."""
    print("\n" + "═" * 58)
    print("  📈  ANÁLISE DE PARTIDAS — BRASILEIRÃO [LEGADO]")
    print("═" * 58)

    finished = df[df["status"] == "FT"].copy()

    if finished.empty:
        print("Nenhuma partida encerrada encontrada.")
        return {}

    print(f"\n✅ Partidas encerradas analisadas: {len(finished)}")

    avg_c_home = finished["corners_home"].mean()
    avg_c_away = finished["corners_away"].mean()
    print(f"\n⚽ ESCANTEIOS")
    print(f"   Mandante — média: {avg_c_home:.2f} | mediana: {finished['corners_home'].median():.1f} | max: {finished['corners_home'].max()}")
    print(f"   Visitante — média: {avg_c_away:.2f} | mediana: {finished['corners_away'].median():.1f} | max: {finished['corners_away'].max()}")

    print(f"\n🏠 Top 5 mandantes (média de escanteios):")
    top_home_corners = (
        finished.groupby("home_team")["corners_home"]
        .agg(["mean", "count"])
        .query("count >= 3")
        .sort_values("mean", ascending=False)
        .head(5)
    )
    for team, row in top_home_corners.iterrows():
        print(f"   {team:<25} {row['mean']:.2f} escanteios ({int(row['count'])} jogos)")

    result_counts = finished["result"].value_counts()
    total = len(finished)
    print(f"\n🏆 RESULTADOS (ponto de vista do mandante):")
    for r, label in [("W", "Vitória mandante"), ("D", "Empate"), ("L", "Derrota mandante")]:
        n = result_counts.get(r, 0)
        print(f"   {label:<22} {n:>3} ({n/total*100:.1f}%)")

    avg_goals = finished["total_goals"].mean()
    print(f"\n⚽ GOLS")
    print(f"   Média por partida: {avg_goals:.2f}")
    print(f"   Jogos sem gols (0x0): {len(finished[finished['total_goals'] == 0])}")

    print(f"\n🟨 CARTÕES")
    print(f"   Amarelos — média por partida: {finished['total_yellows'].mean():.2f}")
    print(f"   Vermelhos — média por partida: {finished['total_reds'].mean():.2f}")

    corr_corners_goals = finished[["corners_home", "score_home"]].corr().iloc[0, 1]
    corr_possession_goals = finished[["possession_home", "score_home"]].corr().iloc[0, 1]
    print(f"\n📐 CORRELAÇÕES (mandante)")
    print(f"   Escanteios × Gols:    {corr_corners_goals:.3f}")
    print(f"   Posse    × Gols:      {corr_possession_goals:.3f}")

    comebacks = finished["comeback"].sum()
    print(f"\n🔄 Viradas de resultado: {comebacks} ({comebacks/total*100:.1f}% das partidas)")

    detect_outliers(finished, "total_corners")
    print("\n" + "═" * 58)

    return {
        "avg_corners_home": round(avg_c_home, 2),
        "avg_corners_away": round(avg_c_away, 2),
        "avg_goals_per_match": round(avg_goals, 2),
        "corr_corners_goals": round(corr_corners_goals, 3),
        "total_matches_analyzed": len(finished),
    }


# ─────────────────────────────────────────────
# 6. EXECUÇÃO PRINCIPAL
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("🔌 Conectando ao Firestore...")
    client = get_firestore_client()

    print("📥 Buscando partidas...")
    df_raw = fetch_matches(client, season_filter=2025)
    print(f"   {len(df_raw)} documentos carregados.")

    if df_raw.empty:
        print("⚠️  Nenhum dado encontrado. Verifique se o Cron já rodou.")
        exit(0)

    print("🧹 Limpando dados...")
    df_clean = clean_matches(df_raw)

    summary = run_analysis(df_clean)

    output_dir = "analysis/output"
    os.makedirs(output_dir, exist_ok=True)

    csv_path = f"{output_dir}/matches_clean_{datetime.today().strftime('%Y%m%d')}.csv"
    df_clean.drop(columns=["goals_raw"]).to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n💾 CSV exportado: {csv_path}")

    json_path = f"{output_dir}/summary_{datetime.today().strftime('%Y%m%d')}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"📄 Resumo JSON: {json_path}")
