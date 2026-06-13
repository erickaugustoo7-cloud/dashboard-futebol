'use client';

import { useState, useEffect } from 'react';

const EV_COLORS: Record<string, string> = {
  high:   'var(--high)',
  medium: 'var(--medium)',
  low:    'var(--low)',
};

function EvBadge({ ev }: { ev: number }) {
  const isPos  = ev > 0;
  const isHigh = ev > 5;
  const color  = isHigh ? 'var(--high)' : isPos ? 'var(--medium)' : 'var(--text-muted)';
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '4px',
      padding: '4px 10px', borderRadius: '20px',
      background: isPos ? (isHigh ? 'var(--high-bg)' : 'var(--medium-bg)') : 'rgba(148,163,184,0.08)',
      border: `1px solid ${isPos ? (isHigh ? 'var(--high-border)' : 'var(--medium-border)') : 'var(--border)'}`,
      fontSize: '13px', fontWeight: 700, color,
    }}>
      {isPos ? '↑' : '↓'} EV {isPos ? '+' : ''}{ev.toFixed(2)}%
    </div>
  );
}

function LegItem({ leg, index }: { leg: any; index: number }) {
  return (
    <div className="leg-item">
      <div className="leg-icon">{index + 1}</div>
      <div style={{ flex: 1 }}>
        <div className="leg-match">{leg.home_team} vs {leg.away_team}</div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '3px', flexWrap: 'wrap' }}>
          <span className="league-badge" style={{ fontSize: '10px' }}>{leg.league}</span>
          <span className="leg-market">{leg.label}</span>
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px', flexShrink: 0 }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '14px', fontWeight: 700, color: 'var(--high)' }}>
          {leg.fair_odd?.toFixed(2)}
        </div>
        <div className="leg-prob">{leg.probability?.toFixed(1)}%</div>
      </div>
    </div>
  );
}

