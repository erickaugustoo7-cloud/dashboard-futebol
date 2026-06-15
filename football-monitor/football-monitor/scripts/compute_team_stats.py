# -*- coding: utf-8 -*-
"""
=============================================================
  COMPUTE TEAM & LEAGUE STATS — Football Monitor
=============================================================
Lê todos os jogos finalizados do Supabase e calcula:
  - Médias por time (geral, casa, fora)
  - Forças de ataque/defesa relativas
  - ELO rating dinâmico
  - Form das últimas 5/10 partidas
  - Fadiga (dias desde o último jogo)
  - Médias por liga (base Poisson)

Como rodar:
  python scripts/compute_team_stats.py
  python scripts/compute_team_stats.py --league 71  (só Brasileirão)
=============================================================
"""

import sys
import io
import json
import math
import time
import argparse
from datetime import date, datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
from supabase_client import supabase_client

# ──────────────────────────────────────────────────────────────
# CONFIGURAÇÕES
# ──────────────────────────────────────────────────────────────
ELO_K           = 32      # Fator K do ELO (quanto cada jogo move o rating)
ELO_BASE        = 1500    # Rating inicial
DECAY_LAMBDA    = 0.01    # Peso temporal: jogo de 70 dias atrás pesa ~50%
FORM_WINDOWS    = [5, 10] # Janelas de form a calcular


def fetch_all_matches(league_id: int = None, max_retries: int = 5) -> pd.DataFrame:
    """Busca todos os jogos finalizados do Supabase com retry em falha de rede."""
    print(f"[1/5] Buscando jogos do Supabase{'  (liga ' + str(league_id) + ')' if league_id else ''}...")
    
    all_rows = []
    offset = 0
    page_size = 1000

    while True:
        for attempt in range(max_retries):
            try:
                query = supabase_client.table("matches").select("*").eq("status", "FT")
                if league_id:
                    query = query.eq("league_id", league_id)
                result = query.order("date").range(offset, offset + page_size - 1).execute()
                rows = result.data
                break  # Sucesso — sai do loop de retry
            except Exception as e:
                wait = 5 * (attempt + 1)
                print(f"    -> Falha de rede (tentativa {attempt+1}/{max_retries}). Aguardando {wait}s... ({e})")
                time.sleep(wait)
        else:
            print("    -> Falhou após todas as tentativas. Usando dados parciais.")
            break

        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    df = pd.DataFrame(all_rows)
    print(f"    -> {len(df)} jogos carregados.")
    return df


def compute_league_stats(df: pd.DataFrame) -> list[dict]:
    """Calcula médias globais por liga e temporada."""
    print("[2/5] Calculando estatísticas por liga...")
    records = []
    
    for (league_id, season), grp in df.groupby(["league_id", "season"]):
        g = grp.dropna(subset=["goals_home", "goals_away"])
        if len(g) < 5:
            continue
        
        total = len(g)
        home_goals = g["goals_home"].sum()
        away_goals = g["goals_away"].sum()
        total_goals = home_goals + away_goals
        
        home_wins = (g["goals_home"] > g["goals_away"]).sum()
        away_wins = (g["goals_home"] < g["goals_away"]).sum()
        draws     = (g["goals_home"] == g["goals_away"]).sum()
        
        btts    = ((g["goals_home"] > 0) & (g["goals_away"] > 0)).sum()
        over15  = ((g["goals_home"] + g["goals_away"]) > 1.5).sum()
        over25  = ((g["goals_home"] + g["goals_away"]) > 2.5).sum()
        over35  = ((g["goals_home"] + g["goals_away"]) > 3.5).sum()
        
        corners_h = g["home_corners"].dropna()
        corners_a = g["away_corners"].dropna()
        
        records.append({
            "league_id":         int(league_id),
            "season":            int(season),
            "total_matches":     total,
            "avg_home_goals":    round(home_goals / total, 4),
            "avg_away_goals":    round(away_goals / total, 4),
            "avg_total_goals":   round(total_goals / total, 4),
            "home_win_pct":      round(home_wins / total * 100, 2),
            "draw_pct":          round(draws / total * 100, 2),
            "away_win_pct":      round(away_wins / total * 100, 2),
            "btts_pct":          round(btts / total * 100, 2),
            "over15_pct":        round(over15 / total * 100, 2),
            "over25_pct":        round(over25 / total * 100, 2),
            "over35_pct":        round(over35 / total * 100, 2),
            "avg_corners_home":  round(corners_h.mean(), 4) if len(corners_h) > 0 else None,
            "avg_corners_away":  round(corners_a.mean(), 4) if len(corners_a) > 0 else None,
            "avg_corners_total": round((corners_h.sum() + corners_a.sum()) / max(len(corners_h), 1), 4) if len(corners_h) > 0 else None,
            "avg_yellow_cards":  round((g["home_yellow_cards"].fillna(0) + g["away_yellow_cards"].fillna(0)).mean(), 4),
            "avg_red_cards":     round((g["home_red_cards"].fillna(0) + g["away_red_cards"].fillna(0)).mean(), 4),
            "updated_at":        datetime.now().isoformat()
        })
    
    print(f"    -> {len(records)} combinações liga/temporada calculadas.")
    return records


