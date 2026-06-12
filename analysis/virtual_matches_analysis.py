# analysis/virtual_matches_analysis.py
"""
Script de análise de dados de Futebol Virtual - Bet365.
Lê dados da coleção 'virtual_matches' (e 'league_meta') do Firestore,
limpa e calcula estatísticas completas com Pandas.

Dependências:
    pip install google-cloud-firestore pandas numpy python-dotenv

Variáveis de ambiente necessárias:
    FIREBASE_SERVICE_ACCOUNT='{...json completo...}'

    O script busca o .env.local automaticamente em:
      1. Diretório atual
      2. Dois níveis acima (raiz do projeto)
"""

import os
import json
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import firestore
from google.oauth2 import service_account

# ─────────────────────────────────────────────
# 0. CARREGAR .env.local (busca em múltiplos locais)
# ─────────────────────────────────────────────

def _load_env() -> None:
    """
    Tenta carregar .env.local do diretório atual e, se não encontrar,
    sobe até 3 níveis na árvore de diretórios.
    """
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / ".env.local",
        script_dir.parent / ".env.local",
        script_dir.parent.parent / ".env.local",
        script_dir.parent.parent.parent / ".env.local",
        Path.cwd() / ".env.local",
    ]
    for path in candidates:
        if path.exists():
            load_dotenv(path)
            print(f"🔐 .env.local carregado de: {path}")
            return
    print("⚠️  .env.local não encontrado — certifique-se de que FIREBASE_SERVICE_ACCOUNT está no ambiente.")

_load_env()


# ─────────────────────────────────────────────
# 1. CONEXÃO COM FIRESTORE
# ─────────────────────────────────────────────

def get_firestore_client() -> firestore.Client:
    """Cria cliente Firestore a partir da variável de ambiente."""
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
# 2. EXPORTAR COLEÇÕES PARA DATAFRAME
# ─────────────────────────────────────────────

def _to_float(value) -> float | None:
    """Converte string de odd para float, retorna None em caso de falha."""
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def _implied_prob(odd: float | None) -> float | None:
    """Converte odd decimal em probabilidade implícita (%)."""
    if odd is None or odd <= 0:
        return None
    return round(1 / odd * 100, 2)


