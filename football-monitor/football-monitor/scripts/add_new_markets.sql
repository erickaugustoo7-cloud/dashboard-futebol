-- ============================================================
--  FOOTBALL MONITOR — ADIÇÃO DE NOVOS MERCADOS
--  Execute este SQL no SQL Editor do Supabase Dashboard
-- ============================================================

-- Adiciona novas colunas na tabela predictions para cobrir os novos mercados
ALTER TABLE predictions 
ADD COLUMN IF NOT EXISTS prob_1x NUMERIC,
ADD COLUMN IF NOT EXISTS prob_12 NUMERIC,
ADD COLUMN IF NOT EXISTS prob_x2 NUMERIC,
ADD COLUMN IF NOT EXISTS prob_dnb_home NUMERIC,
ADD COLUMN IF NOT EXISTS prob_dnb_away NUMERIC,
ADD COLUMN IF NOT EXISTS prob_home_over05 NUMERIC,
ADD COLUMN IF NOT EXISTS prob_home_over15 NUMERIC,
ADD COLUMN IF NOT EXISTS prob_away_over05 NUMERIC,
ADD COLUMN IF NOT EXISTS prob_away_over15 NUMERIC,
ADD COLUMN IF NOT EXISTS prob_btts_or_over25 NUMERIC,
ADD COLUMN IF NOT EXISTS cards_over45_prob NUMERIC,
ADD COLUMN IF NOT EXISTS sog_over85_prob NUMERIC;

-- Atualizar a View v_upcoming_with_predictions para expor as novas probabilidades
DROP VIEW IF EXISTS v_upcoming_with_predictions;

CREATE OR REPLACE VIEW v_upcoming_with_predictions AS
SELECT
  m.fixture_id,
  m.league_id,
  m.league_name,
  m.season,
  m.date,
  m.status,
  m.home_team_id,
  m.home_team_name,
  m.away_team_id,
  m.away_team_name,
  p.home_win_prob,
  p.draw_prob,
  p.away_win_prob,
  p.home_xg,
  p.away_xg,
  p.btts_prob,
  p.over15_prob,
  p.over25_prob,
  p.over35_prob,
  p.most_likely_score,
  p.confidence_score,
  p.confidence_level,
  p.main_suggestion,
  p.main_suggestion_label,
  p.main_suggestion_prob,
  -- Novos Mercados Adicionados
  p.prob_1x,
  p.prob_12,
  p.prob_x2,
  p.prob_dnb_home,
  p.prob_dnb_away,
  p.prob_home_over05,
  p.prob_home_over15,
  p.prob_away_over05,
  p.prob_away_over15,
  p.prob_btts_or_over25,
  p.corners_over85_prob,
  p.corners_over105_prob,
  p.cards_over45_prob,
  p.sog_over85_prob
FROM matches m
LEFT JOIN predictions p ON p.fixture_id = m.fixture_id
WHERE m.status = 'NS'
  AND m.date >= NOW()
  AND m.date <= NOW() + INTERVAL '7 days'
ORDER BY p.confidence_score DESC NULLS LAST, m.date ASC;
