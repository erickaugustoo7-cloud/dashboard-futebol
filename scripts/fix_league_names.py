# -*- coding: utf-8 -*-
"""
=============================================================
  FIX LEAGUE NAMES — Patch nos registros existentes no Supabase
=============================================================
Atualiza o campo league_id e league_name para todos os registros
existentes no banco, que foram gravados com nomes incorretos
(ex: GROUP-STAGE, LEAGUE-PHASE).

Como rodar:
  python scripts/fix_league_names.py
=============================================================
"""

import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from supabase_client import supabase_client as sb

# Mapeamento de league_id para nome legível
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

def fix_league_names():
    print("\n" + "="*70)
    print(" 🔧 CORRIGINDO LEAGUE_NAMES NO BANCO DE DADOS")
    print("="*70)

    total_fixed = 0
    for league_id, league_name in LEAGUE_DISPLAY_NAMES.items():
        print(f"\n  Atualizando liga {league_id}: {league_name}...")
        try:
            # Busca todos os fixture_ids desta liga (que podem ter nome errado)
            offset = 0
            page_size = 1000
            batch_ids = []
            while True:
                res = sb.table("matches")\
                    .select("fixture_id")\
                    .eq("league_id", league_id)\
                    .range(offset, offset + page_size - 1)\
                    .execute()
                rows = res.data or []
                batch_ids.extend([r["fixture_id"] for r in rows])
                if len(rows) < page_size:
                    break
                offset += page_size

            if not batch_ids:
                print(f"     -> Nenhum registro encontrado. Pulando.")
                continue

            # Atualiza em lotes de 500
            updated = 0
            for i in range(0, len(batch_ids), 500):
                chunk = batch_ids[i:i+500]
                sb.table("matches")\
                    .update({"league_name": league_name})\
                    .in_("fixture_id", chunk)\
                    .execute()
                updated += len(chunk)
                time.sleep(0.2)

            print(f"     -> ✅ {updated} registros atualizados.")
            total_fixed += updated

        except Exception as e:
            print(f"     -> ❌ Erro: {e}")

    print(f"\n{'='*70}")
    print(f" ✅ PATCH CONCLUÍDO! {total_fixed} registros corrigidos no total.")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    fix_league_names()
