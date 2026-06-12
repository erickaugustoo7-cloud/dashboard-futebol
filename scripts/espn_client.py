# -*- coding: utf-8 -*-
"""
ESPN API Client Helper
Queries the unofficial ESPN API endpoints to fetch match metadata and stats.
"""

import requests
import time
from datetime import datetime

SITE_API = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# Mapeamento de League IDs da API-Sports para ESPN Slugs
LEAGUE_MAPPING = {
    71: "bra.1",                  # Brasileirão Série A
    39: "eng.1",                  # Premier League
    140: "esp.1",                 # La Liga
    135: "ita.1",                 # Serie A (ITA)
    78: "ger.1",                  # Bundesliga
    61: "fra.1",                  # Ligue 1
    2: "uefa.champions",          # UEFA Champions League
    3: "uefa.europa",             # UEFA Europa League
    13: "conmebol.libertadores",  # Copa Libertadores
    11: "conmebol.sudamericana",  # Copa Sudamericana
    73: "bra.copa_do_brazil",     # Copa do Brasil
    1: "fifa.world",              # Copa do Mundo
    9: "conmebol.america",        # Copa America
    4: "uefa.euro"                # Eurocopa
}

# Mapeamento reverso para facilitar a busca
REVERSE_LEAGUE_MAPPING = {v: k for k, v in LEAGUE_MAPPING.items()}

def get_espn_data(url: str, params: dict = None) -> dict | None:
    """Faz requisição GET de forma robusta."""
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f"   [ESPN Client Warning] Falha ao acessar {url}: {e}")
        return None

def fetch_scoreboard_day(league_slug: str, date_str: str) -> list[dict]:
    """Busca a rodada/dia da liga na ESPN scoreboard API."""
    url = f"{SITE_API}/{league_slug}/scoreboard"
    # O parâmetro dates aceita o formato YYYYMMDD
    formatted_date = date_str.replace("-", "")
    data = get_espn_data(url, params={"dates": formatted_date, "limit": 100})
    if not data:
        return []
    return data.get("events", [])

def fetch_game_summary(league_slug: str, event_id: str) -> dict | None:
    """Busca estatísticas detalhadas (cartões, offsides, etc.) de uma partida."""
    url = f"{SITE_API}/{league_slug}/summary"
    return get_espn_data(url, params={"event": event_id})

def get_stat_value(stats_list: list, stat_name: str):
    """Auxiliar para extrair valor numérico de uma lista de estatísticas da ESPN."""
    for stat in stats_list:
        if stat.get("name") == stat_name:
            val_str = stat.get("displayValue")
            if val_str is not None:
                # Remove o sinal de '%' se houver
                val_str = val_str.replace("%", "").strip()
                try:
                    if "." in val_str:
                        return float(val_str)
                    return int(val_str)
                except ValueError:
                    return None
    return None

