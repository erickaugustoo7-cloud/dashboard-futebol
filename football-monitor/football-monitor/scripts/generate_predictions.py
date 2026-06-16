# -*- coding: utf-8 -*-
"""
=============================================================
  GENERATE PREDICTIONS v3.0 — Football Monitor
=============================================================
Motor de previsões automáticas aprimorado com:
  - Últimos 10 jogos REAIS de cada time (vs qualquer adversário)
  - Confrontos diretos H2H completos
  - Análise de insights gerada pela IA (Gemini)
  - Poisson + ELO + Forma com peso temporal

Como rodar:
  python scripts/generate_predictions.py
  python scripts/generate_predictions.py --days 3
  python scripts/generate_predictions.py --league 71
  python scripts/generate_predictions.py --no-ai   # desativa Gemini
=============================================================
"""

import sys
import io
import os
import json
import time
import re
import argparse
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
from scipy.stats import poisson as scipy_poisson
from dotenv import load_dotenv
from supabase_client import supabase_client
# tensorflow e pickle são importados condicionalmente no bloco --use-nn

# Carrega .env.local para obter GEMINI_API_KEY
try:
    base_dir = os.path.dirname(__file__)
except NameError:
    base_dir = os.getcwd()
env_path = os.path.join(base_dir, "..", ".env.local")
load_dotenv(dotenv_path=env_path)

# ──────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ──────────────────────────────────────────────────────────────
MODEL_VERSION   = "v3.0-ai"
MAX_GOALS       = 7
BATCH_SIZE      = 20
DEFAULT_DAYS    = 7
FORM_WINDOW     = 10   # Últimos N jogos de cada time para análise de forma
H2H_LIMIT       = 10  # Últimos N confrontos diretos

GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
AI_MODEL      = "llama-3.1-8b-instant"  # Limite 500K tokens/dia vs 100K do 70b
AI_DELAY      = 3.0   # 3s entre jogos para respeitar o rate limit do Groq free tier (30 RPM)
AI_MAX_RETRY  = 3

# Globais para o Modelo Neural
USE_NN = False
model = None
scaler = None


# ──────────────────────────────────────────────────────────────
# CLIENTE GROQ (opcional)
# ──────────────────────────────────────────────────────────────
def get_ai_client():
    """Inicializa o cliente Groq se a chave estiver disponível."""
    if not GROQ_API_KEY:
        return None
    try:
        from groq import Groq
        return Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        print(f"    [IA] Aviso: Nao foi possivel inicializar Groq: {e}")
        return None

# Global placeholders for NN model and scaler
model = None
scaler = None


# ──────────────────────────────────────────────────────────────
# FUNÇÕES DE BUSCA NO SUPABASE
# ──────────────────────────────────────────────────────────────

def fetch_upcoming_matches(days: int, league_id: int = None) -> list:
    """Busca jogos agendados (NS) nos próximos N dias."""
    print(f"[1/6] Buscando jogos agendados para os proximos {days} dias...")
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)

    q = supabase_client.table("matches") \
        .select("fixture_id,league_id,league_name,season,date,home_team_id,home_team_name,away_team_id,away_team_name") \
        .eq("status", "NS") \
        .gte("date", now.isoformat()) \
        .lte("date", end.isoformat()) \
        .order("date")

    if league_id:
        q = q.eq("league_id", league_id)

    result = q.execute()
    matches = result.data or []
    print(f"    -> {len(matches)} jogos encontrados.")
    return matches


def fetch_recent_matches(team_id: int, limit: int = FORM_WINDOW) -> list:
    """
    Busca os últimos N jogos FINALIZADOS de um time contra QUALQUER adversário.
    Retorna dados ricos: gols, chutes, posse, cartões, data.
    """
    result = supabase_client.table("matches") \
        .select(
            "date,home_team_id,away_team_id,goals_home,goals_away,"
            "home_shots,away_shots,home_sog,away_sog,"
            "home_possession,away_possession,home_corners,away_corners,"
            "home_yellow_cards,away_yellow_cards"
        ) \
        .eq("status", "FT") \
        .or_(f"home_team_id.eq.{team_id},away_team_id.eq.{team_id}") \
        .order("date", desc=True) \
        .limit(limit) \
        .execute()
    return result.data or []


def fetch_h2h(home_id: int, away_id: int, limit: int = H2H_LIMIT) -> list:
    """Busca os últimos N confrontos diretos entre os dois times."""
    result = supabase_client.table("matches") \
        .select("date,home_team_id,goals_home,goals_away") \
        .eq("status", "FT") \
        .or_(f"and(home_team_id.eq.{home_id},away_team_id.eq.{away_id}),and(home_team_id.eq.{away_id},away_team_id.eq.{home_id})") \
        .order("date", desc=True) \
        .limit(limit) \
        .execute()
    return result.data or []


def fetch_league_stats(league_id: int, season: int) -> dict:
    """Busca médias globais da liga do cache."""
    result = supabase_client.table("league_stats_cache") \
        .select("*") \
        .eq("league_id", league_id) \
        .eq("season", season) \
        .limit(1) \
        .execute()
    return result.data[0] if result.data else {}