def compute_elo_ratings(df: pd.DataFrame) -> dict[int, float]:
    """Calcula ELO dinâmico para todos os times com base na ordem cronológica dos jogos."""
    print("[3/5] Calculando ELO ratings...")
    elo = {}
    
    df_sorted = df.dropna(subset=["goals_home", "goals_away"]).sort_values("date")
    
    for _, row in df_sorted.iterrows():
        h_id = int(row["home_team_id"])
        a_id = int(row["away_team_id"])
        
        elo.setdefault(h_id, ELO_BASE)
        elo.setdefault(a_id, ELO_BASE)
        
        # Expected score (vantagem de 100 pontos para o mandante)
        exp_h = 1 / (1 + 10 ** ((elo[a_id] - elo[h_id] - 100) / 400))
        exp_a = 1 - exp_h
        
        # Resultado real
        gh, ga = int(row["goals_home"]), int(row["goals_away"])
        if gh > ga:
            score_h, score_a = 1.0, 0.0
        elif gh < ga:
            score_h, score_a = 0.0, 1.0
        else:
            score_h, score_a = 0.5, 0.5
        
        # Margem de gols amplifica o ajuste (máximo 1.5x)
        margin = abs(gh - ga)
        k_multiplier = min(1 + math.log(1 + margin) * 0.3, 1.5)
        
        elo[h_id] = elo[h_id] + ELO_K * k_multiplier * (score_h - exp_h)
        elo[a_id] = elo[a_id] + ELO_K * k_multiplier * (score_a - exp_a)
    
    print(f"    -> ELO calculado para {len(elo)} times.")
    return elo


def build_form_json(recent_matches: pd.DataFrame, team_id: int, n: int) -> dict:
    """Constrói JSON de form das últimas N partidas de um time."""
    matches = recent_matches[
        (recent_matches["home_team_id"] == team_id) |
        (recent_matches["away_team_id"] == team_id)
    ].sort_values("date", ascending=False).head(n)
    
    results = []
    for _, m in matches.iterrows():
        is_home = int(m["home_team_id"]) == team_id
        gf = int(m["goals_home"]) if is_home else int(m["goals_away"])
        ga = int(m["goals_away"]) if is_home else int(m["goals_home"])
        result = "W" if gf > ga else ("L" if gf < ga else "D")
        results.append({
            "date":    str(m["date"])[:10] if m["date"] is not None else "",
            "side":    "home" if is_home else "away",
            "gf":      gf,
            "ga":      ga,
            "result":  result,
            "btts":    gf > 0 and ga > 0,
            "over25":  gf + ga > 2.5
        })
    
    if not results:
        return {}
    
    pts_map = {"W": 3, "D": 1, "L": 0}
    total_pts = sum(pts_map[r["result"]] for r in results)
    avg_gf = sum(r["gf"] for r in results) / len(results)
    avg_ga = sum(r["ga"] for r in results) / len(results)
    
    return {
        "n":        len(results),
        "results":  [r["result"] for r in results],
        "points":   total_pts,
        "avg_gf":   round(avg_gf, 2),
        "avg_ga":   round(avg_ga, 2),
        "btts_pct": round(sum(1 for r in results if r["btts"]) / len(results) * 100, 1),
        "over25_pct": round(sum(1 for r in results if r["over25"]) / len(results) * 100, 1),
        "matches":  results
    }


