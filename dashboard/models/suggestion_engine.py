# -*- coding: utf-8 -*-
"""
=============================================================
  SUGGESTION ENGINE — Football Monitor
=============================================================
Motor de análise em 3 níveis que gera sugestões simples e
combinadas para partidas de futebol com base em:
  - Nível 1: Contexto da liga (médias globais)
  - Nível 2: Form recente + ELO dos times (Poisson com decay)
  - Nível 3: H2H (head-to-head histórico)

Como usar:
  from suggestion_engine import SuggestionEngine
  engine = SuggestionEngine(supabase_client)
  
  # Analisar 1 jogo
  analysis = engine.analyze_match(fixture_id=12345)
  
  # Sugestões do dia
  suggestions = engine.get_daily_suggestions(date="2026-06-12", leagues=[71, 39])
=============================================================
"""

import json
import math
from datetime import datetime, timedelta, date
from typing import Optional
import numpy as np
from scipy.stats import poisson


# ──────────────────────────────────────────────────────────────
# PESOS DO MODELO COMPOSTO
# ──────────────────────────────────────────────────────────────
WEIGHTS = {
    "poisson": 0.40,  # Força de ataque/defesa histórica
    "form":    0.30,  # Forma recente (últimas 5-10 partidas)
    "h2h":     0.20,  # Histórico H2H
    "league":  0.10,  # Consistência com médias da liga
}

# Limites de confiança para classificação
CONFIDENCE_HIGH   = 65.0
CONFIDENCE_MEDIUM = 55.0

# Mínimo de partidas para considerar estatísticas confiáveis
MIN_MATCHES_RELIABLE = 8