def fetch_team_stats_cache(team_id: int, league_id: int, season: int) -> dict:
    """Busca ELO e forças de ataque/defesa do cache."""
    result = supabase_client.table("team_stats_cache") \
        .select("elo_rating,attack_strength_home,defense_strength_home,attack_strength_away,defense_strength_away,total_matches") \
        .eq("team_id", team_id) \
        .eq("league_id", league_id) \
        .eq("season", season) \
        .limit(1) \
        .execute()
    return result.data[0] if result.data else {}


# ──────────────────────────────────────────────────────────────
# ANÁLISE DE FORMA REAL (últimos 10 jogos)
# ──────────────────────────────────────────────────────────────

def compute_real_form(matches: list, team_id: int) -> dict:
    """
    Calcula métricas reais de forma a partir dos últimos N jogos.
    Aplica peso temporal: jogos mais recentes valem mais.
    """
    if not matches:
        return {}

    n = len(matches)
    # Pesos decrescentes: jogo mais recente = peso máximo
    weights = [1.0 / (i + 1) for i in range(n)]
    total_w = sum(weights)

    gols_pro_list   = []
    gols_contra_list = []
    results         = []
    shots_list      = []
    possession_list = []
    corners_list    = []
    clean_sheets    = 0
    btts_count      = 0
    over25_count    = 0

    for i, m in enumerate(matches):
        is_home = (m["home_team_id"] == team_id)
        gf = (m["goals_home"] or 0) if is_home else (m["goals_away"] or 0)
        ga = (m["goals_away"] or 0) if is_home else (m["goals_home"] or 0)
        total_goals = gf + ga

        gols_pro_list.append(gf)
        gols_contra_list.append(ga)

        if gf > ga:
            results.append("W")
        elif gf < ga:
            results.append("L")
        else:
            results.append("D")

        if ga == 0:
            clean_sheets += 1
        if gf > 0 and ga > 0:
            btts_count += 1
        if total_goals > 2.5:
            over25_count += 1

        # Estatísticas de jogo (quando disponíveis)
        shots = (m["home_shots"] if is_home else m["away_shots"]) or None
        poss  = (m["home_possession"] if is_home else m["away_possession"]) or None
        crnr  = (m["home_corners"] if is_home else m["away_corners"]) or None
        if shots is not None:
            shots_list.append(shots)
        if poss is not None:
            possession_list.append(poss)
        if crnr is not None:
            corners_list.append(crnr)

    # Médias ponderadas pelo tempo (mais recente pesa mais)
    avg_gols_pro_w   = sum(gols_pro_list[i] * weights[i] for i in range(n)) / total_w
    avg_gols_contra_w = sum(gols_contra_list[i] * weights[i] for i in range(n)) / total_w

    # Médias simples
    avg_gols_pro   = sum(gols_pro_list) / n
    avg_gols_contra = sum(gols_contra_list) / n
    win_rate       = results.count("W") / n
    draw_rate      = results.count("D") / n
    loss_rate      = results.count("L") / n

    # Pontos
    pts = results.count("W") * 3 + results.count("D")

    # Sequência de resultados (da mais recente para mais antiga)
    sequence = "".join(results)

    return {
        "n":                n,
        "results":          results,
        "sequence":         sequence,
        "points":           pts,
        "win_rate":         round(win_rate, 3),
        "draw_rate":        round(draw_rate, 3),
        "loss_rate":        round(loss_rate, 3),
        "avg_goals_scored": round(avg_gols_pro, 2),
        "avg_goals_conceded": round(avg_gols_contra, 2),
        "avg_goals_scored_weighted":   round(avg_gols_pro_w, 2),
        "avg_goals_conceded_weighted": round(avg_gols_contra_w, 2),
        "clean_sheets":     clean_sheets,
        "btts_pct":         round(btts_count / n * 100, 1),
        "over25_pct":       round(over25_count / n * 100, 1),
        "avg_shots":        round(sum(shots_list) / len(shots_list), 1) if shots_list else None,
        "avg_possession":   round(sum(possession_list) / len(possession_list), 1) if possession_list else None,
        "avg_corners":      round(sum(corners_list) / len(corners_list), 1) if corners_list else None,
    }


def compute_h2h_summary(matches: list, home_id: int) -> dict:
    """Processa o histórico H2H e retorna estatísticas."""
    if not matches:
        return {}

    home_wins = away_wins = draws = 0
    total_goals = btts = over25 = 0

    for m in matches:
        is_home = (m["home_team_id"] == home_id)
        gh = m["goals_home"] or 0
        ga = m["goals_away"] or 0
        gf = gh if is_home else ga
        gc = ga if is_home else gh
        tg = gh + ga

        total_goals += tg
        if gh > 0 and ga > 0:
            btts += 1
        if tg > 2.5:
            over25 += 1

        if gf > gc:
            home_wins += 1
        elif gf < gc:
            away_wins += 1
        else:
            draws += 1

    n = len(matches)
    return {
        "total":       n,
        "home_wins":   home_wins,
        "draws":       draws,
        "away_wins":   away_wins,
        "home_win_pct": round(home_wins / n * 100, 1),
        "away_win_pct": round(away_wins / n * 100, 1),
        "draw_pct":    round(draws / n * 100, 1),
        "avg_goals":   round(total_goals / n, 2),
        "btts_pct":    round(btts / n * 100, 1),
        "over25_pct":  round(over25 / n * 100, 1),
    }


