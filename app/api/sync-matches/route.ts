// app/api/sync-matches/route.ts
import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

// ── Mapeamento de League IDs da API-Sports para ESPN Slugs ──
const LEAGUE_MAPPING: Record<number, string> = {
  71: "bra.1",                  // Brasileirão Série A
  39: "eng.1",                  // Premier League
  140: "esp.1",                 // La Liga
  135: "ita.1",                 // Serie A (ITA)
  78: "ger.1",                  // Bundesliga
  61: "fra.1",                  // Ligue 1
  2: "uefa.champions",          // UEFA Champions League
  3: "uefa.europa",             // UEFA Europa League
  13: "conmebol.libertadores",  // Copa Libertadores
  11: "conmebol.sudamericana",  // Copa Sudamericana
  73: "bra.copa_do_brazil",     // Copa do Brasil
  1: "fifa.world",              // Copa do Mundo
  9: "conmebol.america",        // Copa America
  4: "uefa.euro"                // Eurocopa
};

const DEFAULT_LEAGUES = [71, 39, 140, 135, 78, 61, 2, 3, 13, 11, 73, 1, 9, 4];

function getSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY;
  if (!url || !key) {
    throw new Error("NEXT_PUBLIC_SUPABASE_URL and SUPABASE_ANON_KEY/SERVICE_ROLE_KEY are not configured.");
  }
  return createClient(url, key);
}

async function fetchScoreboardDay(leagueSlug: string, dateStr: string): Promise<any[]> {
  const formattedDate = dateStr.replace(/-/g, "");
  const url = `https://site.api.espn.com/apis/site/v2/sports/soccer/${leagueSlug}/scoreboard?dates=${formattedDate}&limit=100`;
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    return data.events ?? [];
  } catch (err) {
    console.error(`[sync-matches] Erro no scoreboard para ${leagueSlug} em ${dateStr}:`, err);
    return [];
  }
}

async function fetchGameSummary(leagueSlug: string, eventId: string): Promise<any | null> {
  const url = `https://site.api.espn.com/apis/site/v2/sports/soccer/${leagueSlug}/summary?event=${eventId}`;
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error(`[sync-matches] Erro ao buscar resumo da partida ${eventId}:`, err);
    return null;
  }
}

function getStatValue(statsList: any[], statName: string): number | null {
  const stat = statsList.find((s: any) => s.name === statName);
  if (!stat || stat.displayValue === undefined) return null;
  const valStr = String(stat.displayValue).replace(/%/g, "").trim();
  const valNum = Number(valStr);
  return isNaN(valNum) ? null : valNum;
}

function parseEspnEvent(event: any, summaryData: any | null, leagueId: number, leagueSlug: string): any {
  const competitions = event.competitions ?? [];
  if (!competitions.length) return null;
  const comp = competitions[0];
  
  const dateIso = comp.date ?? "";
  let timestamp = 0;
  if (dateIso) {
    timestamp = Math.floor(new Date(dateIso).getTime() / 1000);
  }
  
  const statusInfo = comp.status ?? {};
  const statusType = statusInfo.type ?? {};
  const completed = statusType.completed ?? false;
  
  let status = statusType.shortDetail ?? "NS";
  if (status === "FT" || completed) {
    status = "FT";
  } else if (["TBD", "Scheduled", "Pre"].includes(status)) {
    status = "NS";
  }
  
  const competitors = comp.competitors ?? [];
  if (competitors.length < 2) return null;
  const home = competitors.find((c: any) => c.homeAway === "home");
  const away = competitors.find((c: any) => c.homeAway === "away");
  if (!home || !away) return null;
  
  const homeTeam = home.team ?? {};
  const awayTeam = away.team ?? {};
  
  let goalsHome: number | null = null;
  let goalsAway: number | null = null;
  let scoreFtHome: number | null = null;
  let scoreFtAway: number | null = null;
  
  if (completed || home.score !== undefined) {
    goalsHome = parseInt(home.score, 10);
    goalsAway = parseInt(away.score, 10);
    scoreFtHome = goalsHome;
    scoreFtAway = goalsAway;
  }
  
  let homeStats = home.statistics ?? [];
  let awayStats = away.statistics ?? [];
  
  if (summaryData?.boxscore?.teams) {
    const teamsBox = summaryData.boxscore.teams;
    for (const t of teamsBox) {
      if (String(t.team?.id) === String(homeTeam.id)) {
        homeStats = t.statistics ?? [];
      } else if (String(t.team?.id) === String(awayTeam.id)) {
        awayStats = t.statistics ?? [];
      }
    }
  }
  
  const seasonYear = parseInt(event.season?.year ?? new Date().getFullYear().toString(), 10);
  
  return {
    fixture_id: parseInt(event.id, 10),
    league_id: leagueId,
    league_name: event.season?.slug?.toUpperCase() ?? leagueSlug.toUpperCase(),
    season: seasonYear,
    date: dateIso,
    timestamp,
    status,
    home_team_id: parseInt(homeTeam.id, 10),
    home_team_name: homeTeam.displayName ?? "Casa",
    away_team_id: parseInt(awayTeam.id, 10),
    away_team_name: awayTeam.displayName ?? "Fora",
    goals_home: isNaN(goalsHome!) ? null : goalsHome,
    goals_away: isNaN(goalsAway!) ? null : goalsAway,
    score_ht_home: null,
    score_ht_away: null,
    score_ft_home: isNaN(scoreFtHome!) ? null : scoreFtHome,
    score_ft_away: isNaN(scoreFtAway!) ? null : scoreFtAway,
    
    // Stats
    home_shots: getStatValue(homeStats, "totalShots"),
    away_shots: getStatValue(awayStats, "totalShots"),
    home_sog: getStatValue(homeStats, "shotsOnTarget"),
    away_sog: getStatValue(awayStats, "shotsOnTarget"),
    home_possession: getStatValue(homeStats, "possessionPct"),
    away_possession: getStatValue(awayStats, "possessionPct"),
    home_corners: getStatValue(homeStats, "wonCorners"),
    away_corners: getStatValue(awayStats, "wonCorners"),
    home_yellow_cards: getStatValue(homeStats, "yellowCards"),
    away_yellow_cards: getStatValue(awayStats, "yellowCards"),
    home_red_cards: getStatValue(homeStats, "redCards"),
    away_red_cards: getStatValue(awayStats, "redCards"),
    home_fouls: getStatValue(homeStats, "foulsCommitted"),
    away_fouls: getStatValue(awayStats, "foulsCommitted"),
    home_offsides: getStatValue(homeStats, "offsides"),
    away_offsides: getStatValue(awayStats, "offsides"),
    is_backfilled: false,
    updated_at: new Date().toISOString(),
    last_synced_at: new Date().toISOString()
  };
}

