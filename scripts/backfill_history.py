# -*- coding: utf-8 -*-
"""
=============================================================
  BACKFILL HISTORY — ESPN API to Supabase (PostgreSQL)
=============================================================
Busca dados históricos completos das ligas selecionadas de
2022 a 2026 na API pública da ESPN e salva no Supabase.

Estatísticas coletadas:
  - Gols, placares do primeiro e segundo tempo
  - Chutes totais e chutes no gol (SOG)
  - Posse de bola
  - Escanteios (Corners)
  - Cartões amarelos e vermelhos
  - Faltas e impedimentos

Como rodar:
  python scripts/backfill_history.py
=============================================================
"""

import sys
import io
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Forçar UTF-8 no terminal do Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from supabase_client import supabase_client
from espn_client import (
    LEAGUE_MAPPING,
    fetch_scoreboard_day,
    fetch_game_summary,
    parse_espn_event
)

# Configurações do Backfill
# Ligas a processar (mapeadas no espn_client.py)
LEAGUES_TO_PROCESS = [71, 39, 140, 135, 78, 61, 2, 3, 13, 11, 73, 1, 9, 4]
SEASONS = [2022, 2023, 2024, 2025, 2026]

# Nomes legíveis das ligas (para gravar no banco)
LEAGUE_DISPLAY_NAMES = {
    71:  "Brasileirão Série A",
    39:  "Premier League",
    140: "La Liga",
    135: "Serie A",
    78:  "Bundesliga",
    61:  "Ligue 1",
    2:   "UEFA Champions League",
    3:   "UEFA Europa League",
    13:  "Copa Libertadores",
    11:  "Copa Sul-Americana",
    73:  "Copa do Brasil",
    1:   "Copa do Mundo FIFA",
    9:   "Copa América",
    4:   "Eurocopa",
}

DELAY_BETWEEN_DAYS = 0.3    # Ser gentil com a API da ESPN
DELAY_SUMMARY = 0.2         # Delay para requisições de resumo do jogo

def get_season_date_range(league_slug: str, season: int) -> tuple[str, str]:
    """Retorna a janela de datas aproximadas de uma temporada para cada liga."""
    if league_slug == "fifa.world":
        if season == 2022:
            return "2022-11-18", "2022-12-22"
        return f"{season}-06-01", f"{season}-07-31"
        
    if league_slug == "conmebol.america":
        if season == 2024:
            return "2024-06-18", "2024-07-20"
        return f"{season}-06-01", f"{season}-07-31"
        
    if league_slug == "uefa.euro":
        if season == 2024:
            return "2024-06-12", "2024-07-18"
        return f"{season}-06-01", f"{season}-07-31"

    # Ligas europeias normais (agosto de um ano a maio do ano seguinte)
    is_euro = league_slug in [
        "eng.1", "esp.1", "ita.1", "ger.1", "fra.1", 
        "uefa.champions", "uefa.europa"
    ]
    
    if is_euro:
        return f"{season}-08-01", f"{season+1}-06-10"
        
    # Ligas sul-americanas (março/abril a dezembro do mesmo ano)
    if league_slug == "bra.1" and season == 2026:
        # Calendário especial de 2026
        return "2026-01-26", "2026-12-10"
    return f"{season}-03-01", f"{season}-12-18"


