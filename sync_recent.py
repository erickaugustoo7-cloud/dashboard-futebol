# -*- coding: utf-8 -*-
import sys
import io
import time
from datetime import datetime, timedelta
import subprocess

# Forçar UTF-8 no terminal do Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from supabase_client import supabase_client
from espn_client import (
    LEAGUE_MAPPING,
    fetch_scoreboard_day,
    fetch_game_summary,
    parse_espn_event
)

LEAGUES_TO_PROCESS = [71, 39, 140, 135, 78, 61, 2, 3, 13, 11, 73, 1, 9, 4]
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

DELAY_BETWEEN_DAYS = 0.3
DELAY_SUMMARY = 0.2

def save_to_supabase(records: list[dict]):
    if not supabase_client:
        return
    try:
        supabase_client.table("matches").upsert(records).execute()
    except Exception as e:
        print(f"❌ Erro Supabase: {e}")

def sync_recent():
    print("=====================================================")
    print(" 🚀 INICIANDO SYNC DE JOGOS RECENTES")
    print("=====================================================")
    
    # Busca de 3 dias atrás até 7 dias no futuro
    today = datetime.now()
    dates_to_check = [(today + timedelta(days=d)).strftime("%Y-%m-%d") for d in range(-3, 8)]
    print(f"Dias de busca: {dates_to_check[0]} até {dates_to_check[-1]}")

    total_saved = 0
    
    for league_id in LEAGUES_TO_PROCESS:
        league_slug = LEAGUE_MAPPING.get(league_id)
        if not league_slug: continue
        
        batch_records = []
        for day in dates_to_check:
            events = fetch_scoreboard_day(league_slug, day)
            if not events:
                time.sleep(DELAY_BETWEEN_DAYS)
                continue
                
            for event in events:
                event_id = event.get("id")
                competitions = event.get("competitions", [{}])
                comp = competitions[0] if competitions else {}
                status_info = comp.get("status", {})
                completed = status_info.get("type", {}).get("completed", False)
                
                summary_data = None
                if completed and event_id:
                    summary_data = fetch_game_summary(league_slug, event_id)
                    time.sleep(DELAY_SUMMARY)
                    
                parsed = parse_espn_event(event, summary_data)
                if parsed:
                    parsed["league_id"] = league_id
                    parsed["league_name"] = LEAGUE_DISPLAY_NAMES.get(league_id, league_slug)
                    parsed["is_backfilled"] = False
                    batch_records.append(parsed)
                    
            time.sleep(DELAY_BETWEEN_DAYS)
            
        if batch_records:
            save_to_supabase(batch_records)
            total_saved += len(batch_records)
            print(f"✅ {league_slug}: {len(batch_records)} jogos atualizados.")

    print(f"🎉 SYNC DE PARTIDAS CONCLUÍDO! Total atualizado: {total_saved}")
    
    # Em seguida, rodamos o recalculo de ELO para o modelo aprender com os novos placares
    print("\n=====================================================")
    print(" 🧠 INICIANDO APRENDIZADO DO MODELO (Recálculo de ELO)")
    print("=====================================================")
    try:
        subprocess.run(["python", "scripts/compute_team_stats.py"], check=True)
        print("✅ Aprendizado concluído com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao rodar o script de cálculo de stats: {e}")

if __name__ == "__main__":
    sync_recent()
