# -*- coding: utf-8 -*-
"""
=============================================================
  RESOLVE PREDICTIONS — Football Monitor
=============================================================
Motor de resolução de resultados: cruza jogos finalizados
com predições pendentes e calcula P&L (Profit & Loss).

Lógica de resolução por mercado:
  - home_win   : ganha se goals_home > goals_away
  - away_win   : ganha se goals_away > goals_home
  - draw       : ganha se goals_home == goals_away
  - over25     : ganha se (goals_home + goals_away) > 2.5
  - btts_yes   : ganha se goals_home > 0 AND goals_away > 0

Cálculo de P&L (por unidade de stake):
  - Green (acerto) : profit = (bookmaker_odd - 1) * stake
  - Red   (erro)   : profit = -1 * stake

Como rodar:
  python scripts/resolve_predictions.py
  python scripts/resolve_predictions.py --dry-run   # mostra sem salvar
  python scripts/resolve_predictions.py --hours 72  # janela de busca de jogos finalizados
=============================================================
"""

import sys
import io
import os
import argparse
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
from dotenv import load_dotenv

# ──────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ──────────────────────────────────────────────────────────────
BATCH_SIZE     = 50     # updates por lote no Supabase
DEFAULT_HOURS  = 48     # janela de busca de jogos finalizados

# Mercados suportados e suas funções de resolução
# Cada função recebe uma linha do DataFrame e retorna True se a aposta foi vencedora
MARKET_RESOLVERS = {
    "home_win":  lambda r: r["goals_home"] > r["goals_away"],
    "away_win":  lambda r: r["goals_away"] > r["goals_home"],
    "draw":      lambda r: r["goals_home"] == r["goals_away"],
    "over25":    lambda r: (r["goals_home"] + r["goals_away"]) > 2.5,
    "btts_yes":  lambda r: r["goals_home"] > 0 and r["goals_away"] > 0,
}


# ──────────────────────────────────────────────────────────────
# CLIENTE SUPABASE
# ──────────────────────────────────────────────────────────────
def init_supabase():
    """Inicializa o cliente Supabase a partir do .env.local."""
    try:
        base_dir = os.path.dirname(__file__)
    except NameError:
        base_dir = os.getcwd()

    env_path = os.path.join(base_dir, "..", ".env.local")
    load_dotenv(dotenv_path=env_path)

    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        print("ERRO: Credenciais do Supabase não encontradas no .env.local")
        sys.exit(1)

    from supabase import create_client
    return create_client(url, key)


# ──────────────────────────────────────────────────────────────
# FUNÇÕES DE BUSCA
# ──────────────────────────────────────────────────────────────
def fetch_finished_matches(supabase, hours: int) -> pd.DataFrame:
    """
    Busca jogos finalizados nas últimas N horas.
    Retorna apenas os campos necessários para a resolução.
    """
    print(f"[1/4] Buscando jogos finalizados nas últimas {hours}h...")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = supabase.table("matches") \
        .select("fixture_id,home_team_name,away_team_name,goals_home,goals_away,date") \
        .eq("status", "FT") \
        .gte("date", cutoff.isoformat()) \
        .not_.is_("goals_home", "null") \
        .not_.is_("goals_away", "null") \
        .execute()

    df = pd.DataFrame(result.data or [])
    if not df.empty:
        df["goals_home"] = pd.to_numeric(df["goals_home"], errors="coerce").fillna(0).astype(int)
        df["goals_away"] = pd.to_numeric(df["goals_away"], errors="coerce").fillna(0).astype(int)
    print(f"    -> {len(df)} jogos finalizados encontrados.")
    return df


def fetch_pending_predictions(supabase) -> pd.DataFrame:
    """
    Busca predições que ainda não foram resolvidas (bet_resolved IS FALSE
    ou NULL) e que possuem um mercado definido (suggested_bet IS NOT NULL).
    """
    print("[2/4] Buscando predições pendentes...")

    result = supabase.table("predictions") \
        .select("id,fixture_id,suggested_bet,bookmaker_odd,fair_odd,stake,confidence_score,confidence_level,model_version") \
        .eq("bet_resolved", False) \
        .not_.is_("suggested_bet", "null") \
        .execute()

    df = pd.DataFrame(result.data or [])
    if not df.empty:
        df["stake"]         = pd.to_numeric(df["stake"],         errors="coerce").fillna(1.0)
        df["bookmaker_odd"] = pd.to_numeric(df["bookmaker_odd"], errors="coerce")
        df["fair_odd"]      = pd.to_numeric(df["fair_odd"],      errors="coerce")
        # Fallback: se bookmaker_odd for nulo, usa fair_odd
        df["bookmaker_odd"] = df["bookmaker_odd"].combine_first(df["fair_odd"]).fillna(2.0)
    print(f"    -> {len(df)} predições pendentes encontradas.")
    return df