def compute_team_stats(df: pd.DataFrame, elo: dict) -> list[dict]:
    """Calcula estatísticas completas por time, liga e temporada."""
    print("[4/5] Calculando estatísticas por time...")
    
    df_ft = df.dropna(subset=["goals_home", "goals_away"]).copy()
    df_ft["date"] = pd.to_datetime(df_ft["date"], utc=True)
    today = pd.Timestamp.now(tz="UTC")
    
    records = []
    
    # Agrupa por time + liga (usa todos os anos para form, filtra por season para médias)
    for (league_id, season), season_grp in df_ft.groupby(["league_id", "season"]):
        # Busca todos os times que jogaram nessa liga/temporada
        team_ids = set(season_grp["home_team_id"].tolist() + season_grp["away_team_id"].tolist())
        
        # Calcula médias da liga para forças relativas
        lg_avg_home = season_grp["goals_home"].mean() or 1.0
        lg_avg_away = season_grp["goals_away"].mean() or 1.0
        
        for team_id in team_ids:
            team_id = int(team_id)
            
            # Jogos em casa e fora na temporada
            home_g = season_grp[season_grp["home_team_id"] == team_id]
            away_g = season_grp[season_grp["away_team_id"] == team_id]
            all_g  = pd.concat([home_g, away_g])
            
            if len(all_g) == 0:
                continue
            
            team_name = (
                home_g["home_team_name"].iloc[0] if len(home_g) > 0
                else away_g["away_team_name"].iloc[0]
            )
            
            def safe_mean(series):
                s = series.dropna()
                return round(float(s.mean()), 4) if len(s) > 0 else None
            
            def pct(condition, total):
                return round(condition.sum() / max(total, 1) * 100, 2)
            
            # ── Stats gerais ──
            total_matches = len(all_g)
            gf_all = pd.concat([
                home_g["goals_home"].rename("gf"),
                away_g["goals_away"].rename("gf")
            ])
            ga_all = pd.concat([
                home_g["goals_away"].rename("ga"),
                away_g["goals_home"].rename("ga")
            ])
            
            btts_all  = (gf_all > 0) & (ga_all > 0)
            total_all = gf_all + ga_all
            
            # ── Stats em casa ──
            nh = len(home_g)
            gf_h = home_g["goals_home"]
            ga_h = home_g["goals_away"]
            btts_h  = (gf_h > 0) & (ga_h > 0)
            total_h = gf_h + ga_h
            hw_h = (gf_h > ga_h)
            
            # ── Stats fora ──
            na = len(away_g)
            gf_a = away_g["goals_away"]
            ga_a = away_g["goals_home"]
            btts_a  = (gf_a > 0) & (ga_a > 0)
            total_a = gf_a + ga_a
            hw_a = (gf_a > ga_a)
            
            # ── Forças de ataque/defesa ──
            avg_scored_h   = gf_h.mean() if nh > 0 else lg_avg_home
            avg_conceded_h = ga_h.mean() if nh > 0 else lg_avg_away
            avg_scored_a   = gf_a.mean() if na > 0 else lg_avg_away
            avg_conceded_a = ga_a.mean() if na > 0 else lg_avg_home
            
            atk_home = avg_scored_h / lg_avg_home if lg_avg_home > 0 else 1.0
            def_home = avg_conceded_h / lg_avg_away if lg_avg_away > 0 else 1.0
            atk_away = avg_scored_a / lg_avg_away if lg_avg_away > 0 else 1.0
            def_away = avg_conceded_a / lg_avg_home if lg_avg_home > 0 else 1.0
            
            # ── ELO ──
            elo_rating = elo.get(team_id, ELO_BASE)
            
            # ── Form recente (usa todos os jogos do time, não só da temporada) ──
            team_all_history = df_ft[
                (df_ft["home_team_id"] == team_id) |
                (df_ft["away_team_id"] == team_id)
            ]
            form5  = build_form_json(team_all_history, team_id, 5)
            form10 = build_form_json(team_all_history, team_id, 10)
            
            # ── Fadiga ──
            last_dates = team_all_history["date"].dropna()
            last_date  = last_dates.max()
            days_since = (today - last_date).days if pd.notna(last_date) else None
            
            recent_14 = team_all_history[
                team_all_history["date"] >= (today - timedelta(days=14))
            ]
            matches_14 = len(recent_14)
            
            # Score de fadiga: 0–10 (mais de 4 jogos em 14 dias = alto)
            fatigue = min(10, max(0, (matches_14 - 1) * 2.5))
            
            records.append({
                "team_id":                  team_id,
                "team_name":                str(team_name),
                "league_id":                int(league_id),
                "season":                   int(season),
                "total_matches":            total_matches,
                "avg_goals_scored":         round(float(gf_all.mean()), 4),
                "avg_goals_conceded":       round(float(ga_all.mean()), 4),
                "avg_shots":                safe_mean(pd.concat([home_g["home_shots"], away_g["away_shots"]])),
                "avg_sog":                  safe_mean(pd.concat([home_g["home_sog"], away_g["away_sog"]])),
                "avg_corners":              safe_mean(pd.concat([home_g["home_corners"], away_g["away_corners"]])),
                "avg_yellow_cards":         safe_mean(pd.concat([home_g["home_yellow_cards"], away_g["away_yellow_cards"]])),
                "btts_pct":                 pct(btts_all, total_matches),
                "over15_pct":               pct(total_all > 1.5, total_matches),
                "over25_pct":               pct(total_all > 2.5, total_matches),
                "over35_pct":               pct(total_all > 3.5, total_matches),
                # Casa
                "home_matches":             nh,
                "avg_goals_scored_home":    round(float(gf_h.mean()), 4) if nh > 0 else None,
                "avg_goals_conceded_home":  round(float(ga_h.mean()), 4) if nh > 0 else None,
                "avg_shots_home":           safe_mean(home_g["home_shots"]),
                "avg_corners_home":         safe_mean(home_g["home_corners"]),
                "btts_pct_home":            pct(btts_h, nh),
                "over25_pct_home":          pct(total_h > 2.5, nh),
                "home_win_pct":             pct(hw_h, nh),
                # Fora
                "away_matches":             na,
                "avg_goals_scored_away":    round(float(gf_a.mean()), 4) if na > 0 else None,
                "avg_goals_conceded_away":  round(float(ga_a.mean()), 4) if na > 0 else None,
                "avg_shots_away":           safe_mean(away_g["away_shots"]),
                "avg_corners_away":         safe_mean(away_g["away_corners"]),
                "btts_pct_away":            pct(btts_a, na),
                "over25_pct_away":          pct(total_a > 2.5, na),
                "away_win_pct":             pct(hw_a, na),
                # Forças
                "attack_strength_home":     round(float(atk_home), 4),
                "defense_strength_home":    round(float(def_home), 4),
                "attack_strength_away":     round(float(atk_away), 4),
                "defense_strength_away":    round(float(def_away), 4),
                # ELO + Form + Fadiga
                "elo_rating":               round(float(elo_rating), 2),
                "form_last5":               json.dumps(form5, ensure_ascii=False),
                "form_last10":              json.dumps(form10, ensure_ascii=False),
                "last_match_date":          str(last_date.date()) if pd.notna(last_date) else None,
                "days_since_last_match":    days_since,
                "matches_last_14_days":     matches_14,
                "fatigue_score":            round(fatigue, 2),
                "updated_at":               datetime.now().isoformat()
            })
    
    print(f"    -> {len(records)} registros de times calculados.")
    return records


