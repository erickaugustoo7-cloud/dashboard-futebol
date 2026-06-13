'use client';

import { useState, useEffect } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import Link from 'next/link';

const RESULT_COLORS = {
  W: { bg: 'rgba(34,197,94,0.15)', border: 'rgba(34,197,94,0.4)', color: 'var(--high)', label: 'V' },
  D: { bg: 'rgba(245,158,11,0.15)', border: 'rgba(245,158,11,0.4)', color: 'var(--medium)', label: 'E' },
  L: { bg: 'rgba(239,68,68,0.15)', border: 'rgba(239,68,68,0.4)', color: 'var(--low)', label: 'D' },
};

function StatBar({ label, homeVal, awayVal, format = (v: number) => `${v}` }: {
  label: string;
  homeVal: number;
  awayVal: number;
  format?: (v: number) => string;
}) {
  const total = homeVal + awayVal || 1;
  const homePct = (homeVal / total) * 100;
  const awayPct = (awayVal / total) * 100;
  const homeLeads = homeVal >= awayVal;

  return (
    <div style={{ marginBottom: '14px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px', fontSize: '13px' }}>
        <span style={{ color: homeLeads ? 'var(--accent-bright)' : 'var(--text-muted)', fontWeight: homeLeads ? 700 : 400 }}>
          {format(homeVal)}
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</span>
        <span style={{ color: !homeLeads ? '#a78bfa' : 'var(--text-muted)', fontWeight: !homeLeads ? 700 : 400 }}>
          {format(awayVal)}
        </span>
      </div>
      <div style={{ display: 'flex', height: '6px', borderRadius: '3px', overflow: 'hidden', gap: '2px' }}>
        <div style={{ width: `${homePct}%`, background: 'var(--accent-bright)', borderRadius: '3px 0 0 3px', transition: 'width 0.6s ease' }} />
        <div style={{ width: `${awayPct}%`, background: '#a78bfa', borderRadius: '0 3px 3px 0', transition: 'width 0.6s ease' }} />
      </div>
    </div>
  );
}