def parse_espn_event(event: dict, summary_data: dict | None = None) -> dict | None:
    """
    Formata o JSON retornado pela ESPN para o nosso modelo unificado do Postgres.
    Combina dados do evento base com dados detalhados da summary (se disponível).
    """
    try:
        fixture_id = int(event["id"])
        competitions = event.get("competitions", [])
        if not competitions:
            return None
        comp = competitions[0]
        
        # Datas e Horários
        date_iso = comp.get("date", "")
        if not date_iso:
            return None
        
        # Parsing de data para timestamp Unix
        try:
            dt = datetime.strptime(date_iso[:19].replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
            timestamp = int(dt.timestamp())
        except ValueError:
            timestamp = 0
            
        # Status
        status_info = comp.get("status", {})
        status_type = status_info.get("type", {})
        completed = status_type.get("completed", False)
        
        status = status_type.get("shortDetail", "NS")
        if status == "FT" or completed:
            status = "FT"
        elif status in ["TBD", "Scheduled", "Pre"]:
            status = "NS"
            
        # Times e Competidores
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            return None
            
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        
        if not home or not away:
            return None
            
        home_team = home.get("team", {})
        away_team = away.get("team", {})
        
        # Gols e Placares
        goals_home = None
        goals_away = None
        score_ht_home = None
        score_ht_away = None
        score_ft_home = None
        score_ft_away = None
        
        if completed or home.get("score") is not None:
            try:
                goals_home = int(home.get("score", 0))
                goals_away = int(away.get("score", 0))
                score_ft_home = goals_home
                score_ft_away = goals_away
            except (ValueError, TypeError):
                pass
                
        # Estatísticas (Vêm da summary ou do scoreboard)
        # Se passamos a summary_data (que tem mais detalhes), usamos ela de prioridade
        home_stats = []
        away_stats = []
        
        if summary_data and "boxscore" in summary_data:
            teams_box = summary_data["boxscore"].get("teams", [])
            for t in teams_box:
                t_id = t.get("team", {}).get("id")
                if str(t_id) == str(home_team.get("id")):
                    home_stats = t.get("statistics", [])
                elif str(t_id) == str(away_team.get("id")):
                    away_stats = t.get("statistics", [])
        else:
            # Fallback para estatísticas básicas do scoreboard
            home_stats = home.get("statistics", [])
            away_stats = away.get("statistics", [])
            
        # Extrair estatísticas avançadas
        home_shots = get_stat_value(home_stats, "totalShots")
        away_shots = get_stat_value(away_stats, "totalShots")
        
        home_sog = get_stat_value(home_stats, "shotsOnTarget")
        away_sog = get_stat_value(away_stats, "shotsOnTarget")
        
        home_possession = get_stat_value(home_stats, "possessionPct")
        away_possession = get_stat_value(away_stats, "possessionPct")
        
        home_corners = get_stat_value(home_stats, "wonCorners")
        away_corners = get_stat_value(away_stats, "wonCorners")
        
        home_yellow_cards = get_stat_value(home_stats, "yellowCards")
        away_yellow_cards = get_stat_value(away_stats, "yellowCards")
        
        home_red_cards = get_stat_value(home_stats, "redCards")
        away_red_cards = get_stat_value(away_stats, "redCards")
        
        home_fouls = get_stat_value(home_stats, "foulsCommitted")
        away_fouls = get_stat_value(away_stats, "foulsCommitted")
        
        home_offsides = get_stat_value(home_stats, "offsides")
        away_offsides = get_stat_value(away_stats, "offsides")

        # Nome do Campeonato e Ligas
        season_year = int(event.get("season", {}).get("year", datetime.now().year))
        
        return {
            "fixture_id": fixture_id,
            "season": season_year,
            "date": date_iso,
            "timestamp": timestamp,
            "status": status,
            "home_team_id": int(home_team.get("id", 0)),
            "home_team_name": home_team.get("displayName", "Casa"),
            "away_team_id": int(away_team.get("id", 0)),
            "away_team_name": away_team.get("displayName", "Fora"),
            "goals_home": goals_home,
            "goals_away": goals_away,
            "score_ht_home": score_ht_home,
            "score_ht_away": score_ht_away,
            "score_ft_home": score_ft_home,
            "score_ft_away": score_ft_away,
            
            # Stats avançadas
            "home_shots": home_shots,
            "away_shots": away_shots,
            "home_sog": home_sog,
            "away_sog": away_sog,
            "home_possession": home_possession,
            "away_possession": away_possession,
            "home_corners": home_corners,
            "away_corners": away_corners,
            "home_yellow_cards": home_yellow_cards,
            "away_yellow_cards": away_yellow_cards,
            "home_red_cards": home_red_cards,
            "away_red_cards": away_red_cards,
            "home_fouls": home_fouls,
            "away_fouls": away_fouls,
            "home_offsides": home_offsides,
            "away_offsides": away_offsides
        }
    except Exception as e:
        print(f"   [ESPN Parser Error] Falha ao fazer parse do evento: {e}")
        return None