def save_league_stats(records: list[dict]):
    """Salva estatísticas de liga no Supabase."""
    if not records:
        return
    print(f"[5a/5] Salvando {len(records)} stats de liga no Supabase...")
    try:
        supabase_client.table("league_stats_cache").upsert(
            records, on_conflict="league_id,season"
        ).execute()
        print("    -> OK!")
    except Exception as e:
        print(f"    -> ERRO: {e}")




def save_team_stats(records: list[dict]):
    """Salva estatísticas de times no Supabase em lotes."""
    if not records:
        return
    print(f"[5b/5] Salvando {len(records)} stats de times no Supabase...")
    batch_size = 50
    saved = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            supabase_client.table("team_stats_cache").upsert(
                batch, on_conflict="team_id,league_id,season"
            ).execute()
            saved += len(batch)
        except Exception as e:
            print(f"    -> ERRO no lote {i//batch_size + 1}: {e}")
    print(f"    -> {saved} registros salvos!")



def compute_global_team_stats(df: pd.DataFrame, elo: dict) -> list[dict]:
    """
    Calcula estatísticas GLOBAIS de cada time (ignorando liga/temporada).
    
    Este perfil usa TODOS os jogos históricos do time de TODAS as ligas.
    É salvo com league_id=0 e season=0, servindo como fallback para times
    em competições internacionais (Copa do Mundo, Eurocopa, Libertadores, etc.)
    onde não há stats específicas da liga.
    """
    print("[5c/5] Calculando perfil global dos times (cross-liga)...")
    
    df_ft = df.dropna(subset=["goals_home", "goals_away"]).copy()
    df_ft["date"] = pd.to_datetime(df_ft["date"], utc=True)
    today = pd.Timestamp.now(tz="UTC")
    
    # Encontra todos os times únicos
    all_team_ids = set(df_ft["home_team_id"].tolist() + df_ft["away_team_id"].tolist())
    
    # Médias globais (base Poisson global)
    global_avg_home = df_ft["goals_home"].mean() or 1.35
    global_avg_away = df_ft["goals_away"].mean() or 1.10
    
    records = []
    
    for team_id in all_team_ids:
        team_id = int(team_id)
        
        home_g = df_ft[df_ft["home_team_id"] == team_id]
        away_g = df_ft[df_ft["away_team_id"] == team_id]
        all_g  = pd.concat([home_g, away_g])
        
        if len(all_g) < 3:  # Menos de 3 jogos não vale
            continue
        
        team_name = (
            home_g["home_team_name"].iloc[0] if len(home_g) > 0
            else away_g["away_team_name"].iloc[0]
        )
        
        def safe_mean(series):
            s = series.dropna()
            return round(float(s.mean()), 4) if len(s) > 0 else None

        def pct(condition, total):
            return round(condition.sum() / max(total, 1) * 100, 2)
        
        total_matches = len(all_g)
        nh = len(home_g)
        na = len(away_g)
        
        gf_all = pd.concat([home_g["goals_home"].rename("gf"), away_g["goals_away"].rename("gf")])
        ga_all = pd.concat([home_g["goals_away"].rename("ga"), away_g["goals_home"].rename("ga")])
        btts_all  = (gf_all > 0) & (ga_all > 0)
        total_all = gf_all + ga_all
        
        gf_h = home_g["goals_home"]
        ga_h = home_g["goals_away"]
        gf_a = away_g["goals_away"]
        ga_a = away_g["goals_home"]
        hw_h = (gf_h > ga_h)
        hw_a = (gf_a > ga_a)
        
        # Forças relativas às médias globais (não da liga específica)
        avg_scored_h   = gf_h.mean() if nh > 0 else global_avg_home
        avg_conceded_h = ga_h.mean() if nh > 0 else global_avg_away
        avg_scored_a   = gf_a.mean() if na > 0 else global_avg_away
        avg_conceded_a = ga_a.mean() if na > 0 else global_avg_home
        
        atk_home = avg_scored_h / global_avg_home if global_avg_home > 0 else 1.0
        def_home = avg_conceded_h / global_avg_away if global_avg_away > 0 else 1.0
        atk_away = avg_scored_a / global_avg_away if global_avg_away > 0 else 1.0
        def_away = avg_conceded_a / global_avg_home if global_avg_home > 0 else 1.0
        
        elo_rating = elo.get(team_id, ELO_BASE)
        
        # Form recente
        form5  = build_form_json(all_g, team_id, 5)
        form10 = build_form_json(all_g, team_id, 10)
        
        last_dates = all_g["date"].dropna()
        last_date  = last_dates.max()
        days_since = (today - last_date).days if pd.notna(last_date) else None
        
        # Fadiga recente
        recent_14 = all_g[all_g["date"] >= (today - timedelta(days=14))]
        matches_14 = len(recent_14)
        fatigue = min(10, max(0, (matches_14 - 1) * 2.5))
        
        records.append({
            "team_id":                  team_id,
            "team_name":                str(team_name),
            "league_id":                0,   # 0 = perfil global cross-liga
            "season":                   0,   # 0 = global
            "total_matches":            total_matches,
            "avg_goals_scored":         round(float(gf_all.mean()), 4),
            "avg_goals_conceded":       round(float(ga_all.mean()), 4),
            "avg_shots":                safe_mean(pd.concat([home_g.get("home_shots", pd.Series(dtype=float)), away_g.get("away_shots", pd.Series(dtype=float))])),
            "avg_sog":                  safe_mean(pd.concat([home_g.get("home_sog", pd.Series(dtype=float)), away_g.get("away_sog", pd.Series(dtype=float))])),
            "avg_corners":              safe_mean(pd.concat([home_g.get("home_corners", pd.Series(dtype=float)), away_g.get("away_corners", pd.Series(dtype=float))])),
            "avg_yellow_cards":         safe_mean(pd.concat([home_g.get("home_yellow_cards", pd.Series(dtype=float)), away_g.get("away_yellow_cards", pd.Series(dtype=float))])),
            "btts_pct":                 pct(btts_all, total_matches),
            "over15_pct":               pct(total_all > 1.5, total_matches),
            "over25_pct":               pct(total_all > 2.5, total_matches),
            "over35_pct":               pct(total_all > 3.5, total_matches),
            "home_matches":             nh,
            "avg_goals_scored_home":    round(float(gf_h.mean()), 4) if nh > 0 else None,
            "avg_goals_conceded_home":  round(float(ga_h.mean()), 4) if nh > 0 else None,
            "avg_shots_home":           safe_mean(home_g.get("home_shots", pd.Series(dtype=float))),
            "avg_corners_home":         safe_mean(home_g.get("home_corners", pd.Series(dtype=float))),
            "btts_pct_home":            pct((gf_h > 0) & (ga_h > 0), nh),
            "over25_pct_home":          pct((gf_h + ga_h) > 2.5, nh),
            "home_win_pct":             pct(hw_h, nh),
            "away_matches":             na,
            "avg_goals_scored_away":    round(float(gf_a.mean()), 4) if na > 0 else None,
            "avg_goals_conceded_away":  round(float(ga_a.mean()), 4) if na > 0 else None,
            "avg_shots_away":           safe_mean(away_g.get("away_shots", pd.Series(dtype=float))),
            "avg_corners_away":         safe_mean(away_g.get("away_corners", pd.Series(dtype=float))),
            "btts_pct_away":            pct((gf_a > 0) & (ga_a > 0), na),
            "over25_pct_away":          pct((gf_a + ga_a) > 2.5, na),
            "away_win_pct":             pct(hw_a, na),
            "attack_strength_home":     round(float(atk_home), 4),
            "defense_strength_home":    round(float(def_home), 4),
            "attack_strength_away":     round(float(atk_away), 4),
            "defense_strength_away":    round(float(def_away), 4),
            "elo_rating":               round(float(elo_rating), 2),
            "form_last5":               json.dumps(form5, ensure_ascii=False),
            "form_last10":              json.dumps(form10, ensure_ascii=False),
            "last_match_date":          str(last_date.date()) if pd.notna(last_date) else None,
            "days_since_last_match":    days_since,
            "matches_last_14_days":     matches_14,
            "fatigue_score":            round(fatigue, 2),
            "updated_at":               datetime.now().isoformat()
        })
    
    print(f"    -> {len(records)} perfis globais calculados.")
    return records


