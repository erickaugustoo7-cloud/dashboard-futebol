// app/api/suggestions/route.ts
// Retorna sugestões do dia com análise H2H integrada
import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";


function getSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY!;
  return createClient(url, key);
}

// Mapa de tradução para seleções (Inglês ESPN -> Português)
const TEAM_TRANSLATIONS: Record<string, string> = {
  "Spain": "Espanha",
  "Cape Verde": "Cabo Verde",
  "Germany": "Alemanha",
  "England": "Inglaterra",
  "France": "França",
  "Italy": "Itália",
  "Netherlands": "Holanda",
  "Portugal": "Portugal",
  "Belgium": "Bélgica",
  "Croatia": "Croácia",
  "Switzerland": "Suíça",
  "Denmark": "Dinamarca",
  "Sweden": "Suécia",
  "Poland": "Polônia",
  "Austria": "Áustria",
  "Czech Republic": "República Tcheca",
  "Hungary": "Hungria",
  "Turkey": "Turquia",
  "Scotland": "Escócia",
  "Wales": "País de Gales",
  "Ireland": "Irlanda",
  "Serbia": "Sérvia",
  "Ukraine": "Ucrânia",
  "Greece": "Grécia",
  "Norway": "Noruega",
  "Finland": "Finlândia",
  "Romania": "Romênia",
  "Slovakia": "Eslováquia",
  "Slovenia": "Eslovênia",
  "Iceland": "Islândia",
  "Argentina": "Argentina",
  "Brazil": "Brasil",
  "Uruguay": "Uruguai",
  "Colombia": "Colômbia",
  "Chile": "Chile",
  "Peru": "Peru",
  "Ecuador": "Equador",
  "Paraguay": "Paraguai",
  "Venezuela": "Venezuela",
  "Bolivia": "Bolívia",
  "Mexico": "México",
  "United States": "Estados Unidos",
  "Canada": "Canadá",
  "Costa Rica": "Costa Rica",
  "Japan": "Japão",
  "South Korea": "Coreia do Sul",
  "Australia": "Austrália",
  "Iran": "Irã",
  "Saudi Arabia": "Arábia Saudita",
  "Morocco": "Marrocos",
  "Senegal": "Senegal",
  "Egypt": "Egito",
  "Nigeria": "Nigéria",
  "Cameroon": "Camarões",
  "Ghana": "Gana",
  "Ivory Coast": "Costa do Marfim",
  "Algeria": "Argélia",
  "South Africa": "África do Sul",
  "New Zealand": "Nova Zelândia"
};

function translateTeamName(name: string): string {
  if (!name) return "";
  return TEAM_TRANSLATIONS[name] || name;
}

function fairOdd(prob: number): number {
  return prob > 1 ? Math.round((100 / prob) * 100) / 100 : 0;
}

function poissonPmf(k: number, lambda: number): number {
  return (Math.pow(lambda, k) * Math.exp(-lambda)) / factorial(k);
}
function factorial(n: number): number {
  if (n <= 1) return 1;
  return n * factorial(n - 1);
}

function quickPoisson(homeXg: number, awayXg: number, maxGoals = 6) {
  const matrix: number[][] = [];
  let total = 0;
  for (let i = 0; i < maxGoals; i++) {
    matrix[i] = [];
    for (let j = 0; j < maxGoals; j++) {
      matrix[i][j] = poissonPmf(i, homeXg) * poissonPmf(j, awayXg);
      total += matrix[i][j];
    }
  }
  for (let i = 0; i < maxGoals; i++)
    for (let j = 0; j < maxGoals; j++)
      matrix[i][j] /= total;

  let homeWin = 0, draw = 0, awayWin = 0, over25 = 0, btts = 0;
  for (let i = 0; i < maxGoals; i++) {
    for (let j = 0; j < maxGoals; j++) {
      const p = matrix[i][j];
      if (i > j) homeWin += p;
      else if (i === j) draw += p;
      else awayWin += p;
      if (i + j > 2.5) over25 += p;
      if (i > 0 && j > 0) btts += p;
    }
  }
  return { homeWin, draw, awayWin, over25, btts };
}

