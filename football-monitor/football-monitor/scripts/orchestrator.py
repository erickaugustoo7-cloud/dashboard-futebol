# -*- coding: utf-8 -*-
"""
=============================================================
  PIPELINE ORCHESTRATOR — Football Monitor
=============================================================
Orquestrador do pipeline completo de auditoria automática.

Ordem de execução:
  1. sync_recent.py        — Atualiza placares e dados da ESPN
  2. compute_team_stats.py — Recalcula ELO / forças de ataque/defesa
  3. resolve_predictions   — Resolve predições pendentes (P&L)
  4. generate_predictions  — Gera novas predições para os próximos dias

O modo é definido pelo argumento:
  --mode morning   → Passos 1 + 2 + 3 + 4 (pipeline completo)
  --mode resolve   → Apenas passo 3 (resolver pendentes rápido)
  --mode predict   → Apenas passo 4 (só gerar predições)

Logs são escritos em: logs/pipeline_YYYY-MM-DD.log

Como rodar manualmente:
  python scripts/orchestrator.py --mode morning
  python scripts/orchestrator.py --mode resolve
=============================================================
"""

import sys
import io
import os
import argparse
import subprocess
import logging
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ──────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ──────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).resolve().parent.parent
SCRIPTS_DIR  = BASE_DIR / "scripts"
LOGS_DIR     = BASE_DIR / "logs"
PYTHON_EXE   = sys.executable   # usa o mesmo python que está rodando este script

LOGS_DIR.mkdir(exist_ok=True)


# ──────────────────────────────────────────────────────────────
# LOGGING: console + arquivo
# ──────────────────────────────────────────────────────────────
def setup_logger(mode: str) -> logging.Logger:
    today    = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"pipeline_{today}.log"

    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Arquivo (append — acumula todas as execuções do dia)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


# ──────────────────────────────────────────────────────────────
# EXECUTOR DE SCRIPTS
# ──────────────────────────────────────────────────────────────
def run_step(logger: logging.Logger, name: str, script: str, args: list[str] = None) -> bool:
    """
    Executa um script Python como subprocesso.
    Retorna True se sucesso, False se falhou.
    """
    cmd = [PYTHON_EXE, str(SCRIPTS_DIR / script)] + (args or [])
    logger.info(f"{'='*60}")
    logger.info(f"▶  INICIANDO: {name}")
    logger.info(f"   Comando: {' '.join(cmd)}")
    logger.info(f"{'='*60}")

    start = datetime.now()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        elapsed = (datetime.now() - start).seconds

        # Exibe stdout linha a linha para o log
        for line in result.stdout.splitlines():
            if line.strip():
                logger.info(f"   {line}")

        if result.returncode != 0:
            logger.error(f"✗  {name} FALHOU (exit={result.returncode}, {elapsed}s)")
            for line in result.stderr.splitlines():
                if line.strip():
                    logger.error(f"   STDERR: {line}")
            return False

        logger.info(f"✓  {name} concluído em {elapsed}s")
        return True

    except Exception as e:
        logger.error(f"✗  {name} — exceção: {e}")
        return False


# ──────────────────────────────────────────────────────────────
# MODOS DO PIPELINE
# ──────────────────────────────────────────────────────────────
def run_morning_pipeline(logger: logging.Logger, days: int, no_ai: bool) -> None:
    """
    Pipeline completo diário (ideal para rodar às 08:00):
      1. Sincroniza placares recentes (ESPN)
      2. Recalcula ELO / estatísticas de times
      3. Resolve predições pendentes
      4. Gera novas predições
    """
    logger.info("MODO: MORNING PIPELINE (pipeline completo)")
    results = {}

    # Passo 1: Sync de partidas
    results["sync"] = run_step(logger, "Sync de Partidas (ESPN)", "sync_recent.py")

    # Passo 2: Recálculo de stats — só roda se o sync teve sucesso
    if results["sync"]:
        results["stats"] = run_step(logger, "Recálculo de ELO/Stats", "compute_team_stats.py")
    else:
        logger.warning("⚠  Sync falhou — pulando recálculo de stats.")
        results["stats"] = False

    # Passo 3: Resolve pendentes (independente do sync)
    results["resolve"] = run_step(
        logger,
        "Resolução de Predições P&L",
        "resolve_predictions.py",
        ["--hours", "36"]   # janela de 36h para cobrir jogos de ontem
    )

    # Passo 4: Gera novas predições
    predict_args = ["--days", str(days)]
    if no_ai:
        predict_args.append("--no-ai")
    results["predict"] = run_step(logger, "Geração de Predições", "generate_predictions.py", predict_args)

    _print_summary(logger, results)


def run_resolve_only(logger: logging.Logger) -> None:
    """
    Apenas resolve predições pendentes — ideal para rodar às 02:00.
    """
    logger.info("MODO: RESOLVE ONLY")
    ok = run_step(
        logger,
        "Resolução de Predições P&L",
        "resolve_predictions.py",
        ["--hours", "48"]
    )
    _print_summary(logger, {"resolve": ok})


def run_predict_only(logger: logging.Logger, days: int, no_ai: bool) -> None:
    """
    Apenas gera predições — ideal para re-executar em caso de falha.
    """
    logger.info("MODO: PREDICT ONLY")
    predict_args = ["--days", str(days)]
    if no_ai:
        predict_args.append("--no-ai")
    ok = run_step(logger, "Geração de Predições", "generate_predictions.py", predict_args)
    _print_summary(logger, {"predict": ok})


# ──────────────────────────────────────────────────────────────
# RESUMO FINAL
# ──────────────────────────────────────────────────────────────
def _print_summary(logger: logging.Logger, results: dict) -> None:
    logger.info("=" * 60)
    logger.info("  RESUMO DO PIPELINE")
    logger.info("=" * 60)
    all_ok = True
    for step, ok in results.items():
        icon = "✓" if ok else "✗"
        logger.info(f"  {icon}  {step:<20} {'OK' if ok else 'FALHOU'}")
        if not ok:
            all_ok = False

    if all_ok:
        logger.info("  → Pipeline finalizado COM SUCESSO ✅")
    else:
        logger.info("  → Pipeline finalizado COM FALHAS ⚠  (verifique o log acima)")
    logger.info("=" * 60)


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Orquestrador do pipeline Football Monitor.")
    parser.add_argument(
        "--mode", choices=["morning", "resolve", "predict"],
        default="morning",
        help="morning=pipeline completo | resolve=só resolver | predict=só gerar predições"
    )
    parser.add_argument("--days",   type=int, default=3,  help="Dias à frente para predições (padrão: 3)")
    parser.add_argument("--no-ai",  action="store_true",  help="Desativa insights IA (mais rápido)")
    args = parser.parse_args()

    logger = setup_logger(args.mode)
    logger.info(f"Pipeline iniciado — modo={args.mode} | python={PYTHON_EXE}")
    logger.info(f"Diretório base: {BASE_DIR}")

    if args.mode == "morning":
        run_morning_pipeline(logger, args.days, args.no_ai)
    elif args.mode == "resolve":
        run_resolve_only(logger)
    elif args.mode == "predict":
        run_predict_only(logger, args.days, args.no_ai)


if __name__ == "__main__":
    main()