def main():
    parser = argparse.ArgumentParser(description="Calcula e cacheia estatísticas de times e ligas.")
    parser.add_argument("--league", type=int, help="Processar apenas uma liga específica (ID)")
    args = parser.parse_args()
    
    if not supabase_client:
        print("ERRO: Supabase não configurado. Verifique .env.local")
        sys.exit(1)
    
    print("\n" + "="*70)
    print(" COMPUTE TEAM & LEAGUE STATS")
    print("="*70)
    
    df = fetch_all_matches(args.league)
    if df.empty:
        print("Nenhum jogo encontrado. Execute o backfill primeiro.")
        sys.exit(0)
    
    league_records = compute_league_stats(df)
    elo            = compute_elo_ratings(df)
    team_records   = compute_team_stats(df, elo)
    
    save_league_stats(league_records)
    save_team_stats(team_records)
    
    # Perfil global cross-liga (usado como fallback para Copa do Mundo, Eurocopa, etc.)
    if not args.league:  # Só calcula perfil global se for run completo
        global_records = compute_global_team_stats(df, elo)
        save_team_stats(global_records)
    
    print("\n" + "="*70)
    print(" CONCLUIDO COM SUCESSO!")
    print(f"  Ligas calculadas: {len(league_records)}")
    print(f"  Times calculados: {len(team_records)}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