# ──────────────────────────────────────────────────────────────
# MOTOR DE CÁLCULO (Poisson + ELO + Forma Real + H2H)
# ──────────────────────────────────────────────────────────────

def poisson_matrix(home_xg: float, away_xg: float, max_goals: int = MAX_GOALS) -> np.ndarray:
    """Calcula a matriz de probabilidades de placares."""
    home_probs = [scipy_poisson.pmf(i, home_xg) for i in range(max_goals)]
    away_probs = [scipy_poisson.pmf(i, away_xg) for i in range(max_goals)]
    return np.outer(home_probs, away_probs)


def matrix_to_probs(matrix: np.ndarray) -> dict:
    """Extrai probabilidades 1X2, Over/Under e BTTS da matriz."""
    total = matrix.sum()
    if total > 0:
        matrix = matrix / total

    home_win = float(np.tril(matrix, -1).sum())
    draw     = float(np.diag(matrix).sum())
    away_win = float(np.triu(matrix, 1).sum())

    over15 = float(sum(matrix[i, j] for i in range(MAX_GOALS) for j in range(MAX_GOALS) if i + j > 1.5))
    over25 = float(sum(matrix[i, j] for i in range(MAX_GOALS) for j in range(MAX_GOALS) if i + j > 2.5))
    over35 = float(sum(matrix[i, j] for i in range(MAX_GOALS) for j in range(MAX_GOALS) if i + j > 3.5))
    btts   = float(sum(matrix[i, j] for i in range(1, MAX_GOALS) for j in range(1, MAX_GOALS)))

    idx = np.unravel_index(np.argmax(matrix), matrix.shape)

    return {
        "home_win": min(home_win, 1.0),
        "draw":     min(draw, 1.0),
        "away_win": min(away_win, 1.0),
        "over15":   min(over15, 1.0),
        "over25":   min(over25, 1.0),
        "over35":   min(over35, 1.0),
        "btts":     min(btts, 1.0),
        "likely_score_home": int(idx[0]),
        "likely_score_away": int(idx[1]),
    }


def compute_xg(home_stats: dict, away_stats: dict,
               home_form: dict, away_form: dict,
               h2h_summary: dict, league_stats: dict) -> tuple[float, float]:
    """
    Calcula xG combinando 4 fontes de informação com pesos:
      40% Poisson clássico (forças relativas do cache)
      30% Forma real ponderada dos últimos 10 jogos
      20% H2H ajuste de bias
      10% ELO diferencial
    """
    avg_h = league_stats.get("avg_home_goals") or 1.35
    avg_a = league_stats.get("avg_away_goals") or 1.10

    # ── Base Poisson (forças do cache) ──
    atk_h = home_stats.get("attack_strength_home") or 1.0
    def_h = home_stats.get("defense_strength_home") or 1.0
    atk_a = away_stats.get("attack_strength_away") or 1.0
    def_a = away_stats.get("defense_strength_away") or 1.0

    base_home_xg = atk_h * def_a * avg_h
    base_away_xg = atk_a * def_h * avg_a

    # ── Forma Real dos últimos 10 jogos (ponderada pelo tempo) ──
    form_home_xg = home_form.get("avg_goals_scored_weighted")  or avg_h
    form_away_xg = away_form.get("avg_goals_scored_weighted")  or avg_a
    form_home_conceded = home_form.get("avg_goals_conceded_weighted") or avg_a
    form_away_conceded = away_form.get("avg_goals_conceded_weighted") or avg_h

    # xG combinando ataque de um e defesa do outro
    form_home_xg_adj = (form_home_xg + form_away_conceded) / 2
    form_away_xg_adj = (form_away_xg + form_home_conceded) / 2

    # ── ELO diferencial ──
    elo_h = home_stats.get("elo_rating") or 1500
    elo_a = away_stats.get("elo_rating") or 1500
    elo_factor = max(0.85, min(1.15, 1 + ((elo_h - elo_a) / 100) * 0.04))

    # ── Combinação ponderada ──
    home_xg = (base_home_xg * 0.40 + form_home_xg_adj * 0.50) * elo_factor
    away_xg = (base_away_xg * 0.40 + form_away_xg_adj * 0.50) / max(elo_factor, 0.9)

    # ── Ajuste H2H ──
    if h2h_summary.get("total", 0) >= 3:
        h2h_bias = (h2h_summary["home_win_pct"] / 100 - 0.5) * 0.20
        home_xg = max(0.3, home_xg * (1 + h2h_bias))
        away_xg = max(0.3, away_xg * (1 - h2h_bias))

        # Ajuste de gols totais pelo H2H
        h2h_goal_factor = (h2h_summary["avg_goals"] / (avg_h + avg_a)) * 0.15 + 0.85
        home_xg = max(0.3, home_xg * h2h_goal_factor)
        away_xg = max(0.3, away_xg * h2h_goal_factor)

    return (
        max(0.3, min(5.0, round(home_xg, 3))),
        max(0.3, min(5.0, round(away_xg, 3)))
    )


