import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

export const maxDuration = 30;
export const dynamic = 'force-dynamic';

function getSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY!;
  return createClient(url, key);
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const homeId = parseInt(searchParams.get("home_id") ?? "0");
  const awayId = parseInt(searchParams.get("away_id") ?? "0");
  const limit  = parseInt(searchParams.get("limit") ?? "10");

  if (!homeId || !awayId) {
    return NextResponse.json({ error: "home_id e away_id são obrigatórios" }, { status: 400 });
  }

  const sb = getSupabase();

  // Busca confrontos diretos (qualquer combinação casa/fora entre os dois times)
  const { data, error } = await sb
    .from("matches")
    .select("fixture_id, date, league_name, status, home_team_id, home_team_name, away_team_id, away_team_name, goals_home, goals_away")
    .eq("status", "FT")
    .or(
      `and(home_team_id.eq.${homeId},away_team_id.eq.${awayId}),and(home_team_id.eq.${awayId},away_team_id.eq.${homeId})`
    )
    .order("date", { ascending: false })
    .limit(limit);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const matches = data || [];

  // Calcula estatísticas do H2H do ponto de vista do time "home" (primeiro parâmetro)
  let homeWins = 0, awayWins = 0, draws = 0;
  let totalGoalsHome = 0, totalGoalsAway = 0;
  let btts = 0;

  const enriched = matches.map((m) => {
    const isHome = m.home_team_id === homeId;
    const teamGoals  = isHome ? (m.goals_home ?? 0) : (m.goals_away ?? 0);
    const opponentGoals = isHome ? (m.goals_away ?? 0) : (m.goals_home ?? 0);
    const totalGoals = (m.goals_home ?? 0) + (m.goals_away ?? 0);

    totalGoalsHome += teamGoals;
    totalGoalsAway += opponentGoals;
    if ((m.goals_home ?? 0) > 0 && (m.goals_away ?? 0) > 0) btts++;

    let result: "W" | "D" | "L";
    if (teamGoals > opponentGoals)      { result = "W"; homeWins++; }
    else if (teamGoals < opponentGoals) { result = "L"; awayWins++; }
    else                                { result = "D"; draws++; }

    return {
      fixture_id:       m.fixture_id,
      date:             m.date,
      league_name:      m.league_name,
      home_team_name:   m.home_team_name,
      away_team_name:   m.away_team_name,
      goals_home:       m.goals_home,
      goals_away:       m.goals_away,
      total_goals:      totalGoals,
      was_home:         isHome,
      result_for_team1: result,
    };
  });

  const n = matches.length;

  return NextResponse.json({
    team1_id:         homeId,
    team2_id:         awayId,
    total_matches:    n,
    team1_wins:       homeWins,
    draws,
    team2_wins:       awayWins,
    team1_win_pct:    n > 0 ? Math.round((homeWins / n) * 100) : null,
    draw_pct:         n > 0 ? Math.round((draws / n) * 100) : null,
    team2_win_pct:    n > 0 ? Math.round((awayWins / n) * 100) : null,
    avg_goals_team1:  n > 0 ? Math.round((totalGoalsHome / n) * 10) / 10 : null,
    avg_goals_team2:  n > 0 ? Math.round((totalGoalsAway / n) * 10) / 10 : null,
    avg_total_goals:  n > 0 ? Math.round(((totalGoalsHome + totalGoalsAway) / n) * 10) / 10 : null,
    btts_pct:         n > 0 ? Math.round((btts / n) * 100) : null,
    over25_count:     enriched.filter(m => m.total_goals > 2).length,
    over25_pct:       n > 0 ? Math.round((enriched.filter(m => m.total_goals > 2).length / n) * 100) : null,
    matches:          enriched,
  });
}
