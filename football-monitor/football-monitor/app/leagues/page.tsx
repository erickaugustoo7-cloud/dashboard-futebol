'use client';

import { useState, useEffect } from 'react';

const LEAGUE_INFO: Record<number, { name: string; flag: string; country: string }> = {
  71:  { name: 'Brasileirão Série A',  flag: '🇧🇷', country: 'Brasil'    },
  39:  { name: 'Premier League',       flag: '🏴󠁧󠁢󠁥󠁮󠁧󠁿', country: 'Inglaterra' },
  140: { name: 'La Liga',              flag: '🇪🇸', country: 'Espanha'   },
  135: { name: 'Serie A',              flag: '🇮🇹', country: 'Itália'    },
  78:  { name: 'Bundesliga',           flag: '🇩🇪', country: 'Alemanha'  },
  61:  { name: 'Ligue 1',             flag: '🇫🇷', country: 'França'    },
  2:   { name: 'UEFA Champions',       flag: '🏆', country: 'Europa'    },
  3:   { name: 'UEFA Europa',          flag: '🌍', country: 'Europa'    },
  13:  { name: 'Libertadores',         flag: '🌎', country: 'América do Sul' },
  11:  { name: 'Sudamericana',         flag: '🌎', country: 'América do Sul' },
  73:  { name: 'Copa do Brasil',       flag: '🇧🇷', country: 'Brasil'    },
  1:   { name: 'Copa do Mundo',        flag: '🌍', country: 'Mundial'   },
  9:   { name: 'Copa América',         flag: '🌎', country: 'América'   },
  4:   { name: 'Eurocopa',             flag: '🇪🇺', country: 'Europa'    },
};