# Feature column order (matching notebook)
FEATURE_COLS_NN = [
    'h_gf', 'h_ga', 'h_win_rate', 'h_draw_rate', 'h_btts_rate',
    'h_over25_rate', 'h_clean_sheet_rate', 'h_pts_per_game', 'h_n_games',
    'a_gf', 'a_ga', 'a_win_rate', 'a_draw_rate', 'a_btts_rate',
    'a_over25_rate', 'a_clean_sheet_rate', 'a_pts_per_game', 'a_n_games',
    'diff_gf', 'diff_ga', 'diff_win_rate', 'diff_pts',
    'h2h_home_win_rate', 'h2h_avg_goals', 'h2h_btts',
]

def predict_with_nn(feature_dict):
    """Return NN prediction probabilities for home win, draw, away win.
    Expects a dict with keys matching FEATURE_COLS_NN.
    """
    if model is None or scaler is None:
        raise RuntimeError("NN model or scaler not loaded.")
    # Build feature vector in correct order
    vec = np.array([feature_dict.get(col, 0) for col in FEATURE_COLS_NN]).reshape(1, -1)
    vec_scaled = scaler.transform(vec)
    probs = model.predict(vec_scaled, verbose=0)[0]
    # Ensure sum to 1
    probs = probs / probs.sum()
    return {'home_win': float(probs[0]), 'draw': float(probs[1]), 'away_win': float(probs[2])}


def compute_confidence(probs: dict, home_form: dict, away_form: dict,
                        h2h_summary: dict) -> tuple[float, str]:
    """
    Confiança composta (0-100):
      - Decisividade das probabilidades
      - Qualidade dos dados (nº de jogos dos últimos 10)
      - Confirmação pelo H2H
      - Consistência de forma
    """
    best_prob = max(probs["home_win"], probs["draw"], probs["away_win"]) * 100

    # Qualidade de dados: baseada nos jogos reais disponíveis
    h_games = home_form.get("n", 0)
    a_games = away_form.get("n", 0)
    data_quality = min(1.0, (h_games + a_games) / (FORM_WINDOW * 2))

    # Bônus H2H (quando histórico confirma o favorito do modelo)
    h2h_bonus = 0
    if h2h_summary.get("total", 0) >= 3:
        if probs["home_win"] > probs["away_win"] and h2h_summary["home_win_pct"] >= 55:
            h2h_bonus = 6
        elif probs["away_win"] > probs["home_win"] and h2h_summary["away_win_pct"] >= 55:
            h2h_bonus = 6
        elif abs(h2h_summary["home_win_pct"] - h2h_summary["away_win_pct"]) < 15:
            h2h_bonus = 2  # empate histórico aumenta confiança no empate

    # Bônus de consistência de forma (sequência de W/L)
    form_bonus = 0
    h_seq = home_form.get("sequence", "")
    a_seq = away_form.get("sequence", "")
    if h_seq and h_seq[:3].count("W") >= 3 and probs["home_win"] > probs["away_win"]:
        form_bonus += 4
    if a_seq and a_seq[:3].count("W") >= 3 and probs["away_win"] > probs["home_win"]:
        form_bonus += 4
    if h_seq and h_seq[:3].count("L") >= 3:
        form_bonus += 2  # time em queda = mais previsível
    if a_seq and a_seq[:3].count("L") >= 3:
        form_bonus += 2

    score = (best_prob * 0.55) + (data_quality * 28) + h2h_bonus + form_bonus
    score = min(94.0, round(score, 1))

    if score >= 68:
        level = "high"
    elif score >= 54:
        level = "medium"
    else:
        level = "low"

    return score, level


