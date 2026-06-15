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
  label: string; homeVal: number; awayVal: number; format?: (v: number) => string; higherIsBetter?: boolean;
}) {
  const total = homeVal + awayVal || 1;
  const homePct = (homeVal / total) * 100;
  const awayPct = (awayVal / total) * 100;
  const homeLeads = higherIsBetter ? homeVal >= awayVal : homeVal <= awayVal;
  return (
    <div style={{ marginBottom: '14px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px', fontSize: '13px' }}>
        <span style={{ color: homeLeads ? 'var(--accent-bright)' : 'var(--text-muted)', fontWeight: homeLeads ? 700 : 400 }}>{format(homeVal)}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</span>
        <span style={{ color: !homeLeads ? 'var(--medium)' : 'var(--text-muted)', fontWeight: !homeLeads ? 700 : 400 }}>{format(awayVal)}</span>
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

          {/* AI Insights */}
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
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {analysis.all_suggestions.map((s: any, i: number) => (
                      <div key={i} style={{ fontSize: '12px', padding: '5px 10px', borderRadius: '20px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
                        {s.label} · {s.probability}% · odd {s.fair_odd?.toFixed(2)}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
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
              {homePoss !== null && awayPoss !== null && (
                <StatBar
                  label="Posse de Bola %"
                  homeVal={homePoss}
                  awayVal={awayPoss}
                  format={v => `${v}%`}
                />
              )}

              {hs?.avg_shots != null && as_?.avg_shots != null && (
                <StatBar label="Chutes/jogo" homeVal={Number(hs.avg_shots.toFixed(1))} awayVal={Number(as_.avg_shots.toFixed(1))} format={v => v.toString()} />
              )}
              {hs?.avg_sog != null && as_?.avg_sog != null && (
                <StatBar label="Chutes no alvo" homeVal={Number(hs.avg_sog.toFixed(1))} awayVal={Number(as_.avg_sog.toFixed(1))} format={v => v.toString()} />
              )}
              {hs?.avg_corners != null && as_?.avg_corners != null && (
                <StatBar label="Escanteios/jogo" homeVal={Number(hs.avg_corners.toFixed(1))} awayVal={Number(as_.avg_corners.toFixed(1))} format={v => v.toString()} />
              )}
              {hs?.avg_yellow_cards != null && as_?.avg_yellow_cards != null && (
                <StatBar
                  label="Cartões amarelos"
                  homeVal={Number(hs.avg_yellow_cards.toFixed(2))}
                  awayVal={Number(as_.avg_yellow_cards.toFixed(2))}
                  format={v => v.toString()}
                  higherIsBetter={false}
                />
              )}
              {hs?.avg_goals_scored != null && as_?.avg_goals_scored != null && (
                <StatBar label="Gols marcados/jogo" homeVal={Number(hs.avg_goals_scored.toFixed(2))} awayVal={Number(as_.avg_goals_scored.toFixed(2))} format={v => v.toString()} />
              )}
              {hs?.avg_goals_conceded != null && as_?.avg_goals_conceded != null && (
                <StatBar
                  label="Gols sofridos/jogo"
                  homeVal={Number(hs.avg_goals_conceded.toFixed(2))}
                  awayVal={Number(as_.avg_goals_conceded.toFixed(2))}
                  format={v => v.toString()}
                  higherIsBetter={false}
                />
              )}
              {hs?.over25_pct != null && as_?.over25_pct != null && (
                <StatBar label="Over 2.5 (histórico %)" homeVal={Number(hs.over25_pct)} awayVal={Number(as_.over25_pct)} format={v => `${v}%`} />
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
