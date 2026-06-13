# -*- coding: utf-8 -*-
"""
=============================================================
  TEST ESPN API v2 - Brasileirao Serie A (bra.1) | 2022-2026
=============================================================
Endpoint correto: site.api.espn.com/apis/site/v2
Navega pelo calendario da liga, dia a dia, coletando todos os jogos.

Como rodar:
  python scripts/test_espn_brasileirao.py
=============================================================
"""

import sys
import io
import requests
import json
import time
from datetime import datetime, date, timedelta

# Forcar UTF-8 no terminal do Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ── Configuracoes ───────────────────────────────────────────
SITE_API    = "https://site.api.espn.com/apis/site/v2/sports/soccer"
LEAGUE      = "bra.1"
SEASONS     = [2022, 2023, 2024, 2025, 2026]
DELAY       = 0.4  # segundos entre requisicoes

# Datas aproximadas do Brasileirao por ano (inicio - fim)
SEASON_DATES = {
    2022: ("2022-04-10", "2022-11-13"),
    2023: ("2023-04-15", "2023-12-06"),
    2024: ("2024-04-13", "2024-12-08"),
    2025: ("2025-03-29", "2025-12-07"),
    2026: ("2026-01-28", "2026-12-02"),
}

# ── Helpers ─────────────────────────────────────────────────
def get(url: str, params: dict = None) -> dict | None:
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f"   [ERRO] {e}")
        return None

def parse_competition(comp: dict) -> dict | None:
    """Extrai os dados relevantes de uma competicao (jogo)."""
    competitors = comp.get("competitors", [])
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})

    status = comp.get("status", {})
    status_type = status.get("type", {})

    def get_stat(team_data: dict, stat_name: str) -> str:
        for s in team_data.get("statistics", []):
            if s.get("name") == stat_name:
                return s.get("displayValue", "-")
        return "-"

    home_team = home.get("team", {})
    away_team = away.get("team", {})

    return {
        "home":         home_team.get("displayName", "?"),
        "away":         away_team.get("displayName", "?"),
        "home_score":   home.get("score", "-"),
        "away_score":   away.get("score", "-"),
        "home_winner":  home.get("winner", False),
        "status":       status_type.get("shortDetail", "?"),
        "completed":    status_type.get("completed", False),
        "venue":        comp.get("venue", {}).get("fullName", "-"),
        # Stats de time quando disponivel
        "home_shots":   get_stat(home, "totalShots"),
        "away_shots":   get_stat(away, "totalShots"),
        "home_sog":     get_stat(home, "shotsOnTarget"),
        "away_sog":     get_stat(away, "shotsOnTarget"),
        "home_poss":    get_stat(home, "possessionPct"),
        "away_poss":    get_stat(away, "possessionPct"),
    }

def fetch_day(date_str: str) -> list[dict]:
    """Busca todos os jogos do Brasileirao em uma data especifica."""
    url = f"{SITE_API}/{LEAGUE}/scoreboard"
    data = get(url, params={"dates": date_str.replace("-", ""), "limit": 50})
    if not data:
        return []

    games = []
    for event in data.get("events", []):
        date_val = event.get("date", "")[:10]
        name     = event.get("name", "")
        comps    = event.get("competitions", [{}])
        comp     = comps[0] if comps else {}
        parsed   = parse_competition(comp)
        if parsed:
            parsed["date"] = date_val
            parsed["name"] = name
            games.append(parsed)
    return games


def fetch_season_by_calendar(season: int) -> list[dict]:
    """
    Estrategia corrigida: usa datas fixas por temporada para garantir
    que cada ano busca os dados corretos (o parametro ?season= da ESPN
    nao filtra historico — sempre retorna o calendario atual).
    """
    all_games = []

    start_str, end_str = SEASON_DATES.get(season, (f"{season}-04-01", f"{season}-12-15"))
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    end   = datetime.strptime(end_str,   "%Y-%m-%d").date()

    print(f"   Periodo: {start_str} -> {end_str}")

    # Estrategia: busca a cada 3 dias para cobrir todas as rodadas
    # O Brasileirao joga tipicamente sab/dom e qua/qui
    # Buscar de 3 em 3 dias garante cobertura completa sem muitas requisicoes vazias
    dates_to_check = []
    current = start
    while current <= end:
        dates_to_check.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=3)

    # Garante que o dia final tbm seja checado
    if end.strftime("%Y-%m-%d") not in dates_to_check:
        dates_to_check.append(end.strftime("%Y-%m-%d"))

    print(f"   Datas a consultar: {len(dates_to_check)} (intervalo de 3 dias)")

    days_with_games = 0
    for i, day in enumerate(dates_to_check):
        games = fetch_day(day)
        if games:
            # Filtra apenas jogos que pertencem a esta temporada
            season_games = [g for g in games if g["date"].startswith(str(season))]
            if season_games:
                all_games.extend(season_games)
                completed = sum(1 for g in season_games if g["completed"])
                days_with_games += 1
                print(f"   [{i+1:3}/{len(dates_to_check)}] {day}: {len(season_games)} jogo(s) ({completed} finalizado(s))")
        time.sleep(DELAY)

    print(f"   Total de dias com jogos encontrados: {days_with_games}")
    return all_games