def pick_main_suggestion(probs: dict, home_name: str, away_name: str,
                          league_stats: dict, h2h_summary: dict) -> tuple[str, str, float]:
    """Escolhe o mercado com maior edge em relação à média da liga."""
    candidates = [
        ("home_win", f"Vitoria {home_name}",       probs["home_win"] * 100, league_stats.get("home_win_pct", 45)),
        ("draw",     "Empate",                      probs["draw"] * 100,     league_stats.get("draw_pct", 26)),
        ("away_win", f"Vitoria {away_name}",        probs["away_win"] * 100, league_stats.get("away_win_pct", 30)),
        ("over25",   "Over 2.5 Gols",               probs["over25"] * 100,   league_stats.get("over25_pct", 48)),
        ("btts_yes", "Ambos Marcam",                probs["btts"] * 100,     league_stats.get("btts_pct", 50)),
    ]

    # Bônus H2H para over/under
    if h2h_summary.get("total", 0) >= 3:
        for c in candidates:
            if c[0] == "over25" and h2h_summary.get("over25_pct", 0) >= 65:
                candidates[candidates.index(c)] = (c[0], c[1], c[2] + 5, c[3])
                break

    valid = [(m, l, p, ctx) for m, l, p, ctx in candidates if p > 50]
    if not valid:
        valid = candidates

    valid.sort(key=lambda x: x[2] - x[3], reverse=True)
    market, label, prob, _ = valid[0]
    return market, label, prob


# ──────────────────────────────────────────────────────────────
# GERAÇÃO DE INSIGHTS IA (Gemini)
# ──────────────────────────────────────────────────────────────

