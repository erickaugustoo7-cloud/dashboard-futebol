-- ============================================================
--  FOOTBALL MONITOR — SUPABASE SCHEMA COMPLETO
--  Execute este SQL no SQL Editor do Supabase Dashboard
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- TABELA PRINCIPAL: matches (se ainda não existir)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS matches (
  fixture_id          BIGINT PRIMARY KEY,
  league_id           INTEGER,
  league_name         TEXT,
  season              INTEGER,
  date                TIMESTAMPTZ,
  timestamp           BIGINT,
  status              TEXT DEFAULT 'NS',

  home_team_id        INTEGER,
  home_team_name      TEXT,
  away_team_id        INTEGER,
  away_team_name      TEXT,

  goals_home          INTEGER,
  goals_away          INTEGER,
  score_ht_home       INTEGER,
  score_ht_away       INTEGER,
  score_ft_home       INTEGER,
  score_ft_away       INTEGER,

  -- Estatísticas da partida
  home_shots          NUMERIC,
  away_shots          NUMERIC,
  home_sog            NUMERIC,
  away_sog            NUMERIC,
  home_possession     NUMERIC,
  away_possession     NUMERIC,
  home_corners        NUMERIC,
  away_corners        NUMERIC,
  home_yellow_cards   NUMERIC,
  away_yellow_cards   NUMERIC,
  home_red_cards      NUMERIC,
  away_red_cards      NUMERIC,
  home_fouls          NUMERIC,
  away_fouls          NUMERIC,
  home_offsides       NUMERIC,
  away_offsides       NUMERIC,

  is_backfilled       BOOLEAN DEFAULT FALSE,
  updated_at          TIMESTAMPTZ DEFAULT NOW(),
  last_synced_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_matches_league_season  ON matches(league_id, season);
CREATE INDEX IF NOT EXISTS idx_matches_date           ON matches(date DESC);
CREATE INDEX IF NOT EXISTS idx_matches_home_team      ON matches(home_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_away_team      ON matches(away_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_status         ON matches(status);

-- ──────────────────────────────────────────────────────────────
-- TABELA: team_stats_cache
-- Cache de estatísticas calculadas por time, liga e temporada
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS team_stats_cache (
  id                      BIGSERIAL PRIMARY KEY,
  team_id                 INTEGER NOT NULL,
  team_name               TEXT,
  league_id               INTEGER NOT NULL,
  season                  INTEGER NOT NULL,

  -- Médias gerais (todos os jogos)
  total_matches           INTEGER DEFAULT 0,
  avg_goals_scored        NUMERIC DEFAULT 0,
  avg_goals_conceded      NUMERIC DEFAULT 0,
  avg_shots               NUMERIC DEFAULT 0,
  avg_sog                 NUMERIC DEFAULT 0,
  avg_corners             NUMERIC DEFAULT 0,
  avg_yellow_cards        NUMERIC DEFAULT 0,
  avg_red_cards           NUMERIC DEFAULT 0,
  btts_pct                NUMERIC DEFAULT 0,
  over15_pct              NUMERIC DEFAULT 0,
  over25_pct              NUMERIC DEFAULT 0,
  over35_pct              NUMERIC DEFAULT 0,

  -- Como MANDANTE
  home_matches            INTEGER DEFAULT 0,
  avg_goals_scored_home   NUMERIC DEFAULT 0,
  avg_goals_conceded_home NUMERIC DEFAULT 0,
  avg_shots_home          NUMERIC DEFAULT 0,
  avg_corners_home        NUMERIC DEFAULT 0,
  btts_pct_home           NUMERIC DEFAULT 0,
  over25_pct_home         NUMERIC DEFAULT 0,
  home_win_pct            NUMERIC DEFAULT 0,

  -- Como VISITANTE
  away_matches            INTEGER DEFAULT 0,
  avg_goals_scored_away   NUMERIC DEFAULT 0,
  avg_goals_conceded_away NUMERIC DEFAULT 0,
  avg_shots_away          NUMERIC DEFAULT 0,
  avg_corners_away        NUMERIC DEFAULT 0,
  btts_pct_away           NUMERIC DEFAULT 0,
  over25_pct_away         NUMERIC DEFAULT 0,
  away_win_pct            NUMERIC DEFAULT 0,

  -- Forças relativas (base Poisson)
  attack_strength_home    NUMERIC DEFAULT 1.0,
  defense_strength_home   NUMERIC DEFAULT 1.0,
  attack_strength_away    NUMERIC DEFAULT 1.0,
  defense_strength_away   NUMERIC DEFAULT 1.0,

  -- ELO Rating dinâmico
  elo_rating              NUMERIC DEFAULT 1500,

  -- Forma recente (JSON com últimas N partidas)
  form_last5              JSONB,
  form_last10             JSONB,

  -- Fadiga / disponibilidade
  last_match_date         DATE,
  days_since_last_match   INTEGER,
  matches_last_14_days    INTEGER DEFAULT 0,
  fatigue_score           NUMERIC DEFAULT 0,  -- 0=descansado, 10=esgotado

  updated_at              TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(team_id, league_id, season)
);

CREATE INDEX IF NOT EXISTS idx_team_stats_team     ON team_stats_cache(team_id);
CREATE INDEX IF NOT EXISTS idx_team_stats_league   ON team_stats_cache(league_id, season);

-- ──────────────────────────────────────────────────────────────
-- TABELA: league_stats_cache
-- Cache de médias globais por liga + temporada
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS league_stats_cache (
  id                  BIGSERIAL PRIMARY KEY,
  league_id           INTEGER NOT NULL,
  season              INTEGER NOT NULL,
  total_matches       INTEGER DEFAULT 0,

  avg_home_goals      NUMERIC DEFAULT 0,
  avg_away_goals      NUMERIC DEFAULT 0,
  avg_total_goals     NUMERIC DEFAULT 0,

  home_win_pct        NUMERIC DEFAULT 0,
  draw_pct            NUMERIC DEFAULT 0,
  away_win_pct        NUMERIC DEFAULT 0,

  btts_pct            NUMERIC DEFAULT 0,
  over15_pct          NUMERIC DEFAULT 0,
  over25_pct          NUMERIC DEFAULT 0,
  over35_pct          NUMERIC DEFAULT 0,

  avg_corners_home    NUMERIC DEFAULT 0,
  avg_corners_away    NUMERIC DEFAULT 0,
  avg_corners_total   NUMERIC DEFAULT 0,

  avg_yellow_cards    NUMERIC DEFAULT 0,
  avg_red_cards       NUMERIC DEFAULT 0,

  updated_at          TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(league_id, season)
);

-- ──────────────────────────────────────────────────────────────
-- TABELA: predictions
-- Predições geradas pelo motor de análise para cada partida
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predictions (
  id                    BIGSERIAL PRIMARY KEY,
  fixture_id            BIGINT REFERENCES matches(fixture_id),
  
  -- Probabilidades 1X2
  home_win_prob         NUMERIC,
  draw_prob             NUMERIC,
  away_win_prob         NUMERIC,
  home_xg               NUMERIC,
  away_xg               NUMERIC,

  -- Mercados especiais
  btts_prob             NUMERIC,
  over15_prob           NUMERIC,
  over25_prob           NUMERIC,
  over35_prob           NUMERIC,
  corners_over85_prob   NUMERIC,
  corners_over105_prob  NUMERIC,

  -- Placar mais provável
  most_likely_score     TEXT,
  score_prob            NUMERIC,

  -- Score de confiança composto
  confidence_score      NUMERIC,   -- 0 a 100
  confidence_level      TEXT,      -- 'high', 'medium', 'low'

  -- Sugestão principal
  main_suggestion       TEXT,      -- ex: 'over_25', 'btts', 'home_win'
  main_suggestion_label TEXT,      -- ex: 'Over 2.5 Gols'
  main_suggestion_prob  NUMERIC,

  -- Dados usados no cálculo (para auditoria/backtesting)
  poisson_weight        NUMERIC DEFAULT 0.40,
  form_weight           NUMERIC DEFAULT 0.30,
  h2h_weight            NUMERIC DEFAULT 0.20,
  league_weight         NUMERIC DEFAULT 0.10,
  model_version         TEXT DEFAULT 'v1.0',

  created_at            TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(fixture_id, model_version)
);

CREATE INDEX IF NOT EXISTS idx_predictions_fixture    ON predictions(fixture_id);
CREATE INDEX IF NOT EXISTS idx_predictions_confidence ON predictions(confidence_score DESC);

-- ──────────────────────────────────────────────────────────────
-- VIEW: v_upcoming_with_predictions
-- Partidas futuras com predições já calculadas (para dashboard)
-- ──────────────────────────────────────────────────────────────
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
  p.over25_prob,
  p.most_likely_score,
  p.confidence_score,
  p.confidence_level,
  p.main_suggestion,
  p.main_suggestion_label,
  p.main_suggestion_prob
FROM matches m
LEFT JOIN predictions p ON p.fixture_id = m.fixture_id
WHERE m.status = 'NS'
  AND m.date >= NOW()
  AND m.date <= NOW() + INTERVAL '7 days'
ORDER BY p.confidence_score DESC NULLS LAST, m.date ASC;

-- ──────────────────────────────────────────────────────────────
-- VIEW: v_team_h2h
-- Head-to-head entre dois times (usada pelo motor de análise)
-- Exemplo de uso: WHERE (home_team_id=X AND away_team_id=Y) OR (home_team_id=Y AND away_team_id=X)
-- ──────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_team_h2h AS
SELECT
  fixture_id,
  league_id,
  date,
  home_team_id,
  home_team_name,
  away_team_id,
  away_team_name,
  goals_home,
  goals_away,
  CASE
    WHEN goals_home > goals_away THEN 'home'
    WHEN goals_home < goals_away THEN 'away'
    ELSE 'draw'
  END AS result,
  (goals_home + goals_away) AS total_goals,
  CASE WHEN goals_home > 0 AND goals_away > 0 THEN TRUE ELSE FALSE END AS btts,
  CASE WHEN (goals_home + goals_away) > 2.5 THEN TRUE ELSE FALSE END AS over25
FROM matches
WHERE status = 'FT'
  AND goals_home IS NOT NULL
  AND goals_away IS NOT NULL;