# ──────────────────────────────────────────────────────────────
# MOTOR DE RESOLUÇÃO (PANDAS PURO)
# ──────────────────────────────────────────────────────────────
def resolve_bet(row: pd.Series) -> dict:
    """
    Determina o resultado real e calcula o P&L para uma aposta.

    Retorna um dicionário com os campos a serem atualizados no banco.
    """
    market    = row["suggested_bet"]
    odd       = row["bookmaker_odd"]
    stake     = row["stake"]
    now_utc   = datetime.now(timezone.utc).isoformat()

    # Resultado real da partida (do ponto de vista do mercado)
    goals_home = int(row["goals_home"])
    goals_away = int(row["goals_away"])
    total      = goals_home + goals_away

    # Determina o resultado verdadeiro da partida para os mercados 1X2
    if goals_home > goals_away:
        real_1x2 = "home_win"
    elif goals_home < goals_away:
        real_1x2 = "away_win"
    else:
        real_1x2 = "draw"

    # Resultado real do ponto de vista do mercado apostado
    actual_result_map = {
        "home_win":  real_1x2,
        "away_win":  real_1x2,
        "draw":      real_1x2,
        "over25":    f"over25_{'yes' if total > 2.5 else 'no'}",
        "btts_yes":  f"btts_{'yes' if goals_home > 0 and goals_away > 0 else 'no'}",
    }
    actual_result = actual_result_map.get(market, real_1x2)

    # Resolve a aposta
    resolver = MARKET_RESOLVERS.get(market)
    if resolver is None:
        # Mercado desconhecido — marca como resolvido sem P&L
        return {
            "actual_result": f"unknown_market:{market}",
            "profit_loss":   0.0,
            "bet_resolved":  True,
            "resolved_at":   now_utc,
        }

    is_win = resolver(row)

    if is_win:
        profit_loss = round((odd - 1) * stake, 4)
        outcome     = "GREEN ✅"
    else:
        profit_loss = round(-1 * stake, 4)
        outcome     = "RED   ❌"

    return {
        "actual_result": actual_result,
        "profit_loss":   profit_loss,
        "bet_resolved":  True,
        "resolved_at":   now_utc,
        "_outcome":      outcome,   # apenas para log, não vai ao banco
    }


def merge_and_resolve(df_matches: pd.DataFrame, df_preds: pd.DataFrame) -> pd.DataFrame:
    """
    Cruza jogos finalizados com predições pendentes usando Pandas merge.
    Retorna DataFrame com todos os campos resolvidos prontos para o update.
    """
    print("[3/4] Cruzando dados (Pandas merge por fixture_id)...")

    if df_matches.empty or df_preds.empty:
        print("    -> Nada para cruzar.")
        return pd.DataFrame()

    # Merge: apenas predições cujo jogo já terminou aparecem aqui
    df_merged = pd.merge(
        df_preds,
        df_matches[["fixture_id", "home_team_name", "away_team_name",
                    "goals_home", "goals_away"]],
        on="fixture_id",
        how="inner"
    )

    print(f"    -> {len(df_merged)} predições com jogos finalizados para resolver.")

    if df_merged.empty:
        return pd.DataFrame()

    # Aplica a lógica de resolução linha a linha
    resolutions = df_merged.apply(resolve_bet, axis=1, result_type="expand")
    df_resolved = pd.concat([df_merged, resolutions], axis=1)

    return df_resolved


# ──────────────────────────────────────────────────────────────
# UPDATE EM LOTE NO SUPABASE
# ──────────────────────────────────────────────────────────────
def push_resolutions(supabase, df_resolved: pd.DataFrame, dry_run: bool) -> int:
    """
    Atualiza as predições resolvidas no Supabase em lotes.
    Retorna o número de registros atualizados.
    """
    if df_resolved.empty:
        return 0

    print(f"[4/4] {'[DRY-RUN] Simulando' if dry_run else 'Salvando'} {len(df_resolved)} resoluções...")

    updated = 0
    for i in range(0, len(df_resolved), BATCH_SIZE):
        batch_df = df_resolved.iloc[i:i + BATCH_SIZE]

        for _, row in batch_df.iterrows():
            payload = {
                "actual_result": row["actual_result"],
                "profit_loss":   row["profit_loss"],
                "bet_resolved":  True,
                "resolved_at":   row["resolved_at"],
            }

            match_str = f"{row.get('home_team_name','?')} vs {row.get('away_team_name','?')}"
            outcome   = row.get("_outcome", "")
            print(f"    {outcome}  {match_str:<40} | {row['suggested_bet']:<10} "
                  f"| P&L: {row['profit_loss']:+.2f}u | conf: {row.get('confidence_score',0):.0f}")

            if not dry_run:
                try:
                    supabase.table("predictions") \
                        .update(payload) \
                        .eq("id", int(row["id"])) \
                        .execute()
                    updated += 1
                except Exception as e:
                    print(f"        ERRO ao atualizar id={row['id']}: {e}")
            else:
                updated += 1

    return updated


