-- ============================================================
--  FOOTBALL MONITOR — AUDITORIA AUTOMATIZADA
--  Execute este SQL UMA VEZ no Supabase SQL Editor
-- ============================================================
-- Adiciona colunas de auditoria à tabela 'predictions' existente.
-- Usa ADD COLUMN IF NOT EXISTS para ser idempotente (seguro rodar mais de uma vez).

ALTER TABLE predictions
  -- Mercado apostado (ex: 'home_win', 'away_win', 'draw', 'over_25', 'btts_yes')
  ADD COLUMN IF NOT EXISTS suggested_bet    TEXT,

  -- Odd justa calculada pelo modelo (100 / prob%)
  ADD COLUMN IF NOT EXISTS fair_odd         NUMERIC,

  -- Odd do bookmaker no momento da previsão
  -- Por padrão, preenchida com fair_odd (sem integração externa de odds)
  ADD COLUMN IF NOT EXISTS bookmaker_odd    NUMERIC,

  -- Resultado real da partida (preenchido pelo resolve_predictions.py)
  -- Valores possíveis: 'home_win', 'draw', 'away_win', 'over_25', 'btts_yes', etc.
  ADD COLUMN IF NOT EXISTS actual_result    TEXT,

  -- Flag de controle: TRUE após o motor de resolução processar o jogo
  ADD COLUMN IF NOT EXISTS bet_resolved     BOOLEAN DEFAULT FALSE,

  -- Resultado financeiro em unidades de stake
  --   Green: (bookmaker_odd - 1) * stake
  --   Red:   -1 * stake
  ADD COLUMN IF NOT EXISTS profit_loss      NUMERIC,

  -- Stake unitária usada no cálculo (padrão: 1.0)
  ADD COLUMN IF NOT EXISTS stake            NUMERIC DEFAULT 1.0,

  -- Timestamp de quando a aposta foi resolvida
  ADD COLUMN IF NOT EXISTS resolved_at      TIMESTAMPTZ;

-- Índice para acelerar queries do motor de resolução
CREATE INDEX IF NOT EXISTS idx_predictions_resolved
  ON predictions(bet_resolved, actual_result);

-- Índice para acelerar o dashboard de PNL (ordenação por data de resolução)
CREATE INDEX IF NOT EXISTS idx_predictions_resolved_at
  ON predictions(resolved_at DESC)
  WHERE bet_resolved = TRUE;

-- ============================================================
--  VIEW DE AUDITORIA — para o Sanity Dashboard
--  Retorna predições resolvidas com dados do jogo para análise
-- ============================================================
CREATE OR REPLACE VIEW v_audit_predictions AS
SELECT
  p.id,
  p.fixture_id,
  m.league_name,
  m.home_team_name,
  m.away_team_name,
  m.date          AS match_date,
  m.goals_home,
  m.goals_away,

  -- Previsão congelada no momento zero
  p.home_win_prob,
  p.draw_prob,
  p.away_win_prob,
  p.over25_prob,
  p.btts_prob,
  p.confidence_score,
  p.confidence_level,
  p.suggested_bet,
  p.fair_odd,
  p.bookmaker_odd,
  p.stake,

  -- Resultado da resolução
  p.actual_result,
  p.profit_loss,
  p.bet_resolved,
  p.resolved_at,

  -- Faixa de confiança para a Matriz de Calibração
  CASE
    WHEN p.confidence_score >= 90 THEN '90-100'
    WHEN p.confidence_score >= 80 THEN '80-90'
    WHEN p.confidence_score >= 70 THEN '70-80'
    WHEN p.confidence_score >= 60 THEN '60-70'
    ELSE '<60'
  END AS confidence_band,

  -- Flag de acerto (Green = TRUE)
  CASE WHEN p.profit_loss > 0 THEN TRUE ELSE FALSE END AS is_win,

  p.created_at    AS predicted_at,
  p.model_version

FROM predictions p
JOIN matches m ON m.fixture_id = p.fixture_id
WHERE p.suggested_bet IS NOT NULL
ORDER BY p.resolved_at DESC NULLS LAST;