def fetch_virtual_matches(
    client: firestore.Client,
    league_filter: str | None = None,
    type_filter: str | None = None,  # "history" ou "next"
) -> pd.DataFrame:
    """
    Exporta a coleção 'virtual_matches' para um DataFrame flat.

    Args:
        client: Cliente Firestore autenticado.
        league_filter: Filtrar por liga (ex: 'euro', 'copa'). None = todas.
        type_filter: Filtrar por tipo ('history' ou 'next'). None = todos.

    Returns:
        DataFrame com colunas achatadas.
    """
    query = client.collection("virtual_matches")

    if league_filter:
        query = query.where("league", "==", league_filter)
    if type_filter:
        query = query.where("type", "==", type_filter)

    docs = list(query.stream())
    records = []

    for doc in docs:
        data = doc.to_dict()
        if not data:
            continue

        score    = data.get("score", {}) or {}
        score_ht = data.get("scoreHt", {}) or {}
        odds     = data.get("odds", {}) or {}

        record = {
            # Identificação
            "doc_id":        doc.id,
            "match_id":      data.get("matchId"),
            "league":        data.get("league"),
            "type":          data.get("type"),
            "home_team":     data.get("homeTeam"),
            "away_team":     data.get("awayTeam"),

            # Horário
            "match_time":    data.get("matchTime"),
            "hour":          data.get("hour"),
            "minute":        data.get("minute"),
            "match_created": data.get("matchCreatedAt"),

            # Sincronização
            "last_synced_at": (
                data["lastSyncedAt"].ToDatetime().isoformat()
                if data.get("lastSyncedAt") and hasattr(data["lastSyncedAt"], "ToDatetime")
                else None
            ),

            # Placar
            "score_home":    score.get("home", 0),
            "score_away":    score.get("away", 0),
            "ht_home":       score_ht.get("home", 0),
            "ht_away":       score_ht.get("away", 0),

            # Marcadores
            "first_scorer":  data.get("firstScorer"),
            "last_scorer":   data.get("lastScorer"),
            "ht_ft_winner":  data.get("htFtWinner"),

            # Odds — resultado final
            "odd_home":      _to_float(odds.get("odd_resultado_final_casa")),
            "odd_draw":      _to_float(odds.get("odd_resultado_final_empate")),
            "odd_away":      _to_float(odds.get("odd_resultado_final_fora")),

            # Odds — over/under
            "odd_over_0_5":  _to_float(odds.get("odd_over_0.5")),
            "odd_over_1_5":  _to_float(odds.get("odd_over_1.5")),
            "odd_over_2_5":  _to_float(odds.get("odd_over_2.5")),
            "odd_over_3_5":  _to_float(odds.get("odd_over_3.5")),
            "odd_under_2_5": _to_float(odds.get("odd_under_2.5")),
            "odd_under_3_5": _to_float(odds.get("odd_under_3.5")),

            # Odds — ambas marcam
            "odd_btts_sim":  _to_float(odds.get("odd_ambas_sim")),
            "odd_btts_nao":  _to_float(odds.get("odd_ambas_nao")),

            # Odds — intervalo (HT)
            "odd_ht_home":   _to_float(odds.get("odd_intervalo_resultado_casa")),
            "odd_ht_draw":   _to_float(odds.get("odd_intervalo_resultado_empate")),
            "odd_ht_away":   _to_float(odds.get("odd_intervalo_resultado_fora")),

            # Odds — dupla hipótese
            "odd_dc_1x":     _to_float(odds.get("odd_dupla_hipotese_casa_ou_empate")),
            "odd_dc_x2":     _to_float(odds.get("odd_dupla_hipotese_fora_ou_empate")),
            "odd_dc_12":     _to_float(odds.get("odd_dupla_hipotese_casa_ou_fora")),

            # Odds — handicap asiático
            "odd_hc_asia_home": _to_float(odds.get("odd_handicap_asiatico_casa")),
            "odd_hc_asia_away": _to_float(odds.get("odd_handicap_asiatico_fora")),

            # Odds — gols exatos
            "odd_gols_0":    _to_float(odds.get("odd_total_gols_extatos_0")),
            "odd_gols_1":    _to_float(odds.get("odd_total_gols_extatos_1")),
            "odd_gols_2":    _to_float(odds.get("odd_total_gols_extatos_2")),
            "odd_gols_3":    _to_float(odds.get("odd_total_gols_extatos_3")),
        }
        records.append(record)

    df = pd.DataFrame(records)

    if not df.empty and "match_created" in df.columns:
        df["match_created"] = pd.to_datetime(
            df["match_created"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
        )

    return df


def fetch_league_meta(client: firestore.Client) -> pd.DataFrame:
    """
    Exporta a coleção 'league_meta' para um DataFrame.
    Mostra status da última sincronização por liga.
    """
    docs = list(client.collection("league_meta").stream())
    records = []
    for doc in docs:
        data = doc.to_dict()
        if not data:
            continue
        stats = data.get("lastSyncStats", {}) or {}
        records.append({
            "league": data.get("league", doc.id),
            "lastSyncedAt": (
                data["lastSyncedAt"].ToDatetime().isoformat()
                if data.get("lastSyncedAt") and hasattr(data["lastSyncedAt"], "ToDatetime")
                else None
            ),
            "apiLastUpdated": data.get("apiLastUpdated"),
            "synced":  stats.get("synced"),
            "created": stats.get("created"),
            "updated": stats.get("updated"),
        })
    return pd.DataFrame(records)


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

    # Placar
    score_cols = ["score_home", "score_away", "ht_home", "ht_away"]
    df[score_cols] = df[score_cols].fillna(0).astype(int)

    # ── Colunas derivadas ──

    # Resultado final (ponto de vista do mandante)
    df["result"] = df.apply(
        lambda r: "W" if r["score_home"] > r["score_away"]
        else ("D" if r["score_home"] == r["score_away"] else "L"),
        axis=1,
    )

    # Resultado no intervalo
    df["ht_result"] = df.apply(
        lambda r: "W" if r["ht_home"] > r["ht_away"]
        else ("D" if r["ht_home"] == r["ht_away"] else "L"),
        axis=1,
    )

    # Total de gols
    df["total_goals"]    = df["score_home"] + df["score_away"]
    df["total_goals_ht"] = df["ht_home"] + df["ht_away"]
    df["goals_2nd_half"] = df["total_goals"] - df["total_goals_ht"]

    # Flags de resultado
    df["btts"]       = (df["score_home"] > 0) & (df["score_away"] > 0)
    df["over_0_5"]   = df["total_goals"] >= 1
    df["over_1_5"]   = df["total_goals"] >= 2
    df["over_2_5"]   = df["total_goals"] >= 3
    df["over_3_5"]   = df["total_goals"] >= 4
    df["over_0_5_ht"] = df["total_goals_ht"] >= 1

    # Virada de resultado
    df["comeback"] = (
        ((df["ht_home"] < df["ht_away"]) & (df["score_home"] > df["score_away"])) |
        ((df["ht_home"] > df["ht_away"]) & (df["score_home"] < df["score_away"]))
    )

    # Código HT→FT (ex: "D-W" = empate no HT, vitória no FT)
    df["ht_ft_code"] = df["ht_result"] + "-" + df["result"]

    # Probabilidades implícitas das odds
    for col, odd_col in [
        ("prob_home", "odd_home"),
        ("prob_draw", "odd_draw"),
        ("prob_away", "odd_away"),
        ("prob_btts",  "odd_btts_sim"),
        ("prob_over_2_5", "odd_over_2_5"),
    ]:
        if odd_col in df.columns:
            df[col] = df[odd_col].apply(_implied_prob)

    # Margem do bookmaker (over-round) para 1X2
    mask = df[["odd_home", "odd_draw", "odd_away"]].notna().all(axis=1)
    df.loc[mask, "overround_1x2"] = (
        df.loc[mask, "odd_home"].apply(lambda x: 1/x if x else None) +
        df.loc[mask, "odd_draw"].apply(lambda x: 1/x if x else None) +
        df.loc[mask, "odd_away"].apply(lambda x: 1/x if x else None)
    ).round(4)

    return df.reset_index(drop=True)


# ─────────────────────────────────────────────
# 4. DETECÇÃO DE OUTLIERS (IQR)
# ─────────────────────────────────────────────

def detect_outliers(df: pd.DataFrame, column: str) -> pd.DataFrame:
    q1 = df[column].quantile(0.25)
    q3 = df[column].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    outliers = df[(df[column] < lower) | (df[column] > upper)].copy()

    print(f"\n📊 Outliers em '{column}':")
    print(f"   Q1={q1:.2f} | Q3={q3:.2f} | IQR={iqr:.2f}")
    print(f"   Faixa normal: [{lower:.2f}, {upper:.2f}]")
    if len(df) > 0:
        print(f"   {len(outliers)} outliers de {len(df)} partidas ({len(outliers)/len(df)*100:.1f}%)")

    return outliers


# ─────────────────────────────────────────────
# 5. ANÁLISE ESTATÍSTICA
# ─────────────────────────────────────────────

def run_analysis(df: pd.DataFrame) -> dict:
    """
    Calcula e exibe estatísticas completas das partidas históricas.
    Retorna dicionário com os principais indicadores.
    """
    print("\n" + "═" * 68)
    print("  ⚽  ANÁLISE — FUTEBOL VIRTUAL BET365")
    print("═" * 68)

    history = df[df["type"] == "history"].copy()

    if history.empty:
        print("Nenhuma partida histórica encontrada.")
        return {}

    total = len(history)
    print(f"\n✅ Partidas históricas analisadas: {total}")
    print(f"   Ligas: {', '.join(sorted(history['league'].dropna().unique()))}")

    # ── Gols ──
    avg_goals     = history["total_goals"].mean()
    over_2_5_rate = history["over_2_5"].mean()
    btts_rate     = history["btts"].mean()
    over_1_5_rate = history["over_1_5"].mean()
    over_3_5_rate = history["over_3_5"].mean()

    print(f"\n⚽ GOLS")
    print(f"   Média por partida:     {avg_goals:.2f}")
    print(f"   Over 0.5 (%):          {history['over_0_5'].mean()*100:.1f}%")
    print(f"   Over 1.5 (%):          {over_1_5_rate*100:.1f}%")
    print(f"   Over 2.5 (%):          {over_2_5_rate*100:.1f}%")
    print(f"   Over 3.5 (%):          {over_3_5_rate*100:.1f}%")
    print(f"   Ambas marcam (%):      {btts_rate*100:.1f}%")
    print(f"   Jogos 0x0:             {len(history[history['total_goals'] == 0])}")
    print(f"   Gols no 1T (média):    {history['total_goals_ht'].mean():.2f}")
    print(f"   Gols no 2T (média):    {history['goals_2nd_half'].mean():.2f}")
    print(f"   Over 0.5 HT (%):       {history['over_0_5_ht'].mean()*100:.1f}%")

    # ── Resultados ──
    result_counts = history["result"].value_counts()
    print(f"\n🏆 RESULTADOS (ponto de vista do mandante)")
    for r, label in [("W", "Vitória mandante"), ("D", "Empate"), ("L", "Derrota mandante")]:
        n = result_counts.get(r, 0)
        print(f"   {label:<22} {n:>4} ({n/total*100:.1f}%)")

    # ── Resultados por liga ──
    if history["league"].nunique() > 1:
        print(f"\n📊 RESULTADOS POR LIGA")
        league_results = (
            history.groupby("league")["result"]
            .value_counts(normalize=True)
            .mul(100)
            .round(1)
            .unstack(fill_value=0)
            .reindex(columns=["W", "D", "L"], fill_value=0)
        )
        for league, row in league_results.iterrows():
            n_league = len(history[history["league"] == league])
            print(f"   {league:<12} W={row.get('W',0):.1f}% D={row.get('D',0):.1f}% L={row.get('L',0):.1f}%  ({n_league} partidas)")

    # ── Over/Under por liga ──
    print(f"\n📈 OVER/UNDER POR LIGA")
    for league in sorted(history["league"].dropna().unique()):
        sub = history[history["league"] == league]
        print(
            f"   {league:<12} "
            f"O1.5={sub['over_1_5'].mean()*100:.0f}% "
            f"O2.5={sub['over_2_5'].mean()*100:.0f}% "
            f"O3.5={sub['over_3_5'].mean()*100:.0f}% "
            f"BTTS={sub['btts'].mean()*100:.0f}%"
        )

    # ── HT/FT ──
    print(f"\n🕐 RESULTADO NO INTERVALO")
    ht_results = history["ht_result"].value_counts()
    for r, label in [("W", "Mandante vencendo"), ("D", "Empatado"), ("L", "Visitante vencendo")]:
        n = ht_results.get(r, 0)
        print(f"   {label:<24} {n:>4} ({n/total*100:.1f}%)")

    print(f"\n🔄 VIRADAS DE RESULTADO")
    comebacks = history["comeback"].sum()
    print(f"   Total de viradas: {comebacks} ({comebacks/total*100:.1f}%)")

    print(f"\n🔢 PADRÕES HT → FT (top 6)")
    ht_ft_dist = history["ht_ft_code"].value_counts().head(6)
    for pattern, count in ht_ft_dist.items():
        print(f"   {pattern:<6} {count:>4} ({count/total*100:.1f}%)")

    # ── Times mais frequentes ──
    print(f"\n🏠 TOP 5 — Mandantes mais frequentes")
    top_home = history["home_team"].value_counts().head(5)
    for team, count in top_home.items():
        wins = len(history[(history["home_team"] == team) & (history["result"] == "W")])
        print(f"   {team:<22} {count:>4} jogos | {wins} vitórias ({wins/count*100:.1f}%)")

    # ── Primeiros marcadores ──
    if "first_scorer" in history.columns and history["first_scorer"].notna().any():
        print(f"\n⚡ TOP 5 — Primeiros a marcar")
        top_first = history["first_scorer"].dropna().value_counts().head(5)
        for team, count in top_first.items():
            print(f"   {team:<22} {count:>4} ({count/total*100:.1f}%)")

    # ── Análise de Odds ──
    odds_available = history["odd_home"].notna().sum()
    if odds_available > 0:
        print(f"\n💰 ANÁLISE DE ODDS (baseada em {odds_available} partidas com odds)")

        # Probabilidades implícitas médias
        print(f"\n   Probabilidades implícitas médias:")
        print(f"   Casa:     {history['prob_home'].mean():.1f}%")
        print(f"   Empate:   {history['prob_draw'].mean():.1f}%")
        print(f"   Fora:     {history['prob_away'].mean():.1f}%")
        if "prob_over_2_5" in history.columns:
            print(f"   Over 2.5: {history['prob_over_2_5'].mean():.1f}%")
        if "prob_btts" in history.columns:
            print(f"   BTTS:     {history['prob_btts'].mean():.1f}%")

        # Margem do bookmaker
        if "overround_1x2" in history.columns:
            avg_margin = (history["overround_1x2"].mean() - 1) * 100
            print(f"\n   Margem média do bookmaker (1X2): {avg_margin:.2f}%")

        # Comparação odd implícita vs resultado real
        print(f"\n   Calibração das odds vs resultados reais:")
        fav_correct = 0
        fav_total = 0
        for _, row in history.dropna(subset=["odd_home", "odd_draw", "odd_away"]).iterrows():
            odds_dict = {"W": row["odd_home"], "D": row["odd_draw"], "L": row["odd_away"]}
            fav = min(odds_dict, key=odds_dict.get)
            fav_total += 1
            if row["result"] == fav:
                fav_correct += 1
        if fav_total > 0:
            print(f"   Favorito (menor odd) ganhou: {fav_correct}/{fav_total} ({fav_correct/fav_total*100:.1f}%)")

        # Odds médias por liga
        print(f"\n   Odds médias por liga:")
        for league in sorted(history["league"].dropna().unique()):
            sub = history[(history["league"] == league) & history["odd_home"].notna()]
            if sub.empty:
                continue
            print(
                f"   {league:<12} "
                f"Casa={sub['odd_home'].mean():.2f} "
                f"Emp={sub['odd_draw'].mean():.2f} "
                f"Fora={sub['odd_away'].mean():.2f} "
                f"O2.5={sub['odd_over_2_5'].mean():.2f}"
            )

    # ── Outliers ──
    detect_outliers(history, "total_goals")

    print("\n" + "═" * 68)

    return {
        "total_matches_analyzed": total,
        "avg_goals_per_match": round(avg_goals, 2),
        "over_2_5_rate": round(over_2_5_rate, 4),
        "btts_rate": round(btts_rate, 4),
        "home_win_rate": round(result_counts.get("W", 0) / total, 4),
        "draw_rate": round(result_counts.get("D", 0) / total, 4),
        "away_win_rate": round(result_counts.get("L", 0) / total, 4),
        "comeback_rate": round(comebacks / total, 4),
    }


def run_next_matches_report(df: pd.DataFrame) -> None:
    """
    Exibe relatório dos próximos jogos agendados.
    """
    next_m = df[df["type"] == "next"].copy()

    print("\n" + "═" * 68)
    print("  🗓️  PRÓXIMAS PARTIDAS AGENDADAS")
    print("═" * 68)

    if next_m.empty:
        print("  Nenhum próximo jogo encontrado.")
        return

    print(f"\n  Total de próximos jogos: {len(next_m)}")

    for league in sorted(next_m["league"].dropna().unique()):
        sub = next_m[next_m["league"] == league].copy()
        print(f"\n  📋 {league.upper()} ({len(sub)} jogos)")
        print(f"  {'Horário':<8} {'Mandante':<22} {'Visitante':<22} {'Casa':>6} {'Emp':>6} {'Fora':>6}")
        print("  " + "-" * 66)

        sub_sorted = sub.sort_values("match_time", na_position="last")
        for _, row in sub_sorted.iterrows():
            home_odd = f"{row['odd_home']:.2f}" if pd.notna(row.get("odd_home")) else "  -  "
            draw_odd = f"{row['odd_draw']:.2f}" if pd.notna(row.get("odd_draw")) else "  -  "
            away_odd = f"{row['odd_away']:.2f}" if pd.notna(row.get("odd_away")) else "  -  "
            print(
                f"  {str(row.get('match_time', '')):<8} "
                f"{str(row.get('home_team', '')):<22} "
                f"{str(row.get('away_team', '')):<22} "
                f"{home_odd:>6} {draw_odd:>6} {away_odd:>6}"
            )

    print("═" * 68)


def run_league_meta_report(meta_df: pd.DataFrame) -> None:
    """Exibe status da última sincronização por liga."""
    if meta_df.empty:
        print("\n⚠️  Nenhum metadado de liga encontrado (league_meta vazia).")
        return

    print("\n" + "═" * 68)
    print("  🔄  STATUS DE SINCRONIZAÇÃO POR LIGA")
    print("═" * 68)
    print(f"\n  {'Liga':<12} {'Última sync':<25} {'API updated':<22} {'Sinc':>5} {'New':>5} {'Upd':>5}")
    print("  " + "-" * 76)
    for _, row in meta_df.iterrows():
        print(
            f"  {str(row.get('league', '')):<12} "
            f"{str(row.get('lastSyncedAt', 'n/a'))[:22]:<25} "
            f"{str(row.get('apiLastUpdated', 'n/a'))[:20]:<22} "
            f"{str(row.get('synced', '-')):>5} "
            f"{str(row.get('created', '-')):>5} "
            f"{str(row.get('updated', '-')):>5}"
        )
    print("═" * 68)


# ─────────────────────────────────────────────
# 6. EXECUÇÃO PRINCIPAL
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Filtros opcionais via argumento de linha de comando:
    # python virtual_matches_analysis.py euro
    league_arg = sys.argv[1] if len(sys.argv) > 1 else None

    print("🔌 Conectando ao Firestore...")
    client = get_firestore_client()

    print("📥 Buscando metadados de ligas...")
    meta_df = fetch_league_meta(client)
    run_league_meta_report(meta_df)

    print("\n📥 Buscando partidas virtuais...")
    df_raw = fetch_virtual_matches(client, league_filter=league_arg)
    print(f"   {len(df_raw)} documentos carregados.")

    if df_raw.empty:
        print("⚠️  Nenhum dado encontrado. Verifique se o sync já rodou.")
        exit(0)

    print("🧹 Limpando dados...")
    df_clean = clean_matches(df_raw)

    # Análise histórica
    summary = run_analysis(df_clean)

    # Relatório de próximos jogos
    run_next_matches_report(df_clean)

    # ── Exportações ──
    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.today().strftime("%Y%m%d")
    suffix = f"_{league_arg}" if league_arg else ""

    # CSV histórico
    hist_df = df_clean[df_clean["type"] == "history"].copy()
    csv_hist = output_dir / f"virtual_matches_history{suffix}_{today}.csv"
    hist_df.to_csv(csv_hist, index=False, encoding="utf-8-sig")
    print(f"\n💾 CSV histórico exportado: {csv_hist}")

    # CSV próximos jogos
    next_df = df_clean[df_clean["type"] == "next"].copy()
    if not next_df.empty:
        csv_next = output_dir / f"virtual_matches_next{suffix}_{today}.csv"
        next_df.to_csv(csv_next, index=False, encoding="utf-8-sig")
        print(f"💾 CSV próximos jogos exportado: {csv_next}")

    # Resumo JSON
    json_path = output_dir / f"summary{suffix}_{today}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"📄 Resumo JSON: {json_path}")

    print(f"\n✅ Análise concluída!")