function StatBar({ label, value, color = 'var(--accent)' }: { label: string; value: number; color?: string }) {
  return (
    <div style={{ marginBottom: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</span>
        <span style={{ fontSize: '12px', fontWeight: 700, fontFamily: 'var(--font-mono)', color }}>{value.toFixed(1)}%</span>
      </div>
      <div style={{ height: '4px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${Math.min(100, value)}%`, background: color, borderRadius: '2px', transition: 'width 0.6s ease' }} />
      </div>
    </div>
  );
}

export default function Leagues() {
  const [leagues, setLeagues] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [date, setDate]       = useState(() => new Date().toISOString().split('T')[0]);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError('');
      try {
        const res = await fetch(`/api/leagues?date=${date}`);
        const text = await res.text();
        let json;
        try { json = JSON.parse(text); } catch { throw new Error('Erro na resposta do servidor'); }
        if (!res.ok) throw new Error(json.error || 'Falha ao buscar dados');
        setLeagues(json);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [date]);

  const changeDate = (days: number) => {
    const d = new Date(date + 'T12:00:00');
    d.setDate(d.getDate() + days);
    setDate(d.toISOString().split('T')[0]);
  };

  const season = date.split('-')[0];

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Estatísticas por Liga</h1>
        <p className="page-subtitle">Métricas globais, tendências e base Poisson de cada campeonato</p>
      </div>

      <div className="date-selector">
        <button className="date-btn" onClick={() => changeDate(-1)}>← Ano Anterior</button>
        <input
          type="date"
          className="date-input"
          value={date}
          onChange={e => setDate(e.target.value)}
          title="A temporada será inferida a partir do ano selecionado"
        />
        <button className="date-btn" onClick={() => changeDate(1)}>Próximo Ano →</button>
        <button className="date-btn" onClick={() => setDate(new Date().toISOString().split('T')[0])}>Atual</button>
      </div>

      {loading ? (
        <div className="empty-state">
          <div className="spinner" style={{ margin: '0 auto 16px' }}></div>
          <p>Calculando tendências da temporada {season}...</p>
        </div>
      ) : error ? (
        <div className="empty-state">
          <div className="empty-icon">⚠️</div>
          <p style={{ color: 'var(--low)' }}>{error}</p>
        </div>
      ) : leagues.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🏆</div>
          <h3 className="empty-title">Sem dados para {season}</h3>
          <p className="empty-desc">
            Nenhuma estatística de liga calculada. Execute <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--bg-card)', padding: '1px 6px', borderRadius: '4px' }}>compute_team_stats.py</code> para gerar os dados.
          </p>
        </div>
      ) : (
        <>
          <div className="stats-bar" style={{ marginBottom: '28px' }}>
            <div className="stat-item">
              <div className="stat-label">Ligas com dados</div>
              <div className="stat-value">{leagues.length}</div>
            </div>
            <div className="stat-item">
              <div className="stat-label">Temporada</div>
              <div className="stat-value">{season}</div>
            </div>
            <div className="stat-item">
              <div className="stat-label">Total de partidas</div>
              <div className="stat-value">{leagues.reduce((s: number, l: any) => s + (l.total_matches || 0), 0).toLocaleString()}</div>
            </div>
            <div className="stat-item">
              <div className="stat-label">Média gols/jogo</div>
              <div className="stat-value" style={{ color: 'var(--accent-bright)' }}>
                {leagues.length > 0
                  ? (leagues.reduce((s: number, l: any) => s + (l.avg_total_goals || 0), 0) / leagues.length).toFixed(2)
                  : '—'}
              </div>
            </div>
          </div>

          <div className="combinadas-grid">
            {leagues.map((lg) => {
              const info = LEAGUE_INFO[lg.league_id];
              const totalGoals = (lg.avg_home_goals ?? 0) + (lg.avg_away_goals ?? 0);
              const homeWinBar = lg.home_win_pct ?? 0;
              const drawBar    = lg.draw_pct ?? 0;
              const awayWinBar = lg.away_win_pct ?? 0;

              return (
                <div key={lg.league_id} className="combinada-card" style={{ borderTop: '2px solid var(--accent-glow)' }}>
                  {/* Header */}
                  <div className="combinada-header">
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ fontSize: '24px' }}>{info?.flag ?? '🌍'}</span>
                        <div>
                          <div className="combinada-type" style={{ fontSize: '16px' }}>
                            {info?.name ?? `Liga ${lg.league_id}`}
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                            {info?.country ?? ''} · Temporada {lg.season} · {lg.total_matches?.toLocaleString() ?? 0} jogos
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="combinada-ev positive">
                      {(totalGoals).toFixed(2)} xG/jogo
                    </div>
                  </div>

                  {/* Goals bar */}
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ fontSize: '12px', color: 'var(--accent-bright)', fontWeight: 600 }}>
                        Casa {lg.avg_home_goals?.toFixed(2)}
                      </span>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>média de gols</span>
                      <span style={{ fontSize: '12px', color: '#a78bfa', fontWeight: 600 }}>
                        {lg.avg_away_goals?.toFixed(2)} Fora
                      </span>
                    </div>
                    <div className="xg-bar-container" style={{ height: '8px', borderRadius: '4px' }}>
                      <div className="xg-bar-home" style={{ width: `${totalGoals > 0 ? (lg.avg_home_goals / totalGoals) * 100 : 50}%`, borderRadius: '4px 0 0 4px' }} />
                      <div className="xg-bar-away" style={{ flex: 1, borderRadius: '0 4px 4px 0' }} />
                    </div>
                  </div>

                  {/* Results breakdown */}
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>Distribuição de Resultados</div>
                    <div className="prob-bars" style={{ height: '8px', borderRadius: '4px', marginBottom: '6px' }}>
                      <div className="prob-bar-home" style={{ width: `${homeWinBar}%` }} />
                      <div className="prob-bar-draw"  style={{ width: `${drawBar}%` }} />
                      <div className="prob-bar-away"  style={{ width: `${awayWinBar}%` }} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-secondary)' }}>
                      <div>
                        <span style={{ color: 'var(--accent-bright)', fontWeight: 700 }}>{homeWinBar.toFixed(1)}%</span>
                        <span style={{ color: 'var(--text-muted)' }}> Casa</span>
                      </div>
                      <div>
                        <span style={{ fontWeight: 700 }}>{drawBar.toFixed(1)}%</span>
                        <span style={{ color: 'var(--text-muted)' }}> Emp</span>
                      </div>
                      <div>
                        <span style={{ color: '#a78bfa', fontWeight: 700 }}>{awayWinBar.toFixed(1)}%</span>
                        <span style={{ color: 'var(--text-muted)' }}> Fora</span>
                      </div>
                    </div>
                  </div>

                  {/* Market stats */}
                  <StatBar label="Over 2.5 Gols"   value={lg.over25_pct ?? 0} color="var(--high)"    />
                  <StatBar label="Ambos Marcam"     value={lg.btts_pct ?? 0}   color="var(--medium)"  />
                  {lg.over35_pct != null && (
                    <StatBar label="Over 3.5 Gols" value={lg.over35_pct}       color="var(--accent)"  />
                  )}

                  {/* Footer stats */}
                  <div className="combinada-footer">
                    <div className="combinada-stat">
                      <div className="combinada-stat-val" style={{ fontSize: '15px' }}>{lg.avg_corners_total?.toFixed(1) ?? '—'}</div>
                      <div className="combinada-stat-label">Escanteios/jogo</div>
                    </div>
                    <div className="combinada-stat">
                      <div className="combinada-stat-val" style={{ fontSize: '15px' }}>{lg.avg_yellow_cards?.toFixed(1) ?? '—'}</div>
                      <div className="combinada-stat-label">Amarelos/jogo</div>
                    </div>
                    <div className="combinada-stat">
                      <div className="combinada-stat-val" style={{ fontSize: '15px', color: 'var(--accent-bright)' }}>{lg.over15_pct?.toFixed(1) ?? '—'}%</div>
                      <div className="combinada-stat-label">Over 1.5</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
