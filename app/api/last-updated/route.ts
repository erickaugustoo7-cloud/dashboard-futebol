// app/api/last-updated/route.ts
// Expõe os metadados de última sincronização por liga (lidos do Firestore)
import { NextRequest, NextResponse } from "next/server";
import * as admin from "firebase-admin";

// ── Inicialização singleton compartilhada ──
function getFirestoreDb() {
  if (!admin.apps.length) {
    const serviceAccountJson = process.env.FIREBASE_SERVICE_ACCOUNT;
    if (!serviceAccountJson) {
      throw new Error(
        "A variável de ambiente FIREBASE_SERVICE_ACCOUNT não está definida."
      );
    }
    const serviceAccount = JSON.parse(serviceAccountJson);
    admin.initializeApp({
      credential: admin.credential.cert(serviceAccount),
    });
  }
  return admin.firestore();
}

const ALL_LEAGUES = ["euro", "copa", "super", "expressar", "primeiro"];

/**
 * GET /api/last-updated
 *
 * Query params opcionais:
 *   ?league=euro   → retorna apenas os metadados dessa liga
 *                    (omitir = retorna todas as ligas)
 *
 * Requer header: Authorization: Bearer <CRON_SECRET>
 * (ou chamada interna do Vercel Cron com x-vercel-cron: 1)
 *
 * Resposta 200:
 * {
 *   "status": true,
 *   "data": {
 *     "euro": {
 *       "league": "euro",
 *       "lastSyncedAt": "2025-11-21T23:00:00Z",
 *       "apiLastUpdated": "2024-11-21 14:30:00",
 *       "lastSyncStats": { "synced": 56, "created": 10, "updated": 46 }
 *     },
 *     ...
 *   }
 * }
 */
export async function GET(req: NextRequest) {
  // ── Proteção da rota ──
  const isVercelCron = req.headers.get("x-vercel-cron") === "1";
  const authHeader = req.headers.get("authorization");
  const isInternalCall = authHeader === `Bearer ${process.env.CRON_SECRET}`;

  if (!isVercelCron && !isInternalCall) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const db = getFirestoreDb();
    const { searchParams } = new URL(req.url);
    const leagueParam = searchParams.get("league");

    const leaguesToQuery = leagueParam ? [leagueParam] : ALL_LEAGUES;

    // Busca todos os documentos de league_meta em paralelo
    const refs = leaguesToQuery.map((l) =>
      db.collection("league_meta").doc(l)
    );

    const snapshots = await Promise.all(refs.map((r) => r.get()));

    const data: Record<string, object | null> = {};

    snapshots.forEach((snap, idx) => {
      const league = leaguesToQuery[idx];
      if (snap.exists) {
        const docData = snap.data()!;
        // Converte Timestamp do Firestore para ISO string legível
        data[league] = {
          league: docData.league,
          lastSyncedAt:
            docData.lastSyncedAt?.toDate?.()?.toISOString() ?? null,
          apiLastUpdated: docData.apiLastUpdated ?? null,
          lastSyncStats: docData.lastSyncStats ?? null,
        };
      } else {
        // Liga ainda não sincronizada
        data[league] = null;
      }
    });

    return NextResponse.json({
      status: true,
      queried: leaguesToQuery,
      data,
    });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Erro desconhecido";
    console.error("[last-updated] ERRO:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