export const maxDuration = 60;

export async function GET(req: NextRequest) {
  const isVercelCron = req.headers.get("x-vercel-cron") === "1";
  const authHeader = req.headers.get("authorization");
  const isInternalCall = authHeader === `Bearer ${process.env.CRON_SECRET}`;

  if (!isVercelCron && !isInternalCall) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const { searchParams } = new URL(req.url);
    const leaguesParam = searchParams.get("leagues");
    const leagues = leaguesParam ? leaguesParam.split(",").map(l => parseInt(l.trim(), 10)) : DEFAULT_LEAGUES;
    
    const today = new Date();
    const datesToSync: string[] = [];
    
    // Sincronizar dos últimos 3 dias até os próximos 3 dias
    for (let i = -3; i <= 3; i++) {
      const d = new Date(today);
      d.setDate(today.getDate() + i);
      datesToSync.push(d.toISOString().split("T")[0]);
    }

    console.log(`[sync-matches] Ligas: ${leagues.join(", ")} | Datas: ${datesToSync.join(", ")}`);

    const supabase = getSupabase();
    let totalSynced = 0;
    const errors: string[] = [];

    for (const leagueId of leagues) {
      const leagueSlug = LEAGUE_MAPPING[leagueId];
      if (!leagueSlug) continue;

      const leagueRecords: any[] = [];

      for (const day of datesToSync) {
        const events = await fetchScoreboardDay(leagueSlug, day);
        if (!events.length) continue;

        for (const event of events) {
          const comp = event.competitions?.[0] ?? {};
          const completed = comp.status?.type?.completed ?? false;
          
          let summaryData = null;
          if (completed && event.id) {
            summaryData = await fetchGameSummary(leagueSlug, event.id);
            // Delay curto para evitar sobrecarga de requisições paralelas
            await new Promise((r) => setTimeout(r, 100));
          }

          const parsed = parseEspnEvent(event, summaryData, leagueId, leagueSlug);
          if (parsed) {
            leagueRecords.push(parsed);
          }
        }
      }

      if (leagueRecords.length > 0) {
        const { error } = await supabase.from("matches").upsert(leagueRecords);
        if (error) {
          console.error(`[sync-matches] Erro ao salvar dados no Supabase para ${leagueSlug}:`, error);
          errors.push(`${leagueSlug}: ${error.message}`);
        } else {
          totalSynced += leagueRecords.length;
        }
      }
      
      // Delay entre ligas
      await new Promise((r) => setTimeout(r, 1000));
    }

    const summary = {
      message: "Football Sync completed.",
      synced: totalSynced,
      errors: errors.length ? errors : undefined
    };

    console.log("[sync-matches] Resumo final:", JSON.stringify(summary));
    return NextResponse.json(summary);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("[sync-matches] FATAL ERROR:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