export default function Combinadas() {
  const [data, setData]       = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [date, setDate]       = useState(() => new Date().toISOString().split('T')[0]);
  const [evFilter, setEvFilter] = useState<'all' | 'positive'>('all');

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError('');
      try {
        const res = await fetch(`/api/suggestions?date=${date}`);
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
  }, [date]);

  const changeDate = (days: number) => {
    const d = new Date(date + 'T12:00:00');
    d.setDate(d.getDate() + days);
    setDate(d.toISOString().split('T')[0]);
  };

  const combinadas = (data?.combinadas ?? []).filter((c: any) =>
    evFilter === 'all' ? true : c.ev_positive
  );

  const positiveCount = data?.combinadas?.filter((c: any) => c.ev_positive).length ?? 0;
  const bestEv = data?.combinadas?.length
    ? Math.max(...data.combinadas.map((c: any) => c.expected_value ?? -999))
    : null;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Bilhetes Combinados</h1>
        <p className="page-subtitle">Apostas múltiplas geradas automaticamente buscando o maior +EV (Expected Value)</p>
      </div>

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

      {loading ? (
        <div className="empty-state">
          <div className="spinner" style={{ margin: '0 auto 16px' }}></div>
          <p>Calculando bilhetes de +EV...</p>
        </div>
      ) : error ? (
        <div className="empty-state">
          <div className="empty-icon">⚠️</div>
          <p style={{ color: 'var(--low)' }}>{error}</p>
        </div>
      ) : !data || data.combinadas.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🎫</div>
          <h3 className="empty-title">Nenhuma combinada de valor</h3>
          <p className="empty-desc">O motor não encontrou 2+ jogos com confiança suficiente para gerar um bilhete +EV hoje.</p>
        </div>
      ) : (
        <>
          {/* Stats bar */}
          <div className="stats-bar" style={{ marginBottom: '20px' }}>
            <div className="stat-item">
              <div className="stat-label">Bilhetes gerados</div>
              <div className="stat-value">{data.combinadas.length}</div>
            </div>
            <div className="stat-item" style={{ borderColor: 'rgba(34,197,94,0.2)' }}>
              <div className="stat-label">Com +EV 🟢</div>
              <div className="stat-value" style={{ color: 'var(--high)' }}>{positiveCount}</div>
            </div>
            {bestEv !== null && (
              <div className="stat-item" style={{ borderColor: 'rgba(59,130,246,0.2)' }}>
                <div className="stat-label">Melhor EV</div>
                <div className="stat-value" style={{ color: bestEv > 0 ? 'var(--high)' : 'var(--text-secondary)' }}>
                  {bestEv > 0 ? '+' : ''}{bestEv.toFixed(2)}%
                </div>
              </div>
            )}
            <div className="stat-item">
              <div className="stat-label">Jogos base</div>
              <div className="stat-value">{data.analyzed ?? '—'}</div>
            </div>
          </div>

          {/* Filter */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>
              Bilhetes Disponíveis
            </h2>
            <div className="tabs" style={{ margin: 0 }}>
              <button className={`tab ${evFilter === 'all' ? 'active' : ''}`} onClick={() => setEvFilter('all')}>Todos</button>
              <button className={`tab ${evFilter === 'positive' ? 'active' : ''}`} onClick={() => setEvFilter('positive')}>🟢 +EV Apenas</button>
            </div>
          </div>

          <div className="combinadas-grid">
            {combinadas.map((combo: any, idx: number) => {
              const isPositive = combo.ev_positive;
              const evValue    = combo.expected_value ?? 0;

              return (
                <div key={idx} className={`combinada-card ${isPositive ? 'ev-positive' : 'ev-negative'}`}>
                  <div className="combinada-header">
                    <div>
                      <div className="combinada-type">{combo.label}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {combo.legs?.length ?? 0} seleções
                      </div>
                    </div>
                    <EvBadge ev={evValue} />
                  </div>

                  <div className="combinada-legs">
                    {combo.legs?.map((leg: any, i: number) => (
                      <LegItem key={i} leg={leg} index={i} />
                    ))}
                  </div>

                  {/* Probability visualization */}
                  <div style={{ marginBottom: '14px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px', fontSize: '11px', color: 'var(--text-muted)' }}>
                      <span>Probabilidade real</span>
                      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 700 }}>{combo.combined_probability?.toFixed(1)}%</span>
                    </div>
                    <div style={{ height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%',
                        width: `${Math.min(100, combo.combined_probability ?? 0)}%`,
                        background: isPositive ? 'var(--high)' : 'var(--text-muted)',
                        borderRadius: '3px',
                        transition: 'width 0.6s ease'
                      }} />
                    </div>
                  </div>

                  <div className="combinada-footer">
                    <div className="combinada-stat">
                      <div className="combinada-stat-val">{combo.combined_probability?.toFixed(1)}%</div>
                      <div className="combinada-stat-label">Prob. Real</div>
                    </div>
                    <div className="combinada-stat">
                      <div className="combinada-stat-val">{combo.avg_confidence?.toFixed(1)}%</div>
                      <div className="combinada-stat-label">Conf. Média</div>
                    </div>
                    <div className="combinada-stat">
                      <div className="combinada-stat-val" style={{ color: isPositive ? 'var(--high)' : 'var(--text-secondary)' }}>
                        {combo.combined_odd?.toFixed(2)}
                      </div>
                      <div className="combinada-stat-label">Odd Justa</div>
                    </div>
                  </div>

                  {/* Disclaimer */}
                  <div style={{
                    marginTop: '10px', padding: '8px 12px',
                    background: 'rgba(255,255,255,0.02)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '10px', color: 'var(--text-muted)',
                    borderTop: '1px solid var(--border)'
                  }}>
                    ⚠️ Odd justa calculada pelo modelo Poisson. Compare com as odds reais da sua casa de apostas antes de apostar.
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
