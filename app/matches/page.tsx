'use client';

import { useState, useEffect, useMemo } from 'react';

const STATUS_LABELS: Record<string, { label: string; cls: string }> = {
  FT:   { label: 'Encerrado',   cls: 'high'   },
  NS:   { label: 'Agendado',    cls: 'medium'  },
  '1H': { label: '1º Tempo',    cls: 'live'    },
  'HT': { label: 'Intervalo',   cls: 'live'    },
  '2H': { label: '2º Tempo',    cls: 'live'    },
  ET:   { label: 'Prorrogação', cls: 'live'    },
  PEN:  { label: 'Pênaltis',    cls: 'live'    },
};

function getStatusInfo(status: string) {
  return STATUS_LABELS[status] ?? { label: status, cls: 'medium' };
}

function formatTime(isoDate: string) {
  try {
    return isoDate.substring(11, 16);
  } catch {
    return '--:--';
  }
}

export default function Matches() {
  const [matches, setMatches]     = useState<any[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [date, setDate]           = useState(() => new Date().toISOString().split('T')[0]);
  const [search, setSearch]       = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [leagueFilter, setLeagueFilter] = useState<string>('ALL');
  const [view, setView]           = useState<'grouped' | 'list'>('grouped');

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError('');
      try {
        const res = await fetch(`/api/matches?date=${date}`);
        const text = await res.text();
        let json;
        try { json = JSON.parse(text); } catch { throw new Error('Erro na resposta do servidor'); }
        if (!res.ok) throw new Error(json.error || 'Falha ao buscar dados');
        setMatches(json);
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

  // Compute unique leagues for filter dropdown
  const leagues = useMemo(() => {
    const set = new Set(matches.map(m => m.league_name).filter(Boolean));
    return Array.from(set).sort();
  }, [matches]);

  // Filter matches
  const filtered = useMemo(() => {
    return matches.filter(m => {
      const q = search.toLowerCase();
      const matchSearch = !q || 
        m.home_team_name?.toLowerCase().includes(q) || 
        m.away_team_name?.toLowerCase().includes(q) ||
        m.league_name?.toLowerCase().includes(q);
      const matchStatus = statusFilter === 'ALL' || m.status === statusFilter;
      const matchLeague = leagueFilter === 'ALL' || m.league_name === leagueFilter;
      return matchSearch && matchStatus && matchLeague;
    });
  }, [matches, search, statusFilter, leagueFilter]);

  // Group by league
  const grouped = useMemo(() => {
    const map = new Map<string, any[]>();
    filtered.forEach(m => {
      const lg = m.league_name || 'Outros';
      if (!map.has(lg)) map.set(lg, []);
      map.get(lg)!.push(m);
    });
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [filtered]);

  const liveCount = matches.filter(m => ['1H','HT','2H','ET','PEN'].includes(m.status)).length;
  const ftCount   = matches.filter(m => m.status === 'FT').length;
  const nsCount   = matches.filter(m => m.status === 'NS').length;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Todas as Partidas</h1>
        <p className="page-subtitle">Navegue pelo histórico completo e acompanhe jogos ao vivo</p>
      </div>

      {/* Date Selector */}
      <div className="date-selector">
        <button className="date-btn" onClick={() => changeDate(-1)}>← Ontem</button>
        <input
          type="date"
          className="date-input"
          value={date}
          onChange={e => setDate(e.target.value)}
        />
        <button className="date-btn" onClick={() => changeDate(1)}>Amanhã →</button>
        <button className="date-btn" onClick={() => setDate(new Date().toISOString().split('T')[0])}>Hoje</button>
      </div>

      {/* Stats Bar */}
      {!loading && !error && matches.length > 0 && (
        <div className="stats-bar" style={{ marginBottom: '20px' }}>
          <div className="stat-item">
            <div className="stat-label">Total</div>
            <div className="stat-value">{matches.length}</div>
          </div>
          {liveCount > 0 && (
            <div className="stat-item" style={{ borderColor: 'rgba(239,68,68,0.3)' }}>
              <div className="stat-label">Ao Vivo 🔴</div>
              <div className="stat-value" style={{ color: 'var(--low)' }}>{liveCount}</div>
            </div>
          )}
          <div className="stat-item">
            <div className="stat-label">Encerrados</div>
            <div className="stat-value">{ftCount}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">Agendados</div>
            <div className="stat-value" style={{ color: 'var(--text-secondary)' }}>{nsCount}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">Ligas</div>
            <div className="stat-value">{leagues.length}</div>
          </div>
        </div>
      )}

      {/* Filters Row */}
      {!loading && matches.length > 0 && (
        <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Search */}
          <div style={{ position: 'relative', flex: '1', minWidth: '200px' }}>
            <span style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', fontSize: '13px' }}>🔍</span>
            <input
              type="text"
              placeholder="Buscar time ou liga..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="search-input"
              style={{ paddingLeft: '34px', width: '100%' }}
            />
          </div>

          {/* Status Filter */}
          <div className="tabs" style={{ margin: 0 }}>
            {['ALL', 'NS', 'FT', '1H', 'HT', '2H'].map(s => (
              <button
                key={s}
                className={`tab ${statusFilter === s ? 'active' : ''}`}
                onClick={() => setStatusFilter(s)}
              >
                {s === 'ALL' ? 'Todos' : s === 'NS' ? 'Agendados' : s === 'FT' ? 'Encerrados' : s === '1H' ? '1º T' : s === 'HT' ? 'Intervalo' : '2º T'}
              </button>
            ))}
          </div>

          {/* League Filter */}
          {leagues.length > 1 && (
            <select
              value={leagueFilter}
              onChange={e => setLeagueFilter(e.target.value)}
              className="date-input"
              style={{ minWidth: '160px' }}
            >
              <option value="ALL">Todas as Ligas</option>
              {leagues.map(lg => (
                <option key={lg} value={lg}>{lg}</option>
              ))}
            </select>
          )}

          {/* View Toggle */}
          <div className="tabs" style={{ margin: 0 }}>
            <button className={`tab ${view === 'grouped' ? 'active' : ''}`} onClick={() => setView('grouped')}>🏆 Por Liga</button>
            <button className={`tab ${view === 'list' ? 'active' : ''}`} onClick={() => setView('list')}>📋 Lista</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="empty-state">
          <div className="spinner" style={{ margin: '0 auto 16px' }}></div>
          <p>Carregando partidas...</p>
        </div>
      ) : error ? (
        <div className="empty-state">
          <div className="empty-icon">⚠️</div>
          <p style={{ color: 'var(--low)' }}>{error}</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">⚽</div>
          <h3 className="empty-title">{matches.length === 0 ? 'Nenhuma partida encontrada' : 'Nenhum resultado para o filtro'}</h3>
          <p className="empty-desc">
            {matches.length === 0
              ? 'Não há jogos registrados no banco de dados para esta data.'
              : 'Tente ajustar os filtros de busca.'}
          </p>
        </div>
      ) : view === 'grouped' ? (
        /* Grouped by league */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
          {grouped.map(([league, leagueMatches]) => (
            <div key={league}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                marginBottom: '12px', paddingBottom: '10px',
                borderBottom: '1px solid var(--border)'
              }}>
                <span className="league-badge" style={{ fontSize: '12px', padding: '3px 10px' }}>
                  {league}
                </span>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  {leagueMatches.length} {leagueMatches.length === 1 ? 'jogo' : 'jogos'}
                </span>
              </div>
              <div className="matches-grid">
                {leagueMatches.map(match => (
                  <MatchCard key={match.fixture_id} match={match} />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Flat list */
        <div className="matches-grid">
          {filtered.map(match => (
            <MatchCard key={match.fixture_id} match={match} />
          ))}
        </div>
      )}
    </div>
  );
}

function MatchCard({ match }: { match: any }) {
  const statusInfo = getStatusInfo(match.status);
  const isLive = ['1H', 'HT', '2H', 'ET', 'PEN'].includes(match.status);
  const isFinished = match.status === 'FT';

  return (
    <div className={`match-card ${isFinished ? '' : isLive ? 'live-card' : ''}`}
      style={isLive ? { borderLeft: '3px solid var(--low)' } : {}}>
      <div className="match-header">
        <div className="match-meta">
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {formatTime(match.date)}
          </span>
          {match.league_name && (
            <span className="league-badge">{match.league_name}</span>
          )}
        </div>
        <div className={`confidence-badge ${statusInfo.cls}`}>
          {isLive && <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: 'var(--low)', marginRight: '5px', animation: 'pulse 1.5s infinite' }} />}
          {statusInfo.label}
        </div>
      </div>

      <div className="match-teams" style={{ marginBottom: isFinished ? '0' : '0' }}>
        <div className="team-name" style={isFinished && match.goals_home > match.goals_away ? { color: 'var(--high)' } : {}}>
          {match.home_team_name}
        </div>
        <div className="match-vs">
          {isFinished ? (
            <span style={{
              fontSize: '20px',
              fontWeight: 800,
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-primary)',
              letterSpacing: '2px'
            }}>
              {match.goals_home ?? '?'} – {match.goals_away ?? '?'}
            </span>
          ) : isLive ? (
            <span style={{ fontSize: '11px', color: 'var(--low)', fontWeight: 700, animation: 'pulse 1.5s infinite' }}>AO VIVO</span>
          ) : (
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>vs</span>
          )}
        </div>
        <div className="team-name away" style={isFinished && match.goals_away > match.goals_home ? { color: 'var(--high)' } : {}}>
          {match.away_team_name}
        </div>
      </div>
    </div>
  );
}