def backfill_league_season(league_id: int, season: int):
    """Executa a coleta de uma liga e temporada e insere/atualiza no Supabase."""
    league_slug = LEAGUE_MAPPING.get(league_id)
    if not league_slug:
        print(f"⚠️ Liga ID {league_id} não possui mapeamento ESPN. Pulando.")
        return

    print(f"\n" + "="*80)
    print(f" ⚽ LIGA: {league_slug} (ID: {league_id}) | TEMPORADA: {season}")
    print(f"="*80)

    start_str, end_str = get_season_date_range(league_slug, season)
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    end   = datetime.strptime(end_str,   "%Y-%m-%d").date()
    
    print(f"   Período de busca: {start_str} até {end_str}")

    # Coletamos todas as datas possíveis (passo de 1 dia para buscar 100% dos jogos da liga)
    dates_to_check = []
    current = start
    while current <= end:
        dates_to_check.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    print(f"   Dias de busca planejados: {len(dates_to_check)}")

    total_games_saved = 0
    days_with_games = 0
    batch_records = []

    for i, day in enumerate(dates_to_check):
        events = fetch_scoreboard_day(league_slug, day)
        
        if not events:
            time.sleep(DELAY_BETWEEN_DAYS)
            continue
            
        # Filtra apenas eventos que pertencem a este ano ou temporada
        season_events = []
        for event in events:
            event_date = event.get("date", "")
            if event_date.startswith(str(season)) or (
                # Para ligas europeias cruzadas, aceitamos também o ano seguinte
                league_slug in ["eng.1", "esp.1", "ita.1", "ger.1", "fra.1", "uefa.champions", "uefa.europa"]
                and event_date.startswith(str(season + 1))
            ):
                season_events.append(event)

        if not season_events:
            time.sleep(DELAY_BETWEEN_DAYS)
            continue

        days_with_games += 1
        print(f"   [{i+1:3}/{len(dates_to_check)}] {day}: Processando {len(season_events)} jogo(s)...")

        for event in season_events:
            event_id = event.get("id")
            competitions = event.get("competitions", [{}])
            comp = competitions[0] if competitions else {}
            status_info = comp.get("status", {})
            completed = status_info.get("type", {}).get("completed", False)

            summary_data = None
            # Só faz sentido buscar detalhes de estatísticas (cartões/escanteios) de partidas finalizadas
            if completed and event_id:
                summary_data = fetch_game_summary(league_slug, event_id)
                time.sleep(DELAY_SUMMARY)

            parsed = parse_espn_event(event, summary_data)
            if parsed:
                # Enriquecer com IDs da nossa base de dados
                parsed["league_id"] = league_id
                parsed["league_name"] = LEAGUE_DISPLAY_NAMES.get(league_id, league_slug)
                parsed["is_backfilled"] = True
                batch_records.append(parsed)

        # Upsert a cada 20 registros para não estourar payload
        if len(batch_records) >= 20:
            save_to_supabase(batch_records)
            total_games_saved += len(batch_records)
            batch_records = []

        time.sleep(DELAY_BETWEEN_DAYS)

    # Gravar registros restantes
    if batch_records:
        save_to_supabase(batch_records)
        total_games_saved += len(batch_records)

    print(f"   ✅ Concluído! Dias com jogos: {days_with_games} | Total de partidas gravadas: {total_games_saved}")


def save_to_supabase(records: list[dict]):
    """Envia uma lista de partidas para o Supabase usando upsert."""
    if not supabase_client:
        print("   ⚠️  Supabase client não inicializado. Registros não foram salvos.")
        return
        
    try:
        # O supabase python client faz upsert nativo baseado na Primary Key (fixture_id)
        supabase_client.table("matches").upsert(records).execute()
    except Exception as e:
        print(f"   ❌ Erro ao enviar lote para o Supabase: {e}")


def main():
    if not supabase_client:
        print("ERRO: O Supabase Client não pôde ser carregado. Verifique seu .env.local.")
        sys.exit(1)

    print("\n" + "="*80)
    print(" 🚀 INICIANDO BACKFILL DE DADOS HISTÓRICOS FUTEBOL IA -> SUPABASE")
    print("="*80)
    print(f" Ligas configuradas: {len(LEAGUES_TO_PROCESS)}")
    print(f" Temporadas: {SEASONS}")

    start_time = time.time()

    # Iremos processar Brasileirão e Premier League primeiro como teste, ou todas direto
    for league_id in LEAGUES_TO_PROCESS:
        for season in SEASONS:
            # Não fazemos anos futuros que ainda não iniciaram
            if season > datetime.now().year + 1:
                continue
            backfill_league_season(league_id, season)

    duration = time.time() - start_time
    print("\n" + "="*80)
    print(f" 🎉 BACKFILL COMPLETADO COM SUCESSO EM {duration/60:.1f} MINUTOS!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