function ProbBar({ label, value, color = 'var(--high)' }: { label: string; value: number; color?: string }) {
  return (
    <div style={{ marginBottom: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
        <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ fontSize: '14px', fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>{value.toFixed(1)}%</span>
      </div>
      <div style={{ height: '8px', background: 'rgba(255,255,255,0.06)', borderRadius: '4px', overflow: 'hidden' }}>
        <div style={{ width: `${value}%`, height: '100%', background: color, borderRadius: '4px', transition: 'width 0.8s ease' }} />
      </div>
    </div>
  );
}

function ResultBubble({ result }: { result: string }) {
  const cfg = RESULT_COLORS[result as keyof typeof RESULT_COLORS] ?? RESULT_COLORS.D;
  return (
    <div style={{
      width: '28px', height: '28px', borderRadius: '50%', display: 'flex',
      alignItems: 'center', justifyContent: 'center',
      background: cfg.bg, border: `1px solid ${cfg.border}`,
      color: cfg.color, fontSize: '11px', fontWeight: 800,
    }}>
      {cfg.label}
    </div>
  );
}

export default function ConfrontoPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const fixtureId = params.id as string;

  const homeId   = searchParams.get('home_id');
  const awayId   = searchParams.get('away_id');
  const homeName = searchParams.get('home') ?? 'Mandante';
  const awayName = searchParams.get('away') ?? 'Visitante';
  const league   = searchParams.get('league') ?? '';
  let dateRaw = searchParams.get('date') ?? '';
  if (dateRaw === 'undefined' || dateRaw === 'null' || dateRaw === 'Invalid Date') dateRaw = '';
  const date = dateRaw || new Date().toISOString().split('T')[0];

  const [h2h, setH2H]         = useState<any>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    if (!homeId || !awayId) return;
    setLoading(true);

    // Busca H2H e a análise em paralelo
    Promise.all([
      fetch(`/api/h2h?home_id=${homeId}&away_id=${awayId}&limit=10`).then(r => r.json()),
      fetch(`/api/suggestions?fixture_id=${fixtureId}`).then(r => r.json()),
    ]).then(([h2hData, suggestionsData]) => {
      setH2H(h2hData);
      // Encontra a análise específica desta partida
      const matchAnalysis = suggestionsData?.simples?.find((m: any) => String(m.fixture_id) === String(fixtureId));
      setAnalysis(matchAnalysis ?? null);
    }).catch(console.error)
      .finally(() => setLoading(false));
  }, [homeId, awayId, fixtureId, date]);

  if (loading) {
    return (
      <div className="empty-state">
        <div className="spinner" style={{ margin: '0 auto 16px' }}></div>
        <p>Carregando análise do confronto...</p>
      </div>
    );
  }

  const parsedDate = date ? new Date(date) : null;
  const dateLabel = (parsedDate && !isNaN(parsedDate.getTime())) 
    ? parsedDate.toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' }) 
    : '';

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <Link href="/" style={{ color: 'var(--text-muted)', fontSize: '13px', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px', marginBottom: '16px' }}>
          ← Voltar para Sugestões
        </Link>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px', flexWrap: 'wrap' }}>
          <span className="league-badge">{league}</span>
          {dateLabel && <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{dateLabel}</span>}
        </div>
        <h1 className="page-title">{homeName} <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: '28px' }}>vs</span> {awayName}</h1>
        <p className="page-subtitle">Análise completa do confronto baseada em dados históricos</p>
      </div>

      {/* Grid principal */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>

        {/* Probabilidades */}
        {analysis && (
          <div className="card">
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '18px' }}>
              📊 Probabilidades do Modelo
            </h3>
            <ProbBar label={`Vitória ${homeName}`} value={analysis.home_win_prob} color="var(--accent-bright)" />
            <ProbBar label="Empate" value={analysis.draw_prob} color="var(--medium)" />
            <ProbBar label={`Vitória ${awayName}`} value={analysis.away_win_prob} color="#a78bfa" />
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: '14px', marginTop: '4px' }}>
              <ProbBar label="Over 2.5 Gols" value={analysis.over25_prob} color="var(--high)" />
              <ProbBar label="Ambos Marcam (BTTS)" value={analysis.btts_prob} color="var(--medium)" />
            </div>

            {/* xG */}
            <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: '14px', padding: '12px', background: 'rgba(255,255,255,0.03)', borderRadius: '8px' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--accent-bright)', fontFamily: 'var(--font-mono)' }}>{analysis.home_xg}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>xG {homeName}</div>
              </div>
              <div style={{ textAlign: 'center', alignSelf: 'center', color: 'var(--text-muted)', fontWeight: 700 }}>xG</div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 800, color: '#a78bfa', fontFamily: 'var(--font-mono)' }}>{analysis.away_xg}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>xG {awayName}</div>
              </div>
            </div>

            {/* Melhor sugestão */}
            {analysis.suggestion && (
              <div className="suggestion-box" style={{ marginTop: '14px' }}>
                <div>
                  <div className="suggestion-market">🎯 Melhor Aposta</div>
                  <div className="suggestion-label">{analysis.suggestion.label}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Confiança: {analysis.suggestion.confidence}%
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div className="suggestion-odd-label">ODD JUSTA</div>
                  <div className="suggestion-odd">{analysis.suggestion.fair_odd?.toFixed(2)}</div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* H2H Summary */}
        {h2h && h2h.total_matches > 0 && (
          <div className="card">
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '18px' }}>
              ⚔️ Confronto Direto (H2H) — {h2h.total_matches} jogos
            </h3>

            {/* Placar H2H */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-around', marginBottom: '20px', padding: '16px', background: 'rgba(255,255,255,0.03)', borderRadius: '12px' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '36px', fontWeight: 900, color: 'var(--high)' }}>{h2h.team1_wins}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Vitórias</div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 600 }}>{homeName}</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '36px', fontWeight: 900, color: 'var(--medium)' }}>{h2h.draws}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Empates</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '36px', fontWeight: 900, color: '#a78bfa' }}>{h2h.team2_wins}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Vitórias</div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 600 }}>{awayName}</div>
              </div>
            </div>

            {/* Métricas H2H */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '16px' }}>
              {[
                { label: 'Gols/jogo (H2H)', val: h2h.avg_total_goals ?? '—' },
                { label: 'BTTS %', val: h2h.btts_pct != null ? `${h2h.btts_pct}%` : '—' },
                { label: 'Over 2.5 %', val: h2h.over25_pct != null ? `${h2h.over25_pct}%` : '—' },
                { label: `Gols/jogo ${homeName}`, val: h2h.avg_goals_team1 ?? '—' },
              ].map(({ label, val }) => (
                <div key={label} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '8px', padding: '10px', textAlign: 'center', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)' }}>{val}</div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>{label}</div>
                </div>
              ))}
            </div>

            {/* Últimos H2H */}
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Últimos confrontos
              </div>
              {h2h.matches?.slice(0, 8).map((m: any, i: number) => {
                const res = m.result_for_team1;
                const resCfg = RESULT_COLORS[res as keyof typeof RESULT_COLORS];
                return (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: '10px',
                    padding: '8px 0', borderBottom: i < h2h.matches.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
                  }}>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', minWidth: '80px' }}>
                      {m.date?.substring(0, 10)}
                    </span>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {m.home_team_name} {m.goals_home}–{m.goals_away} {m.away_team_name}
                    </span>
                    <div style={{
                      minWidth: '22px', height: '22px', borderRadius: '4px',
                      background: resCfg?.bg, border: `1px solid ${resCfg?.border}`,
                      color: resCfg?.color, fontSize: '10px', fontWeight: 800,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      {resCfg?.label}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Forma Recente */}
        {analysis && (analysis.home_form || analysis.away_form) && (
          <div className="card">
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '18px' }}>
              📈 Forma Recente (Últimos 5 jogos)
            </h3>
            {[
              { name: homeName, form: analysis.home_form, color: 'var(--accent-bright)' },
              { name: awayName, form: analysis.away_form, color: '#a78bfa' },
            ].map(({ name, form, color }) => form && (
              <div key={name} style={{ marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 700, color }}>{name}</span>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{form.points} pts</span>
                </div>
                <div style={{ display: 'flex', gap: '6px', marginBottom: '10px' }}>
                  {form.results?.map((r: any, i: number) => (
                    <ResultBubble key={i} result={r.result} />
                  ))}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                  {[
                    { label: 'Gols/jogo (Pró)', val: form.avg_goals_for },
                    { label: 'Gols/jogo (Con)', val: form.avg_goals_against },
                    { label: 'Clean Sheets', val: form.clean_sheets },
                  ].map(({ label, val }) => (
                    <div key={label} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '6px', padding: '8px', textAlign: 'center', border: '1px solid var(--border)' }}>
                      <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary)' }}>{val}</div>
                      <div style={{ fontSize: '9px', color: 'var(--text-muted)', marginTop: '2px' }}>{label}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* AI Insights */}
        {analysis?.insights?.length > 0 && (
          <div className="card" style={{ border: '1px solid rgba(99,102,241,0.3)', background: 'linear-gradient(135deg, rgba(99,102,241,0.05), rgba(139,92,246,0.05))' }}>
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--accent-bright)', marginBottom: '18px' }}>
              💡 Análise IA — Insights do Confronto
            </h3>
            {analysis.insights.map((insight: string, i: number) => (
              <div key={i} style={{
                display: 'flex', gap: '10px', marginBottom: '12px',
                padding: '10px', background: 'rgba(255,255,255,0.03)',
                borderRadius: '8px', border: '1px solid var(--border)',
              }}>
                <div style={{ minWidth: '24px', height: '24px', borderRadius: '50%', background: 'rgba(99,102,241,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 800, color: 'var(--accent-bright)' }}>
                  {i + 1}
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>{insight}</p>
              </div>
            ))}

            {/* Outros mercados */}
            {analysis.all_suggestions?.length > 1 && (
              <div style={{ marginTop: '16px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Outros mercados analisados
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {analysis.all_suggestions.map((s: any, i: number) => (
                    <div key={i} style={{
                      fontSize: '12px', padding: '5px 10px', borderRadius: '20px',
                      background: i === 0 ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.05)',
                      border: `1px solid ${i === 0 ? 'rgba(99,102,241,0.4)' : 'var(--border)'}`,
                      color: i === 0 ? 'var(--accent-bright)' : 'var(--text-muted)',
                    }}>
                      {s.label} · {s.probability}% · odd {s.fair_odd?.toFixed(2)}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
