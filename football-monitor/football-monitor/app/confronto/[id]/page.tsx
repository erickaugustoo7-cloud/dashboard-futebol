'use client';

import { useState, useEffect } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import Link from 'next/link';

const RESULT_COLORS = {
  W: { bg: 'rgba(34,197,94,0.15)', border: 'rgba(34,197,94,0.4)', color: 'var(--high)', label: 'V' },
  D: { bg: 'rgba(245,158,11,0.15)', border: 'rgba(245,158,11,0.4)', color: 'var(--medium)', label: 'E' },
  L: { bg: 'rgba(239,68,68,0.15)', border: 'rgba(239,68,68,0.4)', color: 'var(--low)', label: 'D' },
};

function StatBar({ label, homeVal, awayVal, format = (v: number) => `${v}`, higherIsBetter = true }: {
  label: string; homeVal: number | null; awayVal: number | null; format?: (v: number) => string; higherIsBetter?: boolean;
}) {
  const h = homeVal ?? 0;
  const a = awayVal ?? 0;
  const total = h + a || 1;
  const homePct = homeVal == null && awayVal == null ? 50 : (homeVal == null ? 0 : (awayVal == null ? 100 : (h / total) * 100));
  const awayPct = homeVal == null && awayVal == null ? 50 : (awayVal == null ? 0 : (homeVal == null ? 100 : (a / total) * 100));
  const homeLeads = higherIsBetter ? h >= a : h <= a;
  
  const displayHome = homeVal != null ? format(homeVal) : '—';
  const displayAway = awayVal != null ? format(awayVal) : '—';

  return (
    <div style={{ marginBottom: '14px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px', fontSize: '13px' }}>
        <span style={{ color: homeVal != null && homeLeads ? 'var(--accent-bright)' : 'var(--text-muted)', fontWeight: homeVal != null && homeLeads ? 700 : 400 }}>{displayHome}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</span>
        <span style={{ color: awayVal != null && !homeLeads ? 'var(--medium)' : 'var(--text-muted)', fontWeight: awayVal != null && !homeLeads ? 700 : 400 }}>{displayAway}</span>
      </div>
      <div style={{ display: 'flex', height: '6px', borderRadius: '3px', overflow: 'hidden', gap: '2px' }}>
        <div style={{ width: `${homePct}%`, background: 'var(--accent-bright)', borderRadius: '3px 0 0 3px', transition: 'width 0.6s ease' }} />
        <div style={{ width: `${awayPct}%`, background: 'var(--medium)', borderRadius: '0 3px 3px 0', transition: 'width 0.6s ease' }} />
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

function ScoutStat({ icon, label, value, color = 'var(--text-primary)' }: { icon: string; label: string; value: string | number | null; color?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
      <span style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span>{icon}</span>{label}
      </span>
      <span style={{ fontSize: '13px', fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>
        {value != null ? value : '—'}
      </span>
    </div>
  );
}

function StrengthMeter({ value, label, color }: { value: number | null; label: string; color: string }) {
  const pct = value != null ? Math.min(100, Math.max(0, (value / 2) * 100)) : 50;
  const display = value != null ? value.toFixed(2) : '—';
  return (
    <div style={{ marginBottom: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '12px' }}>
        <span style={{ color: 'var(--text-muted)' }}>{label}</span>
        <span style={{ color, fontWeight: 700 }}>{display}</span>
      </div>
      <div style={{ height: '5px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '3px', transition: 'width 0.6s ease' }} />
      </div>
    </div>
  );
}

// Calcula posse estimada baseada em chutes + cantos (proxy)
function estimatePossession(shots: number | null, corners: number | null, oppShots: number | null, oppCorners: number | null) {
  if (shots == null && corners == null && oppShots == null && oppCorners == null) return null;
  if ((shots == null && corners == null) || (oppShots == null && oppCorners == null)) return null;
  const h = (shots ?? 0) + (corners ?? 0) * 0.5;
  const a = (oppShots ?? 0) + (oppCorners ?? 0) * 0.5;
  if (h === 0 && a === 0) return 50;
  const total = h + a;
  return Math.round((h / total) * 100);
}

// === Lógica de Distribuição de Poisson (Frontend) ===
function factorial(n: number): number {
  if (n <= 1) return 1;
  return n * factorial(n - 1);
}
function poissonPmf(k: number, lambda: number): number {
  return (Math.pow(lambda, k) * Math.exp(-lambda)) / factorial(k);
}
function poissonCdf(k: number, lambda: number): number {
  let cdf = 0;
  for (let i = 0; i <= k; i++) cdf += poissonPmf(i, lambda);
  return cdf;
}
function calcOdds(probPct: number): string {
  if (probPct >= 99.5) return '1.01';
  if (probPct <= 0.5) return '100.0';
  const odd = 100 / probPct;
  return odd.toFixed(2);
}

// Componente para Tabela Detalhada de Mercado (Over/Under)
function MarketLinesTable({ title, mean, minLine, maxLine, step = 1 }: { title: string; mean: number; minLine: number; maxLine: number; step?: number }) {
  const rows = [];
  for (let line = minLine; line <= maxLine; line += step) {
    // Probabilidade de MENOS DE (Under)
    const k = Math.floor(line); // ex: line 8.5 -> floor é 8. P(X <= 8)
    const underProb = poissonCdf(k, mean) * 100;
    const overProb = 100 - underProb;
    
    rows.push({
      line,
      overProb,
      underProb,
    });
  }

  return (
    <div style={{ marginBottom: '16px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid var(--border)', overflow: 'hidden' }}>
      <div 
        style={{ 
          width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
          padding: '14px 16px', background: 'rgba(255,255,255,0.01)', borderBottom: '1px solid var(--border)',
          color: 'var(--text-primary)', fontSize: '13px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px'
        }}
      >
        <span>{title}</span>
      </div>
      
      <div style={{ padding: '0 12px 12px 12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{ marginTop: '12px' }}>
          {rows.map((row, i) => (
            <div key={row.line} style={{ display: 'flex', gap: '4px', marginBottom: '4px' }}>
              {/* OVER */}
              <div style={{ flex: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', borderRadius: '4px', padding: '6px 8px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Mais de {row.line}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-bright)', fontFamily: 'var(--font-mono)' }}>{calcOdds(row.overProb)}</span>
                  <span style={{ fontSize: '9px', color: 'var(--text-muted)' }}>{row.overProb.toFixed(0)}%</span>
                </div>
              </div>
              {/* UNDER */}
              <div style={{ flex: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', borderRadius: '4px', padding: '6px 8px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Menos {row.line}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--medium)', fontFamily: 'var(--font-mono)' }}>{calcOdds(row.underProb)}</span>
                  <span style={{ fontSize: '9px', color: 'var(--text-muted)' }}>{row.underProb.toFixed(0)}%</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
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

  const [h2h, setH2H]           = useState<any>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    if (!homeId || !awayId) return;
    setLoading(true);
    Promise.all([
      fetch(`/api/h2h?home_id=${homeId}&away_id=${awayId}&limit=10`).then(r => r.json()),
      fetch(`/api/suggestions?fixture_id=${fixtureId}`).then(r => r.json()),
    ]).then(([h2hData, suggestionsData]) => {
      setH2H(h2hData);
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

  const hs = analysis?.home_scout;
  const as_ = analysis?.away_scout;

  // Posse estimada
  const homePoss = estimatePossession(hs?.avg_shots, hs?.avg_corners, as_?.avg_shots, as_?.avg_corners);
  const awayPoss = homePoss !== null ? 100 - homePoss : null;

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
        <h1 className="page-title">
          {homeName} 
          {analysis?.status === 'FT' ? (
            <span style={{ margin: '0 16px', color: 'var(--high)', fontSize: '32px', fontWeight: 800 }}>
              {analysis.goals_home} <span style={{ fontSize: '20px', color: 'var(--text-muted)', margin: '0 4px' }}>x</span> {analysis.goals_away}
            </span>
          ) : (
            <span style={{ margin: '0 16px', color: 'var(--text-muted)', fontWeight: 400, fontSize: '28px' }}>vs</span>
          )}
          {awayName}
        </h1>
        <p className="page-subtitle">Análise completa do confronto baseada em dados históricos</p>
      </div>

      {/* Layout principal (Mobile First -> Desktop estruturado) */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

        {/* === LINHA 1: Visão Geral (Probabilidades + IA) === */}
        <div style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: '24px' }}>
          
          {/* Coluna Esquerda: Dados e Tabelas */}
          <div style={{ flex: '1 1 65%', minWidth: '320px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
              {/* Probabilidades */}
          {analysis && (
            <div className="card">
              <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '18px' }}>
                Probabilidades do Modelo
              </h3>
              <ProbBar label={`Vitória ${homeName}`} value={analysis.home_win_prob} color="var(--accent-bright)" />
              <ProbBar label="Empate" value={analysis.draw_prob} color="var(--medium)" />
              <ProbBar label={`Vitória ${awayName}`} value={analysis.away_win_prob} color="var(--medium)" />
              <div style={{ borderTop: '1px solid var(--border)', paddingTop: '14px', marginTop: '4px' }}>
                <ProbBar label="Over 2.5 Gols" value={analysis.over25_prob} color="var(--high)" />
                <ProbBar label="Ambos Marcam (BTTS)" value={analysis.btts_prob} color="var(--medium)" />
              </div>
              {/* Chances de Gol */}
              <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: '14px', padding: '12px', background: 'rgba(255,255,255,0.03)', borderRadius: '8px' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--accent-bright)', fontFamily: 'var(--font-mono)' }}>{analysis.home_xg}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{homeName}</div>
                </div>
                <div style={{ textAlign: 'center', alignSelf: 'center', color: 'var(--text-muted)', fontWeight: 700, fontSize: '12px' }}>Chances de Gol</div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--medium)', fontFamily: 'var(--font-mono)' }}>{analysis.away_xg}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{awayName}</div>
                </div>
              </div>
              {/* Força do Time */}
              {(analysis.home_elo || analysis.away_elo) && (
                <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: '10px', padding: '10px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--accent-bright)', fontFamily: 'var(--font-mono)' }}>{analysis.home_elo?.toFixed(0) ?? '—'}</div>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{homeName}</div>
                  </div>
                  <div style={{ textAlign: 'center', alignSelf: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>Força do Time</div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--medium)', fontFamily: 'var(--font-mono)' }}>{analysis.away_elo?.toFixed(0) ?? '—'}</div>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{awayName}</div>
                  </div>
                </div>
              )}
              {/* Melhor sugestão */}
              {analysis.suggestion && (
                <div className="suggestion-box" style={{ marginTop: '14px' }}>
                  <div>
                    <div className="suggestion-market">Melhor Aposta</div>
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


          {/* Novos Mercados Alternativos */}
          {analysis && analysis.prob_1x !== undefined && (
            <div className="card" style={{ height: 'fit-content' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '18px' }}>
                Mercados Alternativos (Seguros)
              </h3>
              
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Dupla Chance</div>
                <ProbBar label="Mandante ou Empate (1X)" value={analysis.prob_1x} color="var(--accent-bright)" />
                <ProbBar label="Mandante ou Visitante (12)" value={analysis.prob_12} color="var(--high)" />
                <ProbBar label="Visitante ou Empate (X2)" value={analysis.prob_x2} color="var(--medium)" />
              </div>

              <div style={{ borderTop: '1px solid var(--border)', paddingTop: '16px', marginBottom: '16px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Draw No Bet (Empate Anula)</div>
                <ProbBar label={`DNB — ${homeName}`} value={analysis.prob_dnb_home} color="var(--accent-bright)" />
                <ProbBar label={`DNB — ${awayName}`} value={analysis.prob_dnb_away} color="var(--medium)" />
              </div>

              <div style={{ borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Gols das Equipes</div>
                <ProbBar label={`${homeName} Over 0.5 Gols`} value={analysis.prob_home_over05} color="var(--accent-bright)" />
                <ProbBar label={`${homeName} Over 1.5 Gols`} value={analysis.prob_home_over15} color="var(--high)" />
                <ProbBar label={`${awayName} Over 0.5 Gols`} value={analysis.prob_away_over05} color="var(--medium)" />
                <ProbBar label={`${awayName} Over 1.5 Gols`} value={analysis.prob_away_over15} color="var(--low)" />
              </div>
            </div>
          )}

          {/* Mercados de Estatísticas / Físicos (Principal) */}
          {analysis && analysis.corners_over85_prob !== undefined && (
            <div className="card" style={{ height: 'fit-content' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '18px' }}>
                Mercados de Estatísticas
              </h3>
              
              <div style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-muted)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  <span>🚩</span> Escanteios
                </div>
                <ProbBar label="Mais de 8.5 Escanteios" value={analysis.corners_over85_prob} color="var(--high)" />
                <ProbBar label="Mais de 10.5 Escanteios" value={analysis.corners_over105_prob} color="var(--medium)" />
              </div>

              <div style={{ borderTop: '1px solid var(--border)', paddingTop: '16px', marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-muted)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  <span>🟨</span> Cartões
                </div>
                <ProbBar label="Mais de 4.5 Cartões" value={analysis.cards_over45_prob} color="var(--accent-bright)" />
              </div>

              <div style={{ borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-muted)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  <span>🎯</span> Chutes ao Alvo
                </div>
                <ProbBar label="Mais de 8.5 Chutes no Gol (SOG)" value={analysis.sog_over85_prob} color="var(--high)" />
              </div>
            </div>
          )}
          </div> {/* Fecha o grid interno (Probabilidades, Mercados, etc) */}

          {/* Tabelas Expandidas de Linhas Completas */}
          {analysis && analysis.goals_mean !== undefined && analysis.corners_mean !== undefined && (
            <div className="card" style={{ height: 'fit-content' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '18px' }}>
                Linhas Completas (Odds Justas)
              </h3>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
                <MarketLinesTable title="⚽ Total de Gols" mean={analysis.goals_mean} minLine={0.5} maxLine={5.5} defaultExpanded={true} />
                <MarketLinesTable title="🚩 Escanteios" mean={analysis.corners_mean} minLine={5.5} maxLine={15.5} defaultExpanded={true} />
                <MarketLinesTable title="🟨 Cartões" mean={analysis.cards_mean} minLine={2.5} maxLine={8.5} defaultExpanded={true} />
                <MarketLinesTable title="🎯 Chutes ao Alvo" mean={analysis.sog_mean} minLine={5.5} maxLine={13.5} defaultExpanded={true} />
              </div>
            </div>
          )}
          </div>

          {/* Coluna Direita: Análise IA */}
          <div style={{ flex: '1 1 30%', minWidth: '320px', maxWidth: '400px' }}>
            {analysis?.insights?.length > 0 && (
              <div className="card" style={{ height: 'fit-content' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '18px' }}>
                  Análise IA — Insights do Confronto
                </h3>
                {analysis.insights.map((insight: string, i: number) => (
                  <div key={i} style={{ display: 'flex', gap: '10px', marginBottom: '12px', padding: '10px', background: 'rgba(255,255,255,0.03)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                    <div style={{ minWidth: '24px', height: '24px', borderRadius: '50%', background: 'rgba(99,102,241,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 800, color: 'var(--accent-bright)' }}>
                      {i + 1}
                    </div>
                    <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>{insight}</p>
                  </div>
                ))}
                {analysis.all_suggestions?.length > 1 && (
                  <div style={{ marginTop: '16px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Outros mercados analisados</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {analysis.all_suggestions.map((s: any, i: number) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', borderRadius: '4px', padding: '6px 8px' }}>
                          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{s.label}</span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--accent-bright)', fontFamily: 'var(--font-mono)' }}>{s.fair_odd?.toFixed(2)}</span>
                            <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{s.probability}%</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* === LINHA 2: Scout Comparativo & H2H === */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
          {/* Scout Comparativo */}
          {(hs || as_) && (
            <div className="card">
              <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
                Scout Comparativo
              </h3>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px', fontSize: '12px' }}>
                <span style={{ color: 'var(--accent-bright)', fontWeight: 700 }}>{homeName}</span>
                <span style={{ color: 'var(--text-muted)' }}>Estatística</span>
                <span style={{ color: 'var(--medium)', fontWeight: 700 }}>{awayName}</span>
              </div>

              {/* Posse de Bola */}
              {(homePoss !== null || awayPoss !== null) && (
                <StatBar
                  label="Posse de Bola %"
                  homeVal={homePoss}
                  awayVal={awayPoss}
                  format={v => `${v.toFixed(0)}%`}
                />
              )}

              {(hs?.avg_shots != null || as_?.avg_shots != null) && (
                <StatBar label="Chutes/jogo" homeVal={hs?.avg_shots ?? null} awayVal={as_?.avg_shots ?? null} format={v => v.toFixed(1)} />
              )}
              {(hs?.avg_sog != null || as_?.avg_sog != null) && (
                <StatBar label="Chutes no alvo" homeVal={hs?.avg_sog ?? null} awayVal={as_?.avg_sog ?? null} format={v => v.toFixed(1)} />
              )}
              {(hs?.avg_corners != null || as_?.avg_corners != null) && (
                <StatBar label="Escanteios/jogo" homeVal={hs?.avg_corners ?? null} awayVal={as_?.avg_corners ?? null} format={v => v.toFixed(1)} />
              )}
              {(hs?.avg_yellow_cards != null || as_?.avg_yellow_cards != null) && (
                <StatBar
                  label="Cartões amarelos"
                  homeVal={hs?.avg_yellow_cards ?? null}
                  awayVal={as_?.avg_yellow_cards ?? null}
                  format={v => v.toFixed(2)}
                  higherIsBetter={false}
                />
              )}
              {(hs?.avg_goals_scored != null || as_?.avg_goals_scored != null) && (
                <StatBar label="Gols marcados/jogo" homeVal={hs?.avg_goals_scored ?? null} awayVal={as_?.avg_goals_scored ?? null} format={v => v.toFixed(2)} />
              )}
              {(hs?.avg_goals_conceded != null || as_?.avg_goals_conceded != null) && (
                <StatBar
                  label="Gols sofridos/jogo"
                  homeVal={hs?.avg_goals_conceded ?? null}
                  awayVal={as_?.avg_goals_conceded ?? null}
                  format={v => v.toFixed(2)}
                  higherIsBetter={false}
                />
              )}
              {(hs?.over25_pct != null || as_?.over25_pct != null) && (
                <StatBar label="Over 2.5 (histórico %)" homeVal={hs?.over25_pct ?? null} awayVal={as_?.over25_pct ?? null} format={v => `${v}%`} />
              )}
            </div>
          )}

          {/* H2H */}
          {h2h && h2h.total_matches > 0 && (
            <div className="card" style={{ height: 'fit-content' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '18px' }}>
                Confronto Direto (H2H) — {h2h.total_matches} jogos
              </h3>
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
                  <div style={{ fontSize: '36px', fontWeight: 900, color: 'var(--medium)' }}>{h2h.team2_wins}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Vitórias</div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 600 }}>{awayName}</div>
                </div>
              </div>
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
              <div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Últimos confrontos</div>
                {h2h.matches?.slice(0, 8).map((m: any, i: number) => {
                  const res = m.result_for_team1;
                  const resCfg = RESULT_COLORS[res as keyof typeof RESULT_COLORS];
                  return (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '8px 0', borderBottom: i < h2h.matches.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none' }}>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)', minWidth: '80px' }}>{m.date?.substring(0, 10)}</span>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {m.home_team_name} {m.goals_home}–{m.goals_away} {m.away_team_name}
                      </span>
                      <div style={{ minWidth: '22px', height: '22px', borderRadius: '4px', background: resCfg?.bg, border: `1px solid ${resCfg?.border}`, color: resCfg?.color, fontSize: '10px', fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {resCfg?.label}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* === LINHA 3: Perfis Individuais === */}
        {(hs || as_) && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
            {/* Scout do Mandante */}
            {hs && (
              <div className="card">
                <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--accent-bright)', marginBottom: '16px' }}>
                  Scout — {homeName}
                </h3>

                {analysis?.home_form?.results && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>Forma Recente</div>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      {analysis.home_form.results.map((r: any, i: number) => (
                        <ResultBubble key={i} result={r.result} />
                      ))}
                    </div>
                  </div>
                )}

                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '10px' }}>Força do Time</div>
                  <StrengthMeter value={hs.attack_strength} label="Força de Ataque" color="var(--high)" />
                  <StrengthMeter value={hs.defense_strength} label="Solidez Defensiva" color="var(--accent-bright)" />
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>Dados da Temporada</div>
                  {homePoss !== null && <ScoutStat icon="" label="Posse estimada" value={`${homePoss}%`} color="var(--accent-bright)" />}
                  <ScoutStat icon="" label="Chutes por jogo" value={hs.avg_shots?.toFixed(1)} />
                  <ScoutStat icon="" label="Chutes no alvo" value={hs.avg_sog?.toFixed(1)} />
                  <ScoutStat icon="" label="Escanteios por jogo" value={hs.avg_corners?.toFixed(1)} />
                  <ScoutStat icon="" label="Cartões amarelos/jogo" value={hs.avg_yellow_cards?.toFixed(2)} color="var(--medium)" />
                  <ScoutStat icon="" label="Gols marcados/jogo" value={hs.avg_goals_scored?.toFixed(2)} color="var(--high)" />
                  <ScoutStat icon="" label="Gols sofridos/jogo" value={hs.avg_goals_conceded?.toFixed(2)} color="var(--medium)" />
                  <ScoutStat icon="" label="% jogos Over 2.5" value={hs.over25_pct != null ? `${hs.over25_pct}%` : null} />
                  <ScoutStat icon="" label="% Ambas Marcam" value={hs.btts_pct != null ? `${hs.btts_pct}%` : null} />
                  <ScoutStat icon="" label="% Vitória em casa" value={hs.home_win_pct != null ? `${hs.home_win_pct}%` : null} color="var(--high)" />
                  <ScoutStat icon="" label="Partidas analisadas" value={hs.total_matches} />
                  {hs.fatigue_score != null && (
                    <ScoutStat icon="" label="Fadiga (0=descansado)" value={`${hs.fatigue_score}/10`} color={hs.fatigue_score > 6 ? 'var(--medium)' : hs.fatigue_score > 3 ? 'var(--medium)' : 'var(--high)'} />
                  )}
                </div>

                {/* Destaques do time */}
                <div style={{ background: 'rgba(99,102,241,0.06)', borderRadius: '8px', padding: '12px', border: '1px solid rgba(99,102,241,0.15)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--accent-bright)', fontWeight: 700, marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    Destaques do Perfil
                  </div>
                  {hs.attack_strength != null && hs.attack_strength > 1.2 && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Ataque acima da média da liga</div>
                  )}
                  {hs.defense_strength != null && hs.defense_strength < 0.85 && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Defesa sólida — sofre poucos gols</div>
                  )}
                  {hs.avg_yellow_cards != null && hs.avg_yellow_cards > 2.5 && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Time agressivo — alto volume de cartões</div>
                  )}
                  {hs.over25_pct != null && hs.over25_pct > 60 && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Jogos com muitos gols ({hs.over25_pct}% Over 2.5)</div>
                  )}
                  {hs.avg_corners != null && hs.avg_corners > 6 && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Alto volume de escanteios gerados</div>
                  )}
                  {hs.home_win_pct != null && hs.home_win_pct > 55 && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Forte mandante — {hs.home_win_pct}% de vitórias em casa</div>
                  )}
                </div>
              </div>
            )}

            {/* Scout do Visitante */}
            {as_ && (
              <div className="card">
                <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--medium)', marginBottom: '16px' }}>
                  Scout — {awayName}
                </h3>

                {analysis?.away_form?.results && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>Forma Recente</div>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      {analysis.away_form.results.map((r: any, i: number) => (
                        <ResultBubble key={i} result={r.result} />
                      ))}
                    </div>
                  </div>
                )}

                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '10px' }}>Força do Time</div>
                  <StrengthMeter value={as_.attack_strength} label="Força de Ataque" color="var(--high)" />
                  <StrengthMeter value={as_.defense_strength} label="Solidez Defensiva" color="var(--medium)" />
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>Dados da Temporada</div>
                  {awayPoss !== null && <ScoutStat icon="" label="Posse estimada" value={`${awayPoss}%`} color="var(--medium)" />}
                  <ScoutStat icon="" label="Chutes por jogo" value={as_.avg_shots?.toFixed(1)} />
                  <ScoutStat icon="" label="Chutes no alvo" value={as_.avg_sog?.toFixed(1)} />
                  <ScoutStat icon="" label="Escanteios por jogo" value={as_.avg_corners?.toFixed(1)} />
                  <ScoutStat icon="" label="Cartões amarelos/jogo" value={as_.avg_yellow_cards?.toFixed(2)} color="var(--medium)" />
                  <ScoutStat icon="" label="Gols marcados/jogo" value={as_.avg_goals_scored?.toFixed(2)} color="var(--high)" />
                  <ScoutStat icon="" label="Gols sofridos/jogo" value={as_.avg_goals_conceded?.toFixed(2)} color="var(--medium)" />
                  <ScoutStat icon="" label="% jogos Over 2.5" value={as_.over25_pct != null ? `${as_.over25_pct}%` : null} />
                  <ScoutStat icon="" label="% Ambas Marcam" value={as_.btts_pct != null ? `${as_.btts_pct}%` : null} />
                  <ScoutStat icon="" label="% Vitória fora de casa" value={as_.away_win_pct != null ? `${as_.away_win_pct}%` : null} color="var(--medium)" />
                  <ScoutStat icon="" label="Partidas analisadas" value={as_.total_matches} />
                  {as_.fatigue_score != null && (
                    <ScoutStat icon="" label="Fadiga (0=descansado)" value={`${as_.fatigue_score}/10`} color={as_.fatigue_score > 6 ? 'var(--medium)' : as_.fatigue_score > 3 ? 'var(--medium)' : 'var(--high)'} />
                  )}
                </div>

                <div style={{ background: 'rgba(139,92,246,0.06)', borderRadius: '8px', padding: '12px', border: '1px solid rgba(139,92,246,0.15)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--medium)', fontWeight: 700, marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    Destaques do Perfil
                  </div>
                  {as_.attack_strength != null && as_.attack_strength > 1.2 && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Ataque acima da média da liga</div>
                  )}
                  {as_.defense_strength != null && as_.defense_strength < 0.85 && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Defesa sólida — sofre poucos gols</div>
                  )}
                  {as_.avg_yellow_cards != null && as_.avg_yellow_cards > 2.5 && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Time agressivo — alto volume de cartões</div>
                  )}
                  {as_.over25_pct != null && as_.over25_pct > 60 && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Jogos com muitos gols ({as_.over25_pct}% Over 2.5)</div>
                  )}
                  {as_.avg_corners != null && as_.avg_corners > 6 && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Alto volume de escanteios gerados</div>
                  )}
                  {as_.away_win_pct != null && as_.away_win_pct > 35 && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Competitivo como visitante — {as_.away_win_pct}% de vitórias fora</div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
