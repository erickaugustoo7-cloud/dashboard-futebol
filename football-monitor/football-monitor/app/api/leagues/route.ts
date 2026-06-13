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
  const sb = getSupabase();

  // Retorna ligas dos últimos e próximos jogos (evita bater o limite de 1000 apenas em 1 liga por ordem alfabética)
  const { data, error } = await sb
    .from("matches")
    .select("league_id, league_name")
    .order("date", { ascending: false })
    .limit(3000);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  // Deduplica por league_id
  const seen = new Set<number>();
  const leagues: { league_id: number; league_name: string }[] = [];
  for (const row of data || []) {
    if (row.league_id && !seen.has(row.league_id)) {
      seen.add(row.league_id);
      leagues.push({ league_id: row.league_id, league_name: row.league_name });
    }
  }

  leagues.sort((a, b) => a.league_name.localeCompare(b.league_name));

  return NextResponse.json(leagues);
}