def generate_ai_insights(ai_client, match: dict, home_form: dict,
                          away_form: dict, h2h_summary: dict,
                          probs: dict, home_xg: float, away_xg: float) -> list[str]:
    """
    Gera insights textuais em português usando o Groq Llama 3, e calibra as odds.
    Retorna um dicionário com "insights" e "adjusted_probs".
    """
    if not ai_client:
        return []

    home = match["home_team_name"]
    away = match["away_team_name"]

    def fmt_seq(seq):
        return " → ".join(list(seq[:5])) if seq else "N/D"

    prompt = f"""Você é um analista de futebol especializado. Analise este confronto e gere exatamente 4 insights CONCISOS e DIRETOS em português, cada um com no máximo 2 linhas.
Seja preciso e baseie-se nos dados. IMPORTANTE: Se os times não possuírem histórico na base e o modelo matemático estiver ignorando um claro abismo técnico (ex: Brasil vs San Marino), VOCÊ DEVE corrigir as probabilidades e o xG usando o seu próprio conhecimento futebolístico mundial. Se não houver abismo claro, apenas retorne a matemática original.

CONFRONTO: {home} vs {away}
LIGA: {match.get('league_name', 'N/D')}

=== FORMA DOS ÚLTIMOS {home_form.get('n', 0)} JOGOS ===
{home}:
  - Sequência (mais recente primeiro): {fmt_seq(home_form.get('sequence', ''))}
  - Gols marcados/jogo: {home_form.get('avg_goals_scored', 'N/D')}
  - Gols sofridos/jogo: {home_form.get('avg_goals_conceded', 'N/D')}
  - % Over 2.5: {home_form.get('over25_pct', 'N/D')}%
  - % BTTS: {home_form.get('btts_pct', 'N/D')}%
  - Clean sheets: {home_form.get('clean_sheets', 'N/D')}

{away}:
  - Sequência (mais recente primeiro): {fmt_seq(away_form.get('sequence', ''))}
  - Gols marcados/jogo: {away_form.get('avg_goals_scored', 'N/D')}
  - Gols sofridos/jogo: {away_form.get('avg_goals_conceded', 'N/D')}
  - % Over 2.5: {away_form.get('over25_pct', 'N/D')}%
  - % BTTS: {away_form.get('btts_pct', 'N/D')}%
  - Clean sheets: {away_form.get('clean_sheets', 'N/D')}

=== CONFRONTO DIRETO (H2H - últimos {h2h_summary.get('total', 0)} jogos) ===
  - Vitórias {home}: {h2h_summary.get('home_wins', 0)} ({h2h_summary.get('home_win_pct', 0)}%)
  - Empates: {h2h_summary.get('draws', 0)} ({h2h_summary.get('draw_pct', 0)}%)
  - Vitórias {away}: {h2h_summary.get('away_wins', 0)} ({h2h_summary.get('away_win_pct', 0)}%)
  - Média de gols no H2H: {h2h_summary.get('avg_goals', 'N/D')}
  - Over 2.5 no H2H: {h2h_summary.get('over25_pct', 'N/D')}%

=== MODELO PREDITIVO ===
  - xG {home}: {home_xg}
  - xG {away}: {away_xg}
  - Prob. Vitória {home}: {round(probs['home_win']*100, 1)}%
  - Prob. Empate: {round(probs['draw']*100, 1)}%
  - Prob. Vitória {away}: {round(probs['away_win']*100, 1)}%
  - Prob. Over 2.5: {round(probs['over25']*100, 1)}%
  - Prob. BTTS: {round(probs['btts']*100, 1)}%

Retorne APENAS um objeto JSON válido no seguinte formato exato (sem Markdown, sem blocos de código):
{{
  "insights": [
    "insight 1 conciso",
    "insight 2 conciso",
    "insight 3 conciso",
    "insight 4 conciso"
  ],
  "adjusted_probs": {{
    "home_win": 0.0,
    "draw": 0.0,
    "away_win": 0.0,
    "home_xg": 0.0,
    "away_xg": 0.0
  }}
}}

REGRA OBRIGATÓRIA para adjusted_probs: A soma de home_win + draw + away_win deve ser EXATAMENTE 1.0.
- Se as probabilidades do modelo estiverem coerentes com a realidade: copie os valores originais.
- Se houver um ABISMO técnico claro ignorado pelo modelo (ex: Germany vs Curaçao, Brasil vs San Marino, França vs Gibraltar): corrija com valores extremos como (0.85, 0.10, 0.05) e xG refletindo massacre (ex: 3.5 vs 0.3).
"""

    for attempt in range(AI_MAX_RETRY):
        try:
            chat_completion = ai_client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=AI_MODEL,
                response_format={"type": "json_object"},
                temperature=0.2
            )
            text = chat_completion.choices[0].message.content.strip()

            try:
                data = json.loads(text)
                return data
            except json.JSONDecodeError:
                print(f"        [IA] Erro ao parsear JSON: {text}")
                return {"insights": [], "adjusted_probs": None}

        except Exception as e:
            err_str = str(e)
            wait = 15 * (attempt + 1)  # 15s, 30s, 45s - conservador para o free tier

            if '429' in err_str or 'rate' in err_str.lower():
                if attempt < AI_MAX_RETRY - 1:
                    print(f"        [IA] Rate limit (tentativa {attempt+1}/{AI_MAX_RETRY}). Aguardando {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"        [IA] Rate limit persistente. Pulando IA para este jogo.")
                    return {"insights": [], "adjusted_probs": None}
            else:
                print(f"        [IA] Erro ao gerar insight: {e}")
                return {"insights": [], "adjusted_probs": None}
    return {"insights": [], "adjusted_probs": None}


# ──────────────────────────────────────────────────────────────
# ANÁLISE PRINCIPAL DE UMA PARTIDA
# ──────────────────────────────────────────────────────────────

def analyze_match(match: dict, ai_client) -> dict | None:
    """Analisa uma partida com todos os dados disponíveis."""
    home_id   = match["home_team_id"]
    away_id   = match["away_team_id"]
    league_id = match["league_id"]
    season    = match["season"]

    # Busca em paralelo (sequencial para evitar rate limit do Supabase)
    home_recent  = fetch_recent_matches(home_id, FORM_WINDOW)
    away_recent  = fetch_recent_matches(away_id, FORM_WINDOW)
    h2h_matches  = fetch_h2h(home_id, away_id, H2H_LIMIT)
    league_stats = fetch_league_stats(league_id, season)
    home_stats   = fetch_team_stats_cache(home_id, league_id, season)
    away_stats   = fetch_team_stats_cache(away_id, league_id, season)

    # Calcula forma real dos últimos 10 jogos de cada time
    home_form = compute_real_form(home_recent, home_id)
    away_form = compute_real_form(away_recent, away_id)

    # Processa H2H
    h2h_summary = compute_h2h_summary(h2h_matches, home_id)

    # Calcula xG combinado
    home_xg, away_xg = compute_xg(
        home_stats, away_stats,
        home_form, away_form,
        h2h_summary, league_stats
    )

    # Matriz de Poisson → probabilidades
    matrix = poisson_matrix(home_xg, away_xg)
    probs  = matrix_to_probs(matrix)

    # If NN model is enabled, combine its predictions with Poisson probabilities
    if USE_NN and model is not None and scaler is not None:
        try:
            # Build feature dict from available data
            feat = {
                'h_gf': home_form.get('avg_goals_scored_weighted', 0),
                'h_ga': home_form.get('avg_goals_conceded_weighted', 0),
                'h_win_rate': home_form.get('win_rate', 0),
                'h_draw_rate': home_form.get('draw_rate', 0),
                'h_btts_rate': home_form.get('btts_pct', 0) / 100,
                'h_over25_rate': home_form.get('over25_pct', 0) / 100,
                'h_clean_sheet_rate': home_form.get('clean_sheets', 0) / max(1, home_form.get('n', 1)),
                'h_pts_per_game': (home_form.get('points', 0) / max(1, home_form.get('n', 1))) if home_form.get('n') else 0,
                'h_n_games': home_form.get('n', 0),
                'a_gf': away_form.get('avg_goals_scored_weighted', 0),
                'a_ga': away_form.get('avg_goals_conceded_weighted', 0),
                'a_win_rate': away_form.get('win_rate', 0),
                'a_draw_rate': away_form.get('draw_rate', 0),
                'a_btts_rate': away_form.get('btts_pct', 0) / 100,
                'a_over25_rate': away_form.get('over25_pct', 0) / 100,
                'a_clean_sheet_rate': away_form.get('clean_sheets', 0) / max(1, away_form.get('n', 1)),
                'a_pts_per_game': (away_form.get('points', 0) / max(1, away_form.get('n', 1))) if away_form.get('n') else 0,
                'a_n_games': away_form.get('n', 0),
                'diff_gf': home_form.get('avg_goals_scored_weighted', 0) - away_form.get('avg_goals_scored_weighted', 0),
                'diff_ga': home_form.get('avg_goals_conceded_weighted', 0) - away_form.get('avg_goals_conceded_weighted', 0),
                'diff_win_rate': home_form.get('win_rate', 0) - away_form.get('win_rate', 0),
                'diff_pts': (home_form.get('points', 0) / max(1, home_form.get('n', 1))) - (away_form.get('points', 0) / max(1, away_form.get('n', 1))) if home_form.get('n') and away_form.get('n') else 0,
                'h2h_home_win_rate': h2h_summary.get('home_win_pct', 0) / 100,
                'h2h_avg_goals': h2h_summary.get('avg_goals', 0),
                'h2h_btts': h2h_summary.get('btts_pct', 0) / 100,
            }
            nn_probs = predict_with_nn(feat)
            # Simple average blending for main 1X2 probabilities
            probs['home_win'] = (probs['home_win'] + nn_probs['home_win']) / 2
            probs['draw'] = (probs['draw'] + nn_probs['draw']) / 2
            probs['away_win'] = (probs['away_win'] + nn_probs['away_win']) / 2
        except Exception as e:
            print(f"    [NN] Aviso: Falha ao combinar modelo NN: {e}")

    # Score de confiança
    confidence_score, confidence_level = compute_confidence(
        probs, home_form, away_form, h2h_summary
    )

    # Sugestão principal
    main_market, main_label, main_prob = pick_main_suggestion(
        probs, match["home_team_name"], match["away_team_name"],
        league_stats, h2h_summary
    )

    # Gera insights com IA
    ai_result = generate_ai_insights(
        ai_client, match,
        home_form, away_form, h2h_summary,
        probs, home_xg, away_xg
    )
    ai_insights = []
    if isinstance(ai_result, dict):
        ai_insights = ai_result.get("insights", [])
        adj = ai_result.get("adjusted_probs")
        if adj and isinstance(adj, dict) and "home_win" in adj:
            print(f"    [IA] Odds originais calibradas pelo Groq: {match['home_team_name']} vs {match['away_team_name']}")
            probs["home_win"] = adj.get("home_win", probs["home_win"])
            probs["draw"]     = adj.get("draw", probs["draw"])
            probs["away_win"] = adj.get("away_win", probs["away_win"])
            home_xg           = adj.get("home_xg", home_xg)
            away_xg           = adj.get("away_xg", away_xg)
            
            # Recalcula a sugestão principal pois as probs mudaram
            main_market, main_label, main_prob = pick_main_suggestion(
                probs, match["home_team_name"], match["away_team_name"],
                league_stats, h2h_summary
            )

    def _fair_odd(prob_pct: float) -> float | None:
        """Converte probabilidade (%) em odd justa decimal."""
        return round(100 / prob_pct, 2) if prob_pct > 1 else None

    # ── Campos de Auditoria (Fase 2 — Log da Verdade) ──
    # Congelados no momento zero, ANTES da bola rolar.
    computed_fair_odd = _fair_odd(main_prob)

    return {
        "fixture_id":            match["fixture_id"],
        "home_win_prob":         round(probs["home_win"] * 100, 2),
        "draw_prob":             round(probs["draw"] * 100, 2),
        "away_win_prob":         round(probs["away_win"] * 100, 2),
        "home_xg":               round(home_xg, 2),
        "away_xg":               round(away_xg, 2),
        "btts_prob":             round(probs["btts"] * 100, 2),
        "over15_prob":           round(probs["over15"] * 100, 2),
        "over25_prob":           round(probs["over25"] * 100, 2),
        "over35_prob":           round(probs["over35"] * 100, 2),
        "most_likely_score":     f"{probs['likely_score_home']} x {probs['likely_score_away']}",
        "score_prob":            round(float(matrix[probs["likely_score_home"], probs["likely_score_away"]]) * 100, 2),
        "confidence_score":      confidence_score,
        "confidence_level":      confidence_level,
        "main_suggestion":       main_market,
        "main_suggestion_label": main_label,
        "main_suggestion_prob":  round(main_prob, 2),
        "model_version":         MODEL_VERSION,
        "insights":              json.dumps(ai_insights, ensure_ascii=False) if ai_insights else None,
        # ── Auditoria: congelado no momento zero ──
        "suggested_bet":         main_market,          # ex: 'home_win', 'over25', 'btts_yes'
        "fair_odd":              computed_fair_odd,     # odd justa pelo modelo
        "bookmaker_odd":         computed_fair_odd,     # sem API externa: usa fair_odd por padrão
        "stake":                 1.0,                   # 1 unidade padrão
        "bet_resolved":          False,                 # aguardando resultado
    }


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gera previsoes com forma real e insights IA.")
    parser.add_argument("--days",   type=int, default=DEFAULT_DAYS)
    parser.add_argument("--league", type=int, default=None)
    parser.add_argument("--no-ai",  action="store_true", help="Desativa o Gemini (mais rapido)")
    parser.add_argument("--use-nn", action="store_true", help="Utiliza modelo de rede neural para prever resultado principal")
    args, unknown = parser.parse_known_args()

    # Global flag for NN usage
    global USE_NN, model, scaler
    USE_NN = args.use_nn

    if not supabase_client:
        print("ERRO: Supabase nao configurado.")
        sys.exit(1)

    print("\n" + "=" * 70)
    print(f"  GENERATE PREDICTIONS  ({MODEL_VERSION})")
    print("=" * 70)

    # Inicializa Groq (se não estiver desativado)
    ai_client = None
    if not args.no_ai:
        print("\n[0/6] Inicializando Groq AI (Llama 3)...")
        ai_client = get_ai_client()
        if ai_client:
            print("    -> Groq ativo! Insights IA serao gerados.")
        else:
            print("    -> Groq indisponivel. Rodando sem IA.")
    else:
        print("\n[0/6] Modo --no-ai: IA desativada.")

    # Carrega modelo NN se solicitado
    if USE_NN:
        try:
            import tensorflow as tf
            import pickle
            model_path = os.path.join(os.path.dirname(__file__), "..", "football_nn_model.keras")
            scaler_path = os.path.join(os.path.dirname(__file__), "..", "football_scaler.pkl")
            model = tf.keras.models.load_model(model_path)
            with open(scaler_path, 'rb') as f:
                scaler = pickle.load(f)
            print("    -> Modelo NN carregado com sucesso.")
        except Exception as e:
            print(f"    -> Erro ao carregar modelo NN: {e}")
            model = None
            scaler = None

    # 1. Jogos futuros
    upcoming = fetch_upcoming_matches(args.days, args.league)
    if not upcoming:
        print("Nenhum jogo agendado. Encerrando.")
        sys.exit(0)

    # 2. Analisa cada partida
    print(f"\n[2/6] Analisando {len(upcoming)} partidas...")
    print(f"      Fontes: ultimos {FORM_WINDOW} jogos reais + H2H ({H2H_LIMIT}) + Poisson + ELO + IA")
    predictions = []
    errors = 0

    for i, match in enumerate(upcoming, 1):
        try:
            pred = analyze_match(match, ai_client)
            if pred:
                predictions.append(pred)
                ai_status = "ok" if (pred.get("insights") and json.loads(pred["insights"])) else "sem IA"
                print(f"    [{i:02d}/{len(upcoming)}] {match['home_team_name']} vs {match['away_team_name']} "
                      f"| conf={pred['confidence_score']:.0f} ({pred['confidence_level']}) | IA: {ai_status}")
        except Exception as e:
            errors += 1
            print(f"    -> ERRO no jogo {match.get('fixture_id')}: {e}")

        # Pausa entre chamadas para respeitar o rate limit
        if ai_client:
            time.sleep(AI_DELAY)

    print(f"\n    -> {len(predictions)} previsoes geradas. ({errors} erros)")

    if not predictions:
        print("Nenhuma previsao para salvar.")
        sys.exit(0)

    # 3. Salva no Supabase
    print(f"\n[3/6] Salvando {len(predictions)} previsoes no Supabase...")
    saved = 0
    insights_missing = False  # Flag para detectar coluna ausente
    for i in range(0, len(predictions), BATCH_SIZE):
        batch = predictions[i:i + BATCH_SIZE]
        try:
            supabase_client.table("predictions").upsert(
                batch, on_conflict="fixture_id,model_version"
            ).execute()
            saved += len(batch)
        except Exception as e:
            err_str = str(e)
            # Se a coluna 'insights' não existe, salva sem ela e avisa
            if 'insights' in err_str and 'column' in err_str and not insights_missing:
                insights_missing = True
                print(f"    -> AVISO: Coluna 'insights' nao encontrada. Salvando sem IA.")
                print(f"       Execute no Supabase SQL Editor:")
                print(f"       ALTER TABLE predictions ADD COLUMN IF NOT EXISTS insights JSONB;")
            # Retry removendo o campo insights
            batch_sem_insights = [{k: v for k, v in row.items() if k != 'insights'} for row in batch]
            try:
                supabase_client.table("predictions").upsert(
                    batch_sem_insights, on_conflict="fixture_id,model_version"
                ).execute()
                saved += len(batch)
            except Exception as e2:
                print(f"    -> ERRO no lote {i // BATCH_SIZE + 1}: {e2}")

    # Resumo
    high   = sum(1 for p in predictions if p["confidence_level"] == "high")
    medium = sum(1 for p in predictions if p["confidence_level"] == "medium")
    low    = sum(1 for p in predictions if p["confidence_level"] == "low")
    with_ai = sum(1 for p in predictions if p.get("insights"))

    print("\n" + "=" * 70)
    print("  CONCLUIDO!")
    print(f"  Total analisado  : {len(upcoming)} jogos")
    print(f"  Previsoes salvas : {saved}")
    print(f"  Alta confianca   : {high} | Media: {medium} | Baixa: {low}")
    print(f"  Com insights IA  : {with_ai} jogos")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