async function getTeamStats(sb: any, teamId: number, leagueId: number, season: number) {
  // Primeira tentativa: stats específicos da liga/temporada
  const { data } = await sb
    .from("team_stats_cache")
    .select("*")
    .eq("team_id", teamId)
    .eq("league_id", leagueId)
    .eq("season", season)
    .limit(1);
  if (data?.[0]) return data[0];

  // Segunda tentativa: perfil global cross-liga (league_id=0, season=0)
  // Gerado pelo compute_team_stats.py usando TODOS os jogos do time
  // Garante que times internacionais (Copa do Mundo, Eurocopa) tenham ELO real
  const { data: globalData } = await sb
    .from("team_stats_cache")
    .select("*")
    .eq("team_id", teamId)
    .eq("league_id", 0)
    .eq("season", 0)
    .limit(1);
  if (globalData?.[0]) return globalData[0];

  // Última tentativa: qualquer dado do time (ELO mais recente)
  const { data: anyData } = await sb
    .from("team_stats_cache")
    .select("elo_rating, attack_strength_home, defense_strength_home, attack_strength_away, defense_strength_away")
    .eq("team_id", teamId)
    .order("season", { ascending: false })
    .limit(1);
  return anyData?.[0] ?? null;
}

async function getLeagueStats(sb: any, leagueId: number, season: number) {
  const { data } = await sb
    .from("league_stats_cache")
    .select("*")
    .eq("league_id", leagueId)
    .eq("season", season)
    .limit(1);
  return data?.[0] ?? null;
}

// ── Busca H2H dos últimos N confrontos diretos ──
async function getH2H(sb: any, homeId: number, awayId: number, limit = 8) {
  const { data } = await sb
    .from("matches")
    .select("fixture_id,date,home_team_id,away_team_id,goals_home,goals_away,league_name")
    .eq("status", "FT")
    .or(`and(home_team_id.eq.${homeId},away_team_id.eq.${awayId}),and(home_team_id.eq.${awayId},away_team_id.eq.${homeId})`)
    .order("date", { ascending: false })
    .limit(limit);
  return data ?? [];
}

// ── Busca últimos N jogos de um time ──
async function getRecentForm(sb: any, teamId: number, limit = 5) {
  const { data } = await sb
    .from("matches")
    .select("fixture_id,date,home_team_id,away_team_id,goals_home,goals_away,league_name")
    .eq("status", "FT")
    .or(`home_team_id.eq.${teamId},away_team_id.eq.${teamId}`)
    .order("date", { ascending: false })
    .limit(limit);
  return data ?? [];
}

function computeH2HSummary(h2hMatches: any[], homeId: number) {
  if (!h2hMatches.length) return null;
  let homeWins = 0, draws = 0, awayWins = 0, totalGoals = 0, btts = 0;

  const results = h2hMatches.map((m) => {
    const isHome = m.home_team_id === homeId;
    const tg = (m.goals_home ?? 0) + (m.goals_away ?? 0);
    const hg = isHome ? (m.goals_home ?? 0) : (m.goals_away ?? 0);
    const ag = isHome ? (m.goals_away ?? 0) : (m.goals_home ?? 0);
    totalGoals += tg;
    if ((m.goals_home ?? 0) > 0 && (m.goals_away ?? 0) > 0) btts++;
    let result: "W" | "D" | "L";
    if (hg > ag) { result = "W"; homeWins++; }
    else if (hg < ag) { result = "L"; awayWins++; }
    else { result = "D"; draws++; }
    return { date: m.date?.substring(0, 10), goals_home: m.goals_home, goals_away: m.goals_away, result };
  });

  const n = h2hMatches.length;
  const avgGoals = Math.round((totalGoals / n) * 10) / 10;

  return {
    total: n,
    team1_wins: homeWins,
    draws,
    team2_wins: awayWins,
    team1_win_pct: Math.round((homeWins / n) * 100),
    team2_win_pct: Math.round((awayWins / n) * 100),
    draw_pct: Math.round((draws / n) * 100),
    avg_goals: avgGoals,
    btts_pct: Math.round((btts / n) * 100),
    over25_pct: Math.round((h2hMatches.filter(m => ((m.goals_home ?? 0) + (m.goals_away ?? 0)) > 2).length / n) * 100),
    last5: results.slice(0, 5),
  };
}

