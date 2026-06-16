import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

export const maxDuration = 60;
export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const dateParam = searchParams.get("date") ?? new Date().toISOString().split("T")[0];
  
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY!;
  const sb = createClient(url, key);

  const startDt = new Date(`${dateParam}T00:00:00-03:00`).toISOString();
  const endDt   = new Date(`${dateParam}T23:59:59-03:00`).toISOString();

  const { data, error } = await sb
    .from("matches")
    .select("fixture_id, league_name, date, status, home_team_name, away_team_name, goals_home, goals_away")
    .gte("date", startDt)
    .lte("date", endDt)
    .order("date");

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data || []);
}