# ──────────────────────────────────────────────────────────────
# RELATÓRIO RESUMIDO (Pandas)
# ──────────────────────────────────────────────────────────────
def print_summary(df_resolved: pd.DataFrame) -> None:
    """Exibe métricas gerais da sessão de resolução."""
    if df_resolved.empty:
        return

    total  = len(df_resolved)
    greens = (df_resolved["profit_loss"] > 0).sum()
    reds   = (df_resolved["profit_loss"] < 0).sum()
    pnl    = df_resolved["profit_loss"].sum()
    roi    = (pnl / total) * 100 if total > 0 else 0

    print("\n" + "=" * 60)
    print("  SESSÃO DE RESOLUÇÃO — RESUMO")
    print("=" * 60)
    print(f"  Total resolvido : {total}")
    print(f"  Greens (acertos): {greens} ({greens/total*100:.1f}%)")
    print(f"  Reds  (erros)   : {reds}  ({reds/total*100:.1f}%)")
    print(f"  P&L desta sessão: {pnl:+.2f} unidades")
    print(f"  ROI desta sessão: {roi:+.1f}%")

    # Por mercado
    if "suggested_bet" in df_resolved.columns:
        print("\n  Por mercado:")
        for market, grp in df_resolved.groupby("suggested_bet"):
            g = (grp["profit_loss"] > 0).sum()
            t = len(grp)
            print(f"    {market:<12} {g}/{t} acertos ({g/t*100:.0f}%) | P&L: {grp['profit_loss'].sum():+.2f}u")

    # Por nível de confiança
    if "confidence_level" in df_resolved.columns:
        print("\n  Por confiança:")
        for level, grp in df_resolved.groupby("confidence_level"):
            g = (grp["profit_loss"] > 0).sum()
            t = len(grp)
            print(f"    {level:<8} {g}/{t} acertos ({g/t*100:.0f}%) | P&L: {grp['profit_loss'].sum():+.2f}u")

    print("=" * 60 + "\n")


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Resolve predições pendentes cruzando com resultados reais."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Mostra as resoluções sem salvar no banco."
    )
    parser.add_argument(
        "--hours", type=int, default=DEFAULT_HOURS,
        help=f"Janela de busca de jogos finalizados em horas (padrão: {DEFAULT_HOURS}h)."
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  RESOLVE PREDICTIONS — Motor de Resolução P&L")
    if args.dry_run:
        print("  *** MODO DRY-RUN: nenhuma alteração será salva ***")
    print("=" * 60 + "\n")

    supabase = init_supabase()

    # 1. Busca jogos finalizados
    df_matches = fetch_finished_matches(supabase, args.hours)

    # 2. Busca predições pendentes
    df_preds = fetch_pending_predictions(supabase)

    if df_preds.empty:
        print("\n✅ Nenhuma predição pendente. Tudo já foi resolvido ou não há apostas para resolver.")
        return

    if df_matches.empty:
        print(f"\n⏳ Nenhum jogo finalizado nas últimas {args.hours}h com placar disponível.")
        print("   Tente rodar novamente após os jogos encerrarem, ou use --hours com valor maior.")
        return

    # 3. Cruzamento (Pandas merge) + resolução
    df_resolved = merge_and_resolve(df_matches, df_preds)

    if df_resolved.empty:
        print("\n⏳ Nenhuma predição cruzou com jogos finalizados nesta janela.")
        print("   Os jogos podem ainda não ter terminado.")
        return

    # 4. Exibe preview antes de salvar
    print_summary(df_resolved)

    # 5. Salva no Supabase (ou simula)
    updated = push_resolutions(supabase, df_resolved, dry_run=args.dry_run)

    if args.dry_run:
        print(f"\n[DRY-RUN] {updated} registros seriam atualizados. Nada foi salvo.")
    else:
        print(f"\n✅ {updated} predições resolvidas e salvas no Supabase.")


if __name__ == "__main__":
    main()