function computeFormSummary(matches: any[], teamId: number) {
  if (!matches.length) return null;
  let points = 0;
  let goalsFor = 0, goalsAgainst = 0;

  const results = matches.map((m) => {
    const isHome = m.home_team_id === teamId;
    const gf = isHome ? (m.goals_home ?? 0) : (m.goals_away ?? 0);
    const ga = isHome ? (m.goals_away ?? 0) : (m.goals_home ?? 0);
    goalsFor += gf;
    goalsAgainst += ga;
    let result: "W" | "D" | "L";
    if (gf > ga) { result = "W"; points += 3; }
    else if (gf < ga) { result = "L"; }
    else { result = "D"; points += 1; }
    return { result, gf, ga, date: m.date?.substring(0, 10) };
  });

  const n = matches.length;
  return {
    results,
    points,
    avg_goals_for:     Math.round((goalsFor / n) * 10) / 10,
    avg_goals_against: Math.round((goalsAgainst / n) * 10) / 10,
    clean_sheets:      matches.filter(m => {
      const isHome = m.home_team_id === teamId;
      return isHome ? (m.goals_away ?? 0) === 0 : (m.goals_home ?? 0) === 0;
    }).length,
  };
}

function generateInsight(
  homeName: string, awayName: string,
  h2h: any, homeForm: any, awayForm: any,
  homeXg: number, awayXg: number,
  homeWinP: number, drawP: number, awayWinP: number,
  over25P: number, bttsP: number
): string[] {
  const insights: string[] = [];

  // H2H insights
  if (h2h && h2h.total >= 3) {
    if (h2h.team1_win_pct >= 60) {
      insights.push(`Domínio histórico de ${homeName}: venceu ${h2h.team1_wins} dos últimos ${h2h.total} confrontos diretos (${h2h.team1_win_pct}%).`);
    } else if (h2h.team2_wins / h2h.total >= 0.6) {
      insights.push(`Histórico favorece ${awayName}: ${h2h.team2_wins} vitórias nos últimos ${h2h.total} H2H.`);
    } else {
      insights.push(`Confrontos equilibrados: ${h2h.team1_wins}V ${h2h.draws}E ${h2h.team2_wins}D nos últimos ${h2h.total} jogos.`);
    }
    if (h2h.avg_goals >= 3.0) {
      insights.push(`Jogos com muitos gols entre esses times: média de ${h2h.avg_goals} gols por jogo no H2H.`);
    } else if (h2h.avg_goals <= 1.5) {
      insights.push(`Confrontos tendem a ser fechados: média de apenas ${h2h.avg_goals} gols por jogo no H2H.`);
    }
    if (h2h.btts_pct >= 65) {
      insights.push(`Ambas as equipes marcaram em ${h2h.btts_pct}% dos últimos confrontos diretos.`);
    }
  }

  // Forma recente
  if (homeForm && awayForm) {
    const homePPG = homeForm.points / Math.max(homeForm.results.length, 1);
    const awayPPG = awayForm.points / Math.max(awayForm.results.length, 1);
    if (homePPG >= 2.4) {
      insights.push(`${homeName} em grande fase: ${homeForm.points} pontos nos últimos ${homeForm.results.length} jogos.`);
    }
    if (awayPPG >= 2.4) {
      insights.push(`${awayName} também em excelente forma: ${awayForm.points} pts nos últimos ${awayForm.results.length} jogos.`);
    }
    if (homeForm.clean_sheets >= 3) {
      insights.push(`${homeName} com defesa sólida: ${homeForm.clean_sheets} clean sheets recentes.`);
    }
    if (awayForm.clean_sheets >= 3) {
      insights.push(`${awayName} com defesa sólida: ${awayForm.clean_sheets} clean sheets recentes.`);
    }
  }

  // Probabilidades
  const dominant = homeWinP > awayWinP ? homeName : awayName;
  const dominantP = Math.max(homeWinP, awayWinP);
  const underdog = homeWinP > awayWinP ? awayName : homeName;
  
  if (dominantP >= 75) {
    insights.push(`Alerta de Favoritismo MÁXIMO: ${dominant} tem chance esmagadora de vitória (${dominantP.toFixed(0)}%). Diferença técnica brutal no confronto.`);
  } else if (dominantP >= 55) {
    insights.push(`Modelo favorece claramente ${dominant} com ${dominantP.toFixed(0)}% de probabilidade de vitória.`);
  }
  
  if (over25P >= 65) {
    insights.push(`Alta probabilidade de jogo movimentado: ${over25P.toFixed(0)}% de chance de Over 2.5 gols.`);
  } else if (over25P <= 35) {
    insights.push(`Jogo tende a ser muito fechado: apenas ${over25P.toFixed(0)}% de chance de Over 2.5 gols.`);
  }
  if (bttsP >= 65) {
    insights.push(`Ambas equipes tendem a marcar: ${bttsP.toFixed(0)}% de chance de BTTS (Ambas Marcam).`);
  } else if (bttsP <= 35) {
    insights.push(`Chance alta de pelo menos uma equipe não sofrer gols (BTTS Não: ${(100 - bttsP).toFixed(0)}%).`);
  }

  // Preenche até ter no mínimo 5 insights (fallbacks adicionais estatísticos)
  if (insights.length < 5) {
    if (dominantP > 40 && dominantP < 55) {
      insights.push(`Jogo levemente inclinado para ${dominant} (${dominantP.toFixed(0)}%), mas ${underdog} não pode ser descartado.`);
    } else if (dominantP <= 40) {
      insights.push(`Confronto muito parelho, com chances reais de empate (${drawP.toFixed(0)}%).`);
    }
  }
  
  if (insights.length < 5) {
    if (homeXg > awayXg * 1.5) {
      insights.push(`As Chances de Gol projetam um ataque muito superior para ${homeName} neste embate.`);
    } else if (awayXg > homeXg * 1.5) {
      insights.push(`Força de criação ofensiva pesa a favor do visitante ${awayName}.`);
    } else {
      insights.push(`As Chances de Gol de ambos os times estão parelhas, sugerindo jogo truncado no meio campo.`);
    }
  }

  if (insights.length < 5) {
    insights.push(`A estatística preditiva considera um jogo de ${over25P > 50 ? 'mais' : 'menos'} de 2.5 gols em um cenário normal.`);
  }
  
  if (insights.length < 5) {
    insights.push(`Análise de defesas aponta ${homeWinP > 50 ? 'maior resistência defensiva para o mandante.' : 'que a defesa visitante é o pilar deste confronto.'}`);
  }

  if (insights.length < 5) {
    insights.push(`Insight bônus: Odd justa projetada para Vitória de ${dominant} é de ${(100 / dominantP).toFixed(2)}.`);
  }

  // Garante que retorne pelo menos 5, sem cortar as que já existiam se forem maiores
  return insights.length > 5 ? insights : insights;
}

