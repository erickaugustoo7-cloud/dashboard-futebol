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

  const TEAM_TRANSLATIONS: Record<string, string> = {
    "Spain": "Espanha", "Cape Verde": "Cabo Verde", "Germany": "Alemanha",
    "England": "Inglaterra", "France": "França", "Italy": "Itália",
    "Netherlands": "Holanda", "Portugal": "Portugal", "Belgium": "Bélgica",
    "Croatia": "Croácia", "Switzerland": "Suíça", "Denmark": "Dinamarca",
    "Sweden": "Suécia", "Poland": "Polônia", "Austria": "Áustria",
    "Czech Republic": "República Tcheca", "Hungary": "Hungria", "Turkey": "Turquia",
    "Scotland": "Escócia", "Wales": "País de Gales", "Ireland": "Irlanda",
    "Serbia": "Sérvia", "Ukraine": "Ucrânia", "Greece": "Grécia",
    "Norway": "Noruega", "Finland": "Finlândia", "Romania": "Romênia",
    "Slovakia": "Eslováquia", "Slovenia": "Eslovênia", "Iceland": "Islândia",
    "Argentina": "Argentina", "Brazil": "Brasil", "Uruguay": "Uruguai",
    "Colombia": "Colômbia", "Chile": "Chile", "Peru": "Peru",
    "Ecuador": "Equador", "Paraguay": "Paraguai", "Venezuela": "Venezuela",
    "Bolivia": "Bolívia", "Mexico": "México", "United States": "Estados Unidos",
    "Canada": "Canadá", "Costa Rica": "Costa Rica", "Japan": "Japão",
    "South Korea": "Coreia do Sul", "Australia": "Austrália", "Iran": "Irã",
    "Saudi Arabia": "Arábia Saudita", "Morocco": "Marrocos", "Senegal": "Senegal",
    "Egypt": "Egito", "Nigeria": "Nigéria", "Cameroon": "Camarões",
    "Ghana": "Gana", "Ivory Coast": "Costa do Marfim", "Algeria": "Argélia",
    "South Africa": "África do Sul", "New Zealand": "Nova Zelândia"
  };

  const translatedData = (data || []).map(m => ({
    ...m,
    home_team_name: TEAM_TRANSLATIONS[m.home_team_name] || m.home_team_name,
    away_team_name: TEAM_TRANSLATIONS[m.away_team_name] || m.away_team_name
  }));

  return NextResponse.json(translatedData);
}
