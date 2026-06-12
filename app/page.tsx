'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';

const MARKET_ICONS: Record<string, string> = {
  over25:   '⚽',
  under25:  '🛡️',
  btts_yes: '🔥',
  btts_no:  '🧱',
  home_win: '🏠',
  away_win: '✈️',
  draw:     '🤝',
  '1x':     '🏠🤝',
  x2:       '🤝✈️',
  '12':     '🏠✈️',
};

function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.min(100, Math.max(0, value));
  const color = pct >= 65 ? 'var(--high)' : pct >= 55 ? 'var(--medium)' : 'var(--low)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <div style={{ flex: 1, height: '4px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '2px', transition: 'width 0.6s ease' }} />
      </div>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 700, color, minWidth: '38px' }}>
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}

function H2HBubbles({ results }: { results?: Array<{ result: string }> }) {
  const items = results || [];
  const slots = Array.from({ length: 5 }).map((_, i) => items[i] || { result: '-' });
  return (
    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
      {slots.map((r, i) => {
        const isW = r.result === 'W';
        const isD = r.result === 'D';
        const isL = r.result === 'L';
        const isEmpty = !isW && !isD && !isL;
        return (
          <div
            key={i}
            title={isW ? 'Vitória' : isD ? 'Empate' : isL ? 'Derrota' : 'Sem jogo'}
            style={{
              width: '20px', height: '20px', borderRadius: '50%',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '10px', fontWeight: 700,
              background: isEmpty ? 'rgba(255,255,255,0.05)' : isW ? 'rgba(34,197,94,0.2)' : isD ? 'rgba(245,158,11,0.2)' : 'rgba(239,68,68,0.2)',
              color: isEmpty ? 'var(--text-muted)' : isW ? 'var(--high)' : isD ? 'var(--medium)' : 'var(--low)',
              border: `1px solid ${isEmpty ? 'rgba(255,255,255,0.1)' : isW ? 'rgba(34,197,94,0.4)' : isD ? 'rgba(245,158,11,0.4)' : 'rgba(239,68,68,0.4)'}`,
            }}
          >
            {r.result}
          </div>
        );
      })}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData]           = useState<any>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [date, setDate]           = useState(() => new Date().toISOString().split('T')[0]);
  const [confFilter, setConfFilter] = useState<'all' | 'high' | 'medium'>('all');
  const [leagues, setLeagues]     = useState<{ league_id: number; league_name: string }[]>([]);
  const [selectedLeague, setSelectedLeague] = useState<number | null>(null);

  // Carrega lista de ligas do banco
  useEffect(() => {
    fetch('/api/leagues')
      .then(r => r.json())
      .then(d => setLeagues(Array.isArray(d) ? d : []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError('');
      try {
        const leagueParam = selectedLeague ? `&leagues=${selectedLeague}` : '';
        const res = await fetch(`/api/suggestions?date=${date}${leagueParam}`);
        if (!res.ok) throw new Error('Falha ao buscar dados');
        const json = await res.json();
        setData(json);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [date, selectedLeague]);

  const changeDate = (days: number) => {
    const d = new Date(date + 'T12:00:00');
    d.setDate(d.getDate() + days);
    setDate(d.toISOString().split('T')[0]);
  };

  const filtered = useMemo(() => {
    const all = data?.simples ?? [];
    if (confFilter === 'all') return all;
    return all.filter((m: any) => m.suggestion?.confidence_level === confFilter);
  }, [data, confFilter]);

  const highCount   = data?.simples?.filter((m: any) => m.suggestion?.confidence_level === 'high').length ?? 0;
  const mediumCount = data?.simples?.filter((m: any) => m.suggestion?.confidence_level === 'medium').length ?? 0;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Sugestões do Dia</h1>
        <p className="page-subtitle">Análise preditiva — Poisson + ELO + Forma + H2H</p>
      </div>

      {/* Controles */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '24px', alignItems: 'center' }}>
        {/* Date */}
        <div className="date-selector" style={{ margin: 0, flex: '1 1 auto', minWidth: '280px' }}>
          <button className="date-btn" onClick={() => changeDate(-1)}>← Ontem</button>
          <input type="date" className="date-input" value={date} onChange={e => setDate(e.target.value)} />
          <button className="date-btn" onClick={() => changeDate(1)}>Amanhã →</button>
          <button className="date-btn" onClick={() => setDate(new Date().toISOString().split('T')[0])}>Hoje</button>
        </div>

        {/* League filter */}
        <select
          value={selectedLeague ?? ''}
          onChange={e => setSelectedLeague(e.target.value ? parseInt(e.target.value) : null)}
          style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            color: 'var(--text-primary)',
            padding: '8px 14px',
            borderRadius: '8px',
            fontSize: '14px',
            cursor: 'pointer',
            minWidth: '200px',
          }}
        >
          <option value="">🌍 Todas as Ligas</option>
          {leagues.map(l => (
            <option key={l.league_id} value={l.league_id}>{l.league_name}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="empty-state">
          <div className="spinner" style={{ margin: '0 auto 16px' }}></div>
          <p>Analisando partidas e calculando probabilidades...</p>
        </div>
      ) : error ? (
        <div className="empty-state">
          <div className="empty-icon">⚠️</div>
          <p style={{ color: 'var(--low)' }}>{error}</p>
        </div>
      ) : !data || data.simples.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📅</div>
          <h3 className="empty-title">Nenhuma sugestão para esta data</h3>
          <p className="empty-desc">Não encontramos partidas com dados suficientes para o dia selecionado.</p>
        </div>
      ) : (
        <>
          {/* Stats Bar */}
          <div className="stats-bar">
            <div className="stat-item">
              <div className="stat-label">Total de Jogos</div>
              <div className="stat-value">{data.total_matches}</div>
            </div>
            <div className="stat-item">
              <div className="stat-label">Analisados</div>
              <div className="stat-value">{data.analyzed}</div>
            </div>
            <div className="stat-item" style={{ borderColor: 'rgba(34,197,94,0.2)' }}>
              <div className="stat-label">Alta Confiança 🟢</div>
              <div className="stat-value" style={{ color: 'var(--high)' }}>{highCount}</div>
            </div>
            <div className="stat-item" style={{ borderColor: 'rgba(245,158,11,0.2)' }}>
              <div className="stat-label">Confiança Média 🟡</div>
              <div className="stat-value" style={{ color: 'var(--medium)' }}>{mediumCount}</div>
            </div>
          </div>

          {/* Filter tabs */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>
              Melhores Oportunidades
            </h2>
            <div className="tabs" style={{ margin: 0 }}>
              {(['all', 'high', 'medium'] as const).map(f => (
                <button key={f} className={`tab ${confFilter === f ? 'active' : ''}`} onClick={() => setConfFilter(f)}>
                  {f === 'all' ? 'Todas' : f === 'high' ? '🟢 Alta' : '🟡 Média'}
                </button>
              ))}
            </div>
          </div>

          <div className="matches-grid">
            {filtered.map((match: any) => {
              const sg = match.suggestion;
              const confClass = sg.confidence_level;
              const icon = MARKET_ICONS[sg.market] ?? '📊';
              const homeWinWidth = match.home_win_prob ?? 0;
              const drawWidth    = match.draw_prob ?? 0;
              const awayWinWidth = match.away_win_prob ?? 0;
              const total1x2     = homeWinWidth + drawWidth + awayWinWidth || 100;
              const h2h          = match.h2h;
              const homeForm     = match.home_form;
              const awayForm     = match.away_form;

              return (
                <div key={match.fixture_id} className={`match-card ${confClass}-confidence`}>
                  <div className="match-header">
                    <div className="match-meta">
                      <span className="league-badge">{match.league_name}</span>
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        {match.date ? new Date(match.date).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : ''}
                      </span>
                    </div>
                    <div className={`confidence-badge ${confClass}`}>
                      {confClass === 'high' ? '🟢' : confClass === 'medium' ? '🟡' : '🔴'}
                      {sg.confidence}%
                    </div>
                  </div>

                  {/* Teams */}
                  <div className="match-teams">
                    <div style={{ textAlign: 'center', flex: 1 }}>
                      <div className="team-name">{match.home_team}</div>
                      <div style={{ marginTop: '4px', display: 'flex', justifyContent: 'center' }}>
                        <H2HBubbles results={homeForm?.results} />
                      </div>
                    </div>
                    <div className="match-vs">vs</div>
                    <div style={{ textAlign: 'center', flex: 1 }}>
                      <div className="team-name away">{match.away_team}</div>
                      <div style={{ marginTop: '4px', display: 'flex', justifyContent: 'center' }}>
                        <H2HBubbles results={awayForm?.results} />
                      </div>
                    </div>
                  </div>

                  {/* H2H Compacto */}
                  <div style={{
                    background: 'rgba(255,255,255,0.03)',
                    borderRadius: '8px',
                    padding: '8px 10px',
                    marginBottom: '10px',
                    border: '1px solid var(--border)',
                    minHeight: '74px',
                  }}>
                    {h2h && h2h.total >= 2 ? (
                      <>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                          H2H — últimos {h2h.total} confrontos
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <div style={{ flex: 1, textAlign: 'center' }}>
                            <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--high)' }}>{h2h.team1_wins}</div>
                            <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Vitórias</div>
                          </div>
                          <div style={{ flex: 1, textAlign: 'center' }}>
                            <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--medium)' }}>{h2h.draws}</div>
                            <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Empates</div>
                          </div>
                          <div style={{ flex: 1, textAlign: 'center' }}>
                            <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--low)' }}>{h2h.team2_wins}</div>
                            <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Vitórias</div>
                          </div>
                          <div style={{ flex: 1, textAlign: 'center', borderLeft: '1px solid var(--border)', paddingLeft: '8px' }}>
                            <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-secondary)' }}>{h2h.avg_goals}</div>
                            <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Gols/jogo</div>
                          </div>
                        </div>
                        {/* H2H bubbles */}
                        <div style={{ marginTop: '6px', display: 'flex', justifyContent: 'center' }}>
                          <H2HBubbles results={h2h.last5 ?? []} />
                        </div>
                      </>
                    ) : (
                      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
                         <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Sem histórico direto suficiente</div>
                      </div>
                    )}
                  </div>

                  {/* xG bars */}
                  <div className="xg-row">
                    <div>xG: <span className="xg-val" style={{ color: 'var(--accent-bright)' }}>{match.home_xg}</span></div>
                    <div className="xg-bar-container">
                      <div className="xg-bar-home" style={{ width: `${(match.home_xg / (match.home_xg + match.away_xg || 1)) * 100}%` }} />
                      <div className="xg-bar-away" style={{ width: `${(match.away_xg / (match.home_xg + match.away_xg || 1)) * 100}%` }} />
                    </div>
                    <div>xG: <span className="xg-val" style={{ color: '#a78bfa' }}>{match.away_xg}</span></div>
                  </div>

                  {/* 1X2 probability bars */}
                  <div className="prob-bars" style={{ marginBottom: '4px' }}>
                    <div className="prob-bar-home" style={{ width: `${(homeWinWidth / total1x2) * 100}%` }} />
                    <div className="prob-bar-draw"  style={{ width: `${(drawWidth / total1x2) * 100}%` }} />
                    <div className="prob-bar-away"  style={{ width: `${(awayWinWidth / total1x2) * 100}%` }} />
                  </div>
                  <div className="prob-labels">
                    <div><span className="prob-label-val">{homeWinWidth.toFixed(0)}%</span> Casa</div>
                    <div>Emp <span className="prob-label-val">{drawWidth.toFixed(0)}%</span></div>
                    <div>Fora <span className="prob-label-val">{awayWinWidth.toFixed(0)}%</span></div>
                  </div>

                  {/* Confidence meter */}
                  <div style={{ marginBottom: '12px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '5px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Confiança do modelo</div>
                    <ConfidenceMeter value={sg.confidence} />
                  </div>

                  {/* AI Insights */}
                  <div style={{
                    background: 'rgba(99,102,241,0.06)',
                    border: '1px solid rgba(99,102,241,0.2)',
                    borderRadius: '8px',
                    padding: '10px',
                    marginBottom: '12px',
                    minHeight: '80px',
                  }}>
                    <div style={{ fontSize: '10px', color: 'var(--accent-bright)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 700 }}>
                      💡 Análise IA
                    </div>
                    {match.insights?.length > 0 ? (
                      match.insights.slice(0, 2).map((insight: string, i: number) => (
                        <div key={i} style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px', lineHeight: 1.4 }}>
                          {insight}
                        </div>
                      ))
                    ) : (
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        Aguardando mais dados históricos para gerar conclusões precisas.
                      </div>
                    )}
                  </div>

                  {/* Suggestion Box */}
                  <div className="suggestion-box">
                    <div>
                      <div className="suggestion-market">{icon} {sg.market.replace(/_/g, ' ')}</div>
                      <div className="suggestion-label">{sg.label}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '3px' }}>
                        Prob: {sg.probability}%
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div className="suggestion-odd-label">ODD JUSTA</div>
                      <div className="suggestion-odd">{sg.fair_odd?.toFixed(2)}</div>
                    </div>
                  </div>

                  {/* All suggestions row */}
                  {match.all_suggestions?.length > 1 && (
                    <div style={{ marginTop: '10px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                      {match.all_suggestions.slice(1, 4).map((s: any, i: number) => (
                        <div key={i} style={{
                          fontSize: '11px', padding: '3px 8px',
                          borderRadius: '20px',
                          background: 'rgba(255,255,255,0.04)',
                          border: '1px solid var(--border)',
                          color: 'var(--text-muted)',
                        }}>
                          {s.label} · {s.probability}%
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Link para análise completa */}
                  <Link
                    href={`/confronto/${match.fixture_id}?home_id=${match.home_team_id}&away_id=${match.away_team_id}&home=${encodeURIComponent(match.home_team)}&away=${encodeURIComponent(match.away_team)}&league=${encodeURIComponent(match.league_name)}&date=${match.date}`}
                    style={{
                      display: 'block',
                      marginTop: '12px',
                      padding: '8px',
                      textAlign: 'center',
                      background: 'rgba(99,102,241,0.08)',
                      border: '1px solid rgba(99,102,241,0.2)',
                      borderRadius: '8px',
                      color: 'var(--accent-bright)',
                      fontSize: '12px',
                      fontWeight: 600,
                      textDecoration: 'none',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    🔍 Análise Completa do Confronto →
                  </Link>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