async function analyzeMatch(sb: any, match: any) {
  const { home_team_id, away_team_id, league_id, season, fixture_id } = match;

  const [homeStats, awayStats, leagueStats, h2hMatches, homeRecent, awayRecent, dbPredResult] = await Promise.all([
    getTeamStats(sb, home_team_id, league_id, season),
    getTeamStats(sb, away_team_id, league_id, season),
    getLeagueStats(sb, league_id, season),
    getH2H(sb, home_team_id, away_team_id, 8),
    getRecentForm(sb, home_team_id, 5),
    getRecentForm(sb, away_team_id, 5),
    sb.from("predictions").select("*").eq("fixture_id", fixture_id).limit(1).single()
  ]);

  const dbPred = dbPredResult?.data ?? null;

  const avgH = leagueStats?.avg_home_goals ?? 1.35;
  const avgA = leagueStats?.avg_away_goals ?? 1.10;

  const atkH = homeStats?.attack_strength_home ?? 1.0;
  const defH = homeStats?.defense_strength_home ?? 1.0;
  const atkA = awayStats?.attack_strength_away ?? 1.0;
  const defA = awayStats?.defense_strength_away ?? 1.0;

  const eloH = homeStats?.elo_rating ?? 1500;
  const eloA = awayStats?.elo_rating ?? 1500;

  // ─── xG com ELO como ancora principal ─────────────────────────────────
  // Passo 1: probabilidade de vitória do mandante pelo ELO clássico
  //          (incluindo vantagem de 100 pts para o mandante)
  const eloHomeWinProb = 1 / (1 + Math.pow(10, (eloA - eloH - 100) / 400));

  // Passo 2: razão xG derivada do ELO — homeXg/awayXg ≈ sqrt(winProb/losProb)
  //          Isso garante que se P(home)=0.91, xG home >> xG away sempre.
  const xgRatioElo = Math.sqrt(eloHomeWinProb / Math.max(0.01, 1 - eloHomeWinProb));

  // Passo 3: razão bruta pelas forças de ataque/defesa (contexto estatístico)
  const rawHomeXg = atkH * (defA > 0 ? defA : 1.0) * avgH;
  const rawAwayXg = atkA * (defH > 0 ? defH : 1.0) * avgA;
  const xgRatioStats = rawHomeXg / Math.max(0.01, rawAwayXg);

  // Passo 4: mistura ponderada (70% ELO, 30% stats)
  //          O ELO domina, mas a estatística afia o resultado
  const blendedRatio = xgRatioElo * 0.7 + xgRatioStats * 0.3;

  // Passo 5: calcula xG mantendo a soma próxima da média histórica da liga
  const totalAvgXg = avgH + avgA;  // ex: 1.35 + 1.10 = 2.45
  let homeXg = Math.max(0.3, Math.min(5.0, totalAvgXg * blendedRatio / (1 + blendedRatio)));
  let awayXg = Math.max(0.3, Math.min(5.0, totalAvgXg / (1 + blendedRatio)));
  // ──────────────────────────────────────────────────────────────────────

  // H2H adjustment
  const h2hSummary = computeH2HSummary(h2hMatches, home_team_id);
  if (h2hSummary && h2hSummary.total >= 3) {
    // Ajusta xG levemente baseado no histórico H2H
    const h2hBias = (h2hSummary.team1_win_pct - 50) / 100 * 0.15;
    homeXg = Math.max(0.3, homeXg * (1 + h2hBias));
    awayXg = Math.max(0.3, awayXg * (1 - h2hBias));

    // Ajusta médias de gols pelo histórico H2H
    if (h2hSummary.avg_goals > 0) {
      const h2hGoalFactor = (h2hSummary.avg_goals / (avgH + avgA)) * 0.2 + 0.8;
      homeXg = Math.max(0.3, homeXg * h2hGoalFactor);
      awayXg = Math.max(0.3, awayXg * h2hGoalFactor);
    }
  }

  const probs = quickPoisson(homeXg, awayXg);

  // Form adjustment
  const homeFormSummary = computeFormSummary(homeRecent, home_team_id);
  const awayFormSummary = computeFormSummary(awayRecent, away_team_id);

  let formBonus = 0;
  if (homeFormSummary && awayFormSummary) {
    const hPPG = homeFormSummary.points / Math.max(homeFormSummary.results.length, 1) / 3;
    const aPPG = awayFormSummary.points / Math.max(awayFormSummary.results.length, 1) / 3;
    formBonus = (hPPG - aPPG) * 0.08;
  }

  const adjHomeWin = Math.max(0.05, probs.homeWin + formBonus);
  const adjAwayWin = Math.max(0.05, probs.awayWin - formBonus);
  const adjDraw    = Math.max(0.05, probs.draw);
  const sumAdj     = adjHomeWin + adjDraw + adjAwayWin;

  let homeWinP = (adjHomeWin / sumAdj) * 100;
  let drawP    = (adjDraw / sumAdj) * 100;
  let awayWinP = (adjAwayWin / sumAdj) * 100;
  let over25P  = probs.over25 * 100;
  let bttsP    = probs.btts * 100;

  // Gera insights textuais (fallback)
  let insights = generateInsight(
    translateTeamName(match.home_team_name), translateTeamName(match.away_team_name),
    h2hSummary, homeFormSummary, awayFormSummary,
    homeXg, awayXg,
    homeWinP, drawP, awayWinP,
    over25P, bttsP
  );

  // NOTA: A tabela 'predictions' (dbPred) foi removida como fonte de override.
  // O modelo agora usa diretamente ELO Global + Poisson + Forma, que é mais preciso.

  // Escolhe melhor sugestão

  const candidates = [
    { market: "over25",   label: "Over 2.5 Gols",             prob: over25P,        contextPct: leagueStats?.over25_pct ?? 50 },
    { market: "under25",  label: "Under 2.5 Gols",            prob: 100 - over25P,  contextPct: 100 - (leagueStats?.over25_pct ?? 50) },
    { market: "btts_yes", label: "Ambos Marcam - Sim",        prob: bttsP,          contextPct: leagueStats?.btts_pct ?? 50 },
    { market: "btts_no",  label: "Ambos Marcam - Não",        prob: 100 - bttsP,    contextPct: 100 - (leagueStats?.btts_pct ?? 50) },
    { market: "home_win", label: "Vitória " + match.home_team_name, prob: homeWinP, contextPct: leagueStats?.home_win_pct ?? 45 },
    { market: "draw",     label: "Empate",                    prob: drawP,          contextPct: leagueStats?.draw_pct ?? 26 },
    { market: "away_win", label: "Vitória " + match.away_team_name, prob: awayWinP, contextPct: leagueStats?.away_win_pct ?? 30 },
    { market: "1x",       label: "Mandante ou Empate (1X)",   prob: homeWinP + drawP,  contextPct: (leagueStats?.home_win_pct ?? 45) + (leagueStats?.draw_pct ?? 26) },
    { market: "x2",       label: "Visitante ou Empate (X2)",  prob: awayWinP + drawP, contextPct: (leagueStats?.away_win_pct ?? 30) + (leagueStats?.draw_pct ?? 26) },
    { market: "12",       label: "Mandante ou Visitante (12)",prob: homeWinP + awayWinP, contextPct: (leagueStats?.home_win_pct ?? 45) + (leagueStats?.away_win_pct ?? 30) },
  ].filter(c => c.prob > 50);

  const scoredCandidates = candidates.map(c => {
    // Value edge: quão melhor é a probabilidade do modelo comparada à média da liga
    const edge = c.prob - c.contextPct;
    const edgeBonus = edge > 0 ? (edge / 100) * 15 : 0; // Até 15 pts de bônus

    // Bônus para mercados mais difíceis (vitória seca ou empate) para evitar que double chance domine
    const isDirect = c.market === "home_win" || c.market === "away_win" || c.market === "draw";
    const directBonus = isDirect ? 8 : 0;

    // Penalidade leve para double chance, já que naturalmente tem probabilidade muito alta
    const isDoubleChance = c.market === "1x" || c.market === "x2" || c.market === "12";
    const doubleChancePenalty = isDoubleChance ? 10 : 0;

    // Bônus extra se H2H confirma a tendência
    let h2hBonus = 0;
    if (h2hSummary && h2hSummary.total >= 3) {
      if (c.market === "home_win" && h2hSummary.team1_win_pct >= 60) h2hBonus = 5;
      if (c.market === "away_win" && h2hSummary.team2_win_pct >= 60) h2hBonus = 5;
      if (c.market === "1x" && (h2hSummary.team1_win_pct + h2hSummary.draw_pct) >= 70) h2hBonus = 3;
      if (c.market === "x2" && (h2hSummary.team2_win_pct + h2hSummary.draw_pct) >= 70) h2hBonus = 3;
      if (c.market === "over25" && h2hSummary.over25_pct >= 60) h2hBonus = 5;
      if (c.market === "btts_yes" && h2hSummary.btts_pct >= 60) h2hBonus = 5;
    }
    const confidence = Math.min(94, c.prob + edgeBonus + directBonus + h2hBonus - doubleChancePenalty);
    return { ...c, confidence, fairOdd: fairOdd(c.prob) };
  }).sort((a, b) => b.confidence - a.confidence);

  const best = scoredCandidates[0];
  if (!best) return null;

  return {
    fixture_id,
    league_id,
    league_name:   match.league_name,
    date:          match.date,
    status:        match.status,
    goals_home:    match.goals_home,
    goals_away:    match.goals_away,
    home_team:     translateTeamName(match.home_team_name),
    away_team:     translateTeamName(match.away_team_name),
    home_team_id:  match.home_team_id,
    away_team_id:  match.away_team_id,
    home_xg:       Math.round(homeXg * 100) / 100,
    away_xg:       Math.round(awayXg * 100) / 100,
    home_win_prob: Math.round(homeWinP * 10) / 10,
    draw_prob:     Math.round(drawP * 10) / 10,
    away_win_prob: Math.round(awayWinP * 10) / 10,
    over25_prob:   Math.round(over25P * 10) / 10,
    btts_prob:     Math.round(bttsP * 10) / 10,
    home_elo:      eloH,
    away_elo:      eloA,
    home_form:     homeFormSummary,
    away_form:     awayFormSummary,
    h2h:           h2hSummary,
    insights,
    // ─── Scout stats de cada time ────────────────────────────────────────
    home_scout: homeStats ? {
      avg_shots:         homeStats.avg_shots          ?? null,
      avg_sog:           homeStats.avg_sog             ?? null,
      avg_corners:       homeStats.avg_corners         ?? null,
      avg_yellow_cards:  homeStats.avg_yellow_cards    ?? null,
      avg_goals_scored:  homeStats.avg_goals_scored    ?? null,
      avg_goals_conceded:homeStats.avg_goals_conceded  ?? null,
      over25_pct:        homeStats.over25_pct          ?? null,
      btts_pct:          homeStats.btts_pct            ?? null,
      home_win_pct:      homeStats.home_win_pct        ?? null,
      away_win_pct:      homeStats.away_win_pct        ?? null,
      attack_strength:   homeStats.attack_strength_home ?? null,
      defense_strength:  homeStats.defense_strength_home ?? null,
      total_matches:     homeStats.total_matches       ?? null,
      fatigue_score:     homeStats.fatigue_score       ?? null,
    } : null,
    away_scout: awayStats ? {
      avg_shots:         awayStats.avg_shots           ?? null,
      avg_sog:           awayStats.avg_sog             ?? null,
      avg_corners:       awayStats.avg_corners         ?? null,
      avg_yellow_cards:  awayStats.avg_yellow_cards    ?? null,
      avg_goals_scored:  awayStats.avg_goals_scored    ?? null,
      avg_goals_conceded:awayStats.avg_goals_conceded  ?? null,
      over25_pct:        awayStats.over25_pct          ?? null,
      btts_pct:          awayStats.btts_pct            ?? null,
      home_win_pct:      awayStats.home_win_pct        ?? null,
      away_win_pct:      awayStats.away_win_pct        ?? null,
      attack_strength:   awayStats.attack_strength_away ?? null,
      defense_strength:  awayStats.defense_strength_away ?? null,
      total_matches:     awayStats.total_matches       ?? null,
      fatigue_score:     awayStats.fatigue_score       ?? null,
    } : null,
    // ─────────────────────────────────────────────────────────────────────
    suggestion: {
      market:           best.market,
      label:            best.label,
      probability:      Math.round(best.prob * 10) / 10,
      confidence:       Math.round(best.confidence * 10) / 10,
      confidence_level: best.confidence >= 65 ? "high" : best.confidence >= 55 ? "medium" : "low",
      fair_odd:         best.fairOdd,
    },
    all_suggestions: scoredCandidates.slice(0, 5).map(c => ({
      market:      c.market,
      label:       c.label,
      probability: Math.round(c.prob * 10) / 10,
      confidence:  Math.round(c.confidence * 10) / 10,
      fair_odd:    c.fairOdd,
    })),
  };
}