# ── Exibicao de resultados ───────────────────────────────────
def print_sample(games: list[dict], n: int = 10):
    """Exibe uma tabela com os primeiros N jogos."""
    print(f"\n  {'#':<4} {'Data':<12} {'Casa':<28} {'Placar':<9} {'Fora':<28} {'Status':<8} {'Shots H/A':<12} {'Poss H/A'}")
    print(f"  {'-'*115}")
    for i, g in enumerate(games[:n], 1):
        score   = f"{g['home_score']} x {g['away_score']}"
        shots   = f"{g['home_shots']}/{g['away_shots']}"
        poss    = f"{g['home_poss']}/{g['away_poss']}"
        winner  = " [W]" if g["home_winner"] else ""
        print(f"  {i:<4} {g['date']:<12} {g['home']:<28} {score:<9} {g['away']:<28} {g['status']:<8} {shots:<12} {poss}")


# ── Main ─────────────────────────────────────────────────────
def main():
    print("\n" + "="*65)
    print("  ESPN API v2 - TESTE BRASILEIRAO 2022-2026")
    print("="*65)
    print(f"\n  Iniciado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Endpoint: {SITE_API}/{LEAGUE}/scoreboard")
    print(f"  Temporadas: {SEASONS}")
    print(f"  Sem API key - acesso publico direto\n")

    all_results = {}

    for season in SEASONS:
        print(f"\n{'='*65}")
        print(f"  TEMPORADA {season}")
        print(f"{'='*65}")

        games = fetch_season_by_calendar(season)
        completed = [g for g in games if g["completed"]]
        scheduled = [g for g in games if not g["completed"]]

        print(f"\n  Resultado {season}:")
        print(f"    Total de jogos encontrados : {len(games)}")
        print(f"    Jogos finalizados           : {len(completed)}")
        print(f"    Jogos agendados/em andamento: {len(scheduled)}")

        if completed:
            # Stats adicionais
            has_shots = sum(1 for g in completed if g["home_shots"] != "-")
            has_poss  = sum(1 for g in completed if g["home_poss"] != "-")
            print(f"    Jogos c/ dados de chutes    : {has_shots}")
            print(f"    Jogos c/ posse de bola      : {has_poss}")

            print(f"\n  Amostra dos ultimos 10 jogos finalizados:")
            print_sample(completed[-10:])

        all_results[season] = {
            "total":     len(games),
            "completed": len(completed),
            "scheduled": len(scheduled),
            "games":     games,
        }
        time.sleep(1)

    # Resumo final
    print(f"\n\n{'='*65}")
    print("  RESUMO FINAL")
    print(f"{'='*65}")
    print(f"\n  {'Temporada':<12} {'Total':<8} {'Finalizados':<14} {'Agendados':<12} {'Stats?'}")
    print(f"  {'-'*60}")
    for s, r in all_results.items():
        games = r["games"]
        comp  = r["games"][:r["completed"]] if r["completed"] else []
        has_stats = "Sim" if any(g["home_shots"] != "-" for g in games) else "Nao"
        print(f"  {s:<12} {r['total']:<8} {r['completed']:<14} {r['scheduled']:<12} {has_stats}")

    total = sum(r["total"] for r in all_results.values())
    total_done = sum(r["completed"] for r in all_results.values())
    print(f"\n  Total geral     : {total} jogos")
    print(f"  Total finalizados: {total_done} jogos")
    print(f"\n  Teste concluido as {datetime.now().strftime('%H:%M:%S')}")

    # Salvar resultado em JSON (sem a lista completa de jogos p/ nao ser enorme)
    summary = {s: {k: v for k, v in r.items() if k != "games"} for s, r in all_results.items()}
    # Salva amostra de 20 jogos por ano
    for s, r in all_results.items():
        summary[s]["sample_games"] = r["games"][:20]

    output_path = "scripts/espn_test_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n  Resultado salvo em: {output_path}")
    print("  (Amostra de 20 jogos por temporada incluida)\n")


if __name__ == "__main__":
    main()