class SuggestionEngine:
    """Motor de análise e sugestões para partidas de futebol."""

    def __init__(self, supabase_client):
        self.sb = supabase_client

    # ──────────────────────────────────────────────────────────
    # ANÁLISE COMPLETA DE UMA PARTIDA
    # ──────────────────────────────────────────────────────────
    def analyze_match(self, fixture_id: int) -> dict:
        """
        Retorna análise completa de 3 níveis para uma partida.
        """
        match = self._get_match(fixture_id)
        if not match:
            return {"error": f"Partida {fixture_id} não encontrada"}

        home_id    = match["home_team_id"]
        away_id    = match["away_team_id"]
        league_id  = match["league_id"]
        season     = match["season"]

        # ── Buscar dados ──
        home_stats  = self._get_team_stats(home_id, league_id, season)
        away_stats  = self._get_team_stats(away_id, league_id, season)
        league_data = self._get_league_stats(league_id, season)
        h2h_data    = self._get_h2h(home_id, away_id, n=10)

        # ── Nível 1: Poisson com forças relativas ──
        poisson_result = self._run_poisson(home_stats, away_stats, league_data)

        # ── Nível 2: Ajuste por form recente ──
        form_adjustment = self._calc_form_adjustment(home_stats, away_stats)

        # ── Nível 3: H2H ──
        h2h_result = self._analyze_h2h(h2h_data)

        # ── Composição final das probabilidades ──
        final_probs = self._compose_probabilities(
            poisson_result, form_adjustment, h2h_result, league_data
        )

        # ── Gerar sugestões ──
        suggestions = self._generate_suggestions(final_probs, h2h_result, home_stats, away_stats, league_data)

        return {
            "fixture_id":   fixture_id,
            "match":        match,
            "level1_poisson":   poisson_result,
            "level2_form":      form_adjustment,
            "level3_h2h":       h2h_result,
            "final_probs":      final_probs,
            "suggestions":      suggestions,
            "main_suggestion":  suggestions[0] if suggestions else None,
        }

    # ──────────────────────────────────────────────────────────
    # SUGESTÕES DO DIA
    # ──────────────────────────────────────────────────────────
    def get_daily_suggestions(
        self,
        target_date: str = None,
        leagues: list[int] = None,
        min_confidence: float = CONFIDENCE_MEDIUM,
        max_combined: int = 5
    ) -> dict:
        """
        Retorna sugestões simples e combinadas para um dia.
        
        Args:
            target_date: Data no formato 'YYYY-MM-DD' (padrão: hoje)
            leagues: Lista de IDs de ligas (padrão: todas)
            min_confidence: Confiança mínima para incluir nas combinadas
            max_combined: Máximo de jogos na combinada
        """
        if target_date is None:
            target_date = date.today().isoformat()
        
        # Busca partidas do dia
        matches = self._get_matches_by_date(target_date, leagues)
        
        analyzed = []
        for match in matches:
            try:
                result = self.analyze_match(match["fixture_id"])
                if result.get("main_suggestion"):
                    analyzed.append(result)
            except Exception as e:
                print(f"Erro ao analisar partida {match.get('fixture_id')}: {e}")
        
        # Ordena por confiança decrescente
        analyzed.sort(
            key=lambda x: x["main_suggestion"]["confidence"] if x.get("main_suggestion") else 0,
            reverse=True
        )
        
        # Filtra para combinadas
        high_confidence = [
            a for a in analyzed
            if a.get("main_suggestion", {}).get("confidence", 0) >= min_confidence
        ]
        
        # Gera combinadas (2, 3, até max_combined)
        combinadas = self._build_combinadas(high_confidence, max_combined)
        
        return {
            "date":          target_date,
            "total_matches": len(matches),
            "analyzed":      len(analyzed),
            "simples":       [a["main_suggestion"] for a in analyzed if a.get("main_suggestion")],
            "combinadas":    combinadas,
        }

    # ──────────────────────────────────────────────────────────
    # NÍVEL 1: POISSON
    # ──────────────────────────────────────────────────────────
    def _run_poisson(self, home_stats: dict, away_stats: dict, league: dict) -> dict:
        """Calcula xG e probabilidades via modelo de Poisson com forças relativas."""
        max_goals = 7
        
        if not home_stats or not away_stats or not league:
            # Fallback para médias genéricas
            home_xg = 1.35
            away_xg = 1.10
        else:
            avg_h = league.get("avg_home_goals", 1.35)
            avg_a = league.get("avg_away_goals", 1.10)
            
            atk_h = home_stats.get("attack_strength_home", 1.0)
            def_h = home_stats.get("defense_strength_home", 1.0)
            atk_a = away_stats.get("attack_strength_away", 1.0)
            def_a = away_stats.get("defense_strength_away", 1.0)
            
            # ELO adjustment (±5% por 100 pontos de diferença)
            elo_h = home_stats.get("elo_rating", 1500)
            elo_a = away_stats.get("elo_rating", 1500)
            elo_diff = (elo_h - elo_a) / 100
            elo_factor = 1 + (elo_diff * 0.05)
            elo_factor = max(0.80, min(1.20, elo_factor))
            
            home_xg = atk_h * def_a * avg_h * elo_factor
            away_xg = atk_a * def_h * avg_a / max(elo_factor, 0.85)
        
        # Clamp xG para valores razoáveis
        home_xg = max(0.3, min(home_xg, 4.5))
        away_xg = max(0.3, min(away_xg, 4.5))
        
        # Matriz de probabilidades de placar
        home_pmf = [poisson.pmf(i, home_xg) for i in range(max_goals)]
        away_pmf = [poisson.pmf(i, away_xg) for i in range(max_goals)]
        matrix = np.outer(home_pmf, away_pmf)
        
        # Dixon-Coles: ajuste para correlação nos placares baixos (0-0, 1-0, 0-1, 1-1)
        rho = -0.13
        matrix[0, 0] *= (1 - rho)
        matrix[0, 1] *= (1 + rho)
        matrix[1, 0] *= (1 + rho)
        matrix[1, 1] *= (1 - rho)
        
        # Normaliza
        matrix /= matrix.sum()
        
        home_win = float(np.sum(np.tril(matrix, -1)))
        draw     = float(np.sum(np.diag(matrix)))
        away_win = float(np.sum(np.triu(matrix, 1)))
        
        # Over/Under
        total_goals_matrix = np.zeros((max_goals, max_goals))
        for i in range(max_goals):
            for j in range(max_goals):
                total_goals_matrix[i, j] = i + j
        
        over15 = float(np.sum(matrix[total_goals_matrix > 1.5]))
        over25 = float(np.sum(matrix[total_goals_matrix > 2.5]))
        over35 = float(np.sum(matrix[total_goals_matrix > 3.5]))
        
        # BTTS
        btts = 1.0 - float(matrix[0, :].sum() + matrix[:, 0].sum() - matrix[0, 0])
        
        # Placar mais provável
        best_idx = np.unravel_index(np.argmax(matrix), matrix.shape)
        
        return {
            "home_xg":          round(home_xg, 3),
            "away_xg":          round(away_xg, 3),
            "home_win_prob":    round(home_win * 100, 2),
            "draw_prob":        round(draw * 100, 2),
            "away_win_prob":    round(away_win * 100, 2),
            "btts_prob":        round(btts * 100, 2),
            "over15_prob":      round(over15 * 100, 2),
            "over25_prob":      round(over25 * 100, 2),
            "over35_prob":      round(over35 * 100, 2),
            "most_likely_score": f"{best_idx[0]}-{best_idx[1]}",
            "score_prob":       round(float(matrix[best_idx]) * 100, 2),
        }

    # ──────────────────────────────────────────────────────────
    # NÍVEL 2: FORM RECENTE
    # ──────────────────────────────────────────────────────────
    def _calc_form_adjustment(self, home_stats: dict, away_stats: dict) -> dict:
        """Calcula ajuste baseado na forma recente dos times."""
        def parse_form(stats, key="form_last5"):
            if not stats:
                return None
            raw = stats.get(key)
            if isinstance(raw, str):
                try:
                    return json.loads(raw)
                except:
                    return None
            return raw
        
        home_form5 = parse_form(home_stats)
        away_form5 = parse_form(away_stats)
        
        def form_score(form: dict) -> float:
            """Converte form em score 0-1 (0.5 = neutro)."""
            if not form or not form.get("n"):
                return 0.5
            n = form["n"]
            pts = form.get("points", 0)
            max_pts = n * 3
            return pts / max_pts if max_pts > 0 else 0.5
        
        hs = form_score(home_form5)
        as_ = form_score(away_form5)
        
        # Diferença de form: positivo = casa favorecida
        form_diff = hs - as_
        
        # Traduz em ajuste de probabilidade (±10% máximo)
        adj = form_diff * 0.15
        
        return {
            "home_form_score":  round(hs * 100, 1),
            "away_form_score":  round(as_ * 100, 1),
            "form_difference":  round(form_diff * 100, 1),
            "home_adjustment":  round(adj * 100, 2),  # % de ajuste nas probs
            "home_form5":       home_form5,
            "away_form5":       away_form5,
            "home_avg_gf_last5": home_form5.get("avg_gf") if home_form5 else None,
            "home_avg_ga_last5": home_form5.get("avg_ga") if home_form5 else None,
            "away_avg_gf_last5": away_form5.get("avg_gf") if away_form5 else None,
            "away_avg_ga_last5": away_form5.get("avg_ga") if away_form5 else None,
        }

    # ──────────────────────────────────────────────────────────
    # NÍVEL 3: H2H
    # ──────────────────────────────────────────────────────────
    def _analyze_h2h(self, h2h: list[dict]) -> dict:
        """Analisa histórico de confrontos diretos."""
        if not h2h:
            return {"available": False, "n": 0}
        
        n = len(h2h)
        home_wins = sum(1 for m in h2h if m["result"] == "home")
        draws     = sum(1 for m in h2h if m["result"] == "draw")
        away_wins = sum(1 for m in h2h if m["result"] == "away")
        btts      = sum(1 for m in h2h if m.get("btts"))
        over25    = sum(1 for m in h2h if m.get("over25"))
        
        total_gf = sum(m.get("goals_home", 0) or 0 for m in h2h)
        total_ga = sum(m.get("goals_away", 0) or 0 for m in h2h)
        
        return {
            "available":    True,
            "n":            n,
            "home_win_pct": round(home_wins / n * 100, 1),
            "draw_pct":     round(draws / n * 100, 1),
            "away_win_pct": round(away_wins / n * 100, 1),
            "btts_pct":     round(btts / n * 100, 1),
            "over25_pct":   round(over25 / n * 100, 1),
            "avg_goals":    round((total_gf + total_ga) / n, 2),
            "matches":      h2h[:5],  # últimos 5 para display
        }

    # ──────────────────────────────────────────────────────────
    # COMPOSIÇÃO FINAL
    # ──────────────────────────────────────────────────────────
    def _compose_probabilities(
        self,
        poisson_r: dict,
        form_r: dict,
        h2h_r: dict,
        league: dict
    ) -> dict:
        """Combina os 3 níveis com pesos para probabilidades finais."""
        
        # Base: Poisson
        p_home = poisson_r["home_win_prob"] / 100
        p_draw = poisson_r["draw_prob"] / 100
        p_away = poisson_r["away_win_prob"] / 100
        p_over25 = poisson_r["over25_prob"] / 100
        p_btts   = poisson_r["btts_prob"] / 100
        
        # Ajuste de form (apenas shift pequeno)
        form_adj = form_r.get("home_adjustment", 0) / 100
        p_home = max(0.05, p_home + form_adj * WEIGHTS["form"])
        p_away = max(0.05, p_away - form_adj * WEIGHTS["form"])
        
        # Ajuste H2H
        if h2h_r.get("available") and h2h_r["n"] >= 4:
            w = WEIGHTS["h2h"]
            h2h_home = h2h_r["home_win_pct"] / 100
            h2h_draw = h2h_r["draw_pct"] / 100
            h2h_away = h2h_r["away_win_pct"] / 100
            h2h_over = h2h_r["over25_pct"] / 100
            h2h_btts = h2h_r["btts_pct"] / 100
            
            p_home  = (1 - w) * p_home  + w * h2h_home
            p_draw  = (1 - w) * p_draw  + w * h2h_draw
            p_away  = (1 - w) * p_away  + w * h2h_away
            p_over25 = (1 - w) * p_over25 + w * h2h_over
            p_btts   = (1 - w) * p_btts  + w * h2h_btts
        
        # Normaliza 1X2
        total = p_home + p_draw + p_away
        if total > 0:
            p_home /= total
            p_draw /= total
            p_away /= total
        
        def fair_odd(p):
            return round(1 / p, 2) if p > 0.01 else 0.0
        
        return {
            "home_win_prob": round(p_home * 100, 2),
            "draw_prob":     round(p_draw * 100, 2),
            "away_win_prob": round(p_away * 100, 2),
            "home_odd":      fair_odd(p_home),
            "draw_odd":      fair_odd(p_draw),
            "away_odd":      fair_odd(p_away),
            "btts_prob":     round(p_btts * 100, 2),
            "over15_prob":   poisson_r["over15_prob"],
            "over25_prob":   round(p_over25 * 100, 2),
            "over35_prob":   poisson_r["over35_prob"],
            "home_xg":       poisson_r["home_xg"],
            "away_xg":       poisson_r["away_xg"],
            "most_likely_score": poisson_r["most_likely_score"],
        }

    # ──────────────────────────────────────────────────────────
    # GERAÇÃO DE SUGESTÕES
    # ──────────────────────────────────────────────────────────
    def _generate_suggestions(
        self,
        probs: dict,
        h2h: dict,
        home_stats: dict,
        away_stats: dict,
        league: dict
    ) -> list[dict]:
        """Gera lista de sugestões ordenadas por confiança."""
        suggestions = []
        
        # ── Contexto adicional para calcular confiança ──
        league_over25 = (league or {}).get("over25_pct", 50)
        league_btts   = (league or {}).get("btts_pct", 50)
        h2h_n         = h2h.get("n", 0)
        h2h_available = h2h.get("available", False)
        
        def build_suggestion(market: str, label: str, prob: float, context_prob: float = None) -> dict:
            """Constrói uma sugestão com cálculo de confiança."""
            base_conf = prob
            
            # Bonus de convergência com H2H e liga
            bonus = 0.0
            if h2h_available and h2h_n >= 4:
                h2h_prob = h2h.get(f"{market}_pct", prob * 100) / 100
                convergence = 1 - abs(prob / 100 - h2h_prob)
                bonus += convergence * 5  # até +5 pontos de bônus
            
            if context_prob is not None:
                league_convergence = 1 - abs(prob - context_prob) / 100
                bonus += league_convergence * 3  # até +3 pontos de bônus
            
            confidence = min(95, base_conf + bonus)
            
            if confidence >= CONFIDENCE_HIGH:
                level = "high"
            elif confidence >= CONFIDENCE_MEDIUM:
                level = "medium"
            else:
                level = "low"
            
            return {
                "market":          market,
                "label":           label,
                "probability":     round(prob, 1),
                "confidence":      round(confidence, 1),
                "confidence_level": level,
                "fair_odd":        round(100 / prob, 2) if prob > 1 else 0,
            }
        
        # Over 2.5
        if probs["over25_prob"] > 50:
            suggestions.append(build_suggestion(
                "over25", "Over 2.5 Gols",
                probs["over25_prob"], league_over25
            ))
        
        # Under 2.5
        if (100 - probs["over25_prob"]) > 52:
            suggestions.append(build_suggestion(
                "under25", "Under 2.5 Gols",
                100 - probs["over25_prob"], 100 - league_over25
            ))
        
        # BTTS - Sim
        if probs["btts_prob"] > 50:
            suggestions.append(build_suggestion(
                "btts_yes", "Ambos Marcam - Sim",
                probs["btts_prob"], league_btts
            ))
        
        # BTTS - Não
        if (100 - probs["btts_prob"]) > 52:
            suggestions.append(build_suggestion(
                "btts_no", "Ambos Marcam - Não",
                100 - probs["btts_prob"], 100 - league_btts
            ))
        
        # Resultado 1X2
        home_p = probs["home_win_prob"]
        draw_p = probs["draw_prob"]
        away_p = probs["away_win_prob"]
        
        if home_p > 55:
            suggestions.append(build_suggestion("home_win", "Vitória Mandante", home_p))
        if draw_p > 35:
            suggestions.append(build_suggestion("draw", "Empate", draw_p))
        if away_p > 45:
            suggestions.append(build_suggestion("away_win", "Vitória Visitante", away_p))
        
        # Dupla hipótese (1X, X2, 12)
        if home_p + draw_p > 72:
            suggestions.append(build_suggestion(
                "1x", "Mandante ou Empate (1X)",
                home_p + draw_p
            ))
        if away_p + draw_p > 68:
            suggestions.append(build_suggestion(
                "x2", "Visitante ou Empate (X2)",
                away_p + draw_p
            ))
        
        # Over 1.5
        if probs["over15_prob"] > 80:
            suggestions.append(build_suggestion("over15", "Over 1.5 Gols", probs["over15_prob"]))
        
        # Corners (se disponível)
        home_corners = (home_stats or {}).get("avg_corners_home")
        away_corners = (away_stats or {}).get("avg_corners_away")
        if home_corners and away_corners:
            avg_corners = home_corners + away_corners
            if avg_corners > 10.5:
                suggestions.append(build_suggestion(
                    "corners_over105", "Escanteios Over 10.5",
                    min(75, 45 + (avg_corners - 10.5) * 5)
                ))
            elif avg_corners < 8.5:
                suggestions.append(build_suggestion(
                    "corners_under85", "Escanteios Under 8.5",
                    min(72, 45 + (8.5 - avg_corners) * 5)
                ))
        
        # Ordena por confiança
        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        return suggestions

    # ──────────────────────────────────────────────────────────
    # CONSTRUÇÃO DE APOSTAS COMBINADAS
    # ──────────────────────────────────────────────────────────
    def _build_combinadas(self, analyzed: list[dict], max_legs: int = 5) -> list[dict]:
        """Monta apostas combinadas com os jogos de maior confiança."""
        # Filtra apenas confiança alta
        high = [
            a for a in analyzed
            if a.get("main_suggestion", {}).get("confidence_level") in ("high", "medium")
        ]
        
        if len(high) < 2:
            return []
        
        combinadas = []
        
        for n_legs in range(2, min(max_legs + 1, len(high) + 1)):
            # Pega os N melhores jogos (evita 2 jogos do mesmo time)
            selected = []
            used_teams = set()
            
            for item in high:
                match = item.get("match", {})
                home_id = match.get("home_team_id")
                away_id = match.get("away_team_id")
                
                if home_id in used_teams or away_id in used_teams:
                    continue
                
                selected.append(item)
                used_teams.add(home_id)
                used_teams.add(away_id)
                
                if len(selected) == n_legs:
                    break
            
            if len(selected) < n_legs:
                continue
            
            # Calcula odd combinada e probabilidade conjunta
            combined_prob = 1.0
            combined_odd  = 1.0
            legs_info = []
            
            for item in selected:
                sg = item["main_suggestion"]
                prob = sg["probability"] / 100
                odd  = sg["fair_odd"]
                
                combined_prob *= prob
                combined_odd  *= odd
                
                match = item.get("match", {})
                legs_info.append({
                    "fixture_id":    item["fixture_id"],
                    "home_team":     match.get("home_team_name"),
                    "away_team":     match.get("away_team_name"),
                    "league":        match.get("league_name"),
                    "date":          match.get("date"),
                    "market":        sg["market"],
                    "label":         sg["label"],
                    "probability":   sg["probability"],
                    "confidence":    sg["confidence"],
                    "fair_odd":      sg["fair_odd"],
                })
            
            # Expected Value: EV = (prob * odd) - 1 → positivo = vale apostar
            ev = combined_prob * combined_odd - 1
            avg_confidence = sum(l["confidence"] for l in legs_info) / n_legs
            
            combinadas.append({
                "type":               f"{n_legs}-fold",
                "label":              f"{'Dupla' if n_legs==2 else 'Tripla' if n_legs==3 else str(n_legs)+'x'}",
                "legs":               legs_info,
                "combined_probability": round(combined_prob * 100, 2),
                "combined_odd":       round(combined_odd, 2),
                "expected_value":     round(ev * 100, 2),
                "avg_confidence":     round(avg_confidence, 1),
                "ev_positive":        ev > 0,
            })
        
        return combinadas

    # ──────────────────────────────────────────────────────────
    # HELPERS: CONSULTAS AO SUPABASE
    # ──────────────────────────────────────────────────────────
    def _get_match(self, fixture_id: int) -> Optional[dict]:
        r = self.sb.table("matches").select("*").eq("fixture_id", fixture_id).single().execute()
        return r.data

    def _get_team_stats(self, team_id: int, league_id: int, season: int) -> Optional[dict]:
        r = (
            self.sb.table("team_stats_cache")
            .select("*")
            .eq("team_id", team_id)
            .eq("league_id", league_id)
            .eq("season", season)
            .limit(1)
            .execute()
        )
        return r.data[0] if r.data else None

    def _get_league_stats(self, league_id: int, season: int) -> Optional[dict]:
        r = (
            self.sb.table("league_stats_cache")
            .select("*")
            .eq("league_id", league_id)
            .eq("season", season)
            .limit(1)
            .execute()
        )
        return r.data[0] if r.data else None

    def _get_h2h(self, home_id: int, away_id: int, n: int = 10) -> list[dict]:
        # Busca confrontos em ambas as direções
        r1 = (
            self.sb.table("matches")
            .select("fixture_id,date,home_team_id,home_team_name,away_team_id,away_team_name,goals_home,goals_away")
            .eq("home_team_id", home_id)
            .eq("away_team_id", away_id)
            .eq("status", "FT")
            .order("date", desc=True)
            .limit(n)
            .execute()
        )
        r2 = (
            self.sb.table("matches")
            .select("fixture_id,date,home_team_id,home_team_name,away_team_id,away_team_name,goals_home,goals_away")
            .eq("home_team_id", away_id)
            .eq("away_team_id", home_id)
            .eq("status", "FT")
            .order("date", desc=True)
            .limit(n)
            .execute()
        )
        
        all_matches = (r1.data or []) + (r2.data or [])
        all_matches.sort(key=lambda x: x.get("date", ""), reverse=True)
        
        result = []
        for m in all_matches[:n]:
            gh = m.get("goals_home") or 0
            ga = m.get("goals_away") or 0
            # Normaliza: always from home_id perspective
            if m["home_team_id"] == home_id:
                gf, gc = gh, ga
            else:
                gf, gc = ga, gh
            
            result.append({
                "date":       m.get("date", "")[:10],
                "goals_home": gf,
                "goals_away": gc,
                "result":     "home" if gf > gc else ("away" if gf < gc else "draw"),
                "btts":       gf > 0 and gc > 0,
                "over25":     (gf + gc) > 2.5,
            })
        
        return result

    def _get_matches_by_date(self, target_date: str, leagues: list[int] = None) -> list[dict]:
        """Busca partidas agendadas em uma data."""
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        start = dt.isoformat() + "Z"
        end   = (dt + timedelta(days=1)).isoformat() + "Z"
        
        q = (
            self.sb.table("matches")
            .select("fixture_id,league_id,home_team_id,away_team_id,date,status")
            .eq("status", "NS")
            .gte("date", start)
            .lt("date", end)
        )
        if leagues:
            q = q.in_("league_id", leagues)
        
        r = q.order("date").execute()
        return r.data or []