export const maxDuration = 30;
export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const dateParam    = searchParams.get("date") ?? new Date().toISOString().split("T")[0];
  const leaguesParam = searchParams.get("leagues");
  const leagues = leaguesParam ? leaguesParam.split(",").map(Number) : null;

  const fixtureIdParam = searchParams.get("fixture_id");

  const sb = getSupabase();

  let q = sb
    .from("matches")
    .select("fixture_id,league_id,league_name,season,date,status,home_team_id,home_team_name,away_team_id,away_team_name,goals_home,goals_away");

  if (fixtureIdParam) {
    q = q.eq("fixture_id", fixtureIdParam);
  } else {
    const startDt = new Date(`${dateParam}T00:00:00-03:00`).toISOString();
    const endDt   = new Date(`${dateParam}T23:59:59-03:00`).toISOString();
    q = q.in("status", ["NS", "FT"]).gte("date", startDt).lte("date", endDt).order("date");
    if (leagues?.length) q = q.in("league_id", leagues);
  }

  const { data: matches, error } = await q;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!matches?.length) return NextResponse.json({ date: dateParam, simples: [], combinadas: [] });

  // Analisa em lotes de 4
  const analyzed: any[] = [];
  for (let i = 0; i < matches.length; i += 4) {
    const batch = matches.slice(i, i + 4);
    const results = await Promise.all(batch.map(m => analyzeMatch(sb, m).catch((e) => {
      console.error("Error analyzing match", m.fixture_id, e);
      return null;
    })));
    analyzed.push(...results.filter(Boolean));
  }

  analyzed.sort((a, b) => (b.suggestion?.confidence ?? 0) - (a.suggestion?.confidence ?? 0));

  // Combinadas
  const highConf = analyzed.filter(a => (a.suggestion?.confidence ?? 0) >= 55);
  const combinadas: any[] = [];

  for (let n = 2; n <= Math.min(5, highConf.length); n++) {
    const selected: any[] = [];
    const usedTeams = new Set<number>();

    for (const item of highConf) {
      if (usedTeams.has(item.home_team_id) || usedTeams.has(item.away_team_id)) continue;
      selected.push(item);
      usedTeams.add(item.home_team_id);
      usedTeams.add(item.away_team_id);
      if (selected.length === n) break;
    }

    if (selected.length < n) continue;

    let combinedProb = 1.0;
    let combinedOdd  = 1.0;
    const legs = selected.map(item => {
      const sg = item.suggestion;
      combinedProb *= sg.probability / 100;
      combinedOdd  *= sg.fair_odd;
      return {
        fixture_id:  item.fixture_id,
        home_team:   item.home_team,
        away_team:   item.away_team,
        league:      item.league_name,
        date:        item.date,
        market:      sg.market,
        label:       sg.label,
        probability: sg.probability,
        confidence:  sg.confidence,
        fair_odd:    sg.fair_odd,
      };
    });

    const ev = combinedProb * combinedOdd - 1;
    combinadas.push({
      type:                `${n}-fold`,
      label:               n === 2 ? "Dupla" : n === 3 ? "Tripla" : `${n}x`,
      legs,
      combined_probability: Math.round(combinedProb * 10000) / 100,
      combined_odd:         Math.round(combinedOdd * 100) / 100,
      expected_value:       Math.round(ev * 10000) / 100,
      ev_positive:          ev > 0,
      avg_confidence:       Math.round(legs.reduce((s, l) => s + l.confidence, 0) / legs.length * 10) / 10,
    });
  }

  return NextResponse.json({
    date:          dateParam,
    total_matches: matches.length,
    analyzed:      analyzed.length,
    simples:       analyzed,
    combinadas,
  });
}
