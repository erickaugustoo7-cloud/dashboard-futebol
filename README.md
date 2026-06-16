# ⚽ Football Monitor — Futebol Virtual Bet365

Pipeline completo de monitoramento de partidas de futebol virtual com ingestão automática via Vercel Cron e análise local com Python/Pandas.

## Arquitetura

```
API RapidAPI (futebol-virtual-bet3651) → Vercel Cron (Next.js) → Firestore → Python/Pandas
```

---

## Estrutura do Projeto

```
football-monitor/
├── app/
│   └── api/
│       ├── sync-matches/
│       │   └── route.ts        ← Cron principal: busca histórico + próximos + last-updated
│       └── last-updated/
│           └── route.ts        ← Endpoint para consultar status de sync por liga
├── analysis/
│   ├── virtual_matches_analysis.py   ← Script de análise completa (odds, HT/FT, por liga)
│   └── output/                       ← CSVs e JSONs gerados (gitignored)
├── .env.example                ← Template de variáveis de ambiente
├── .gitignore
├── package.json
├── vercel.json                 ← Cron configurado: toda hora (0 * * * *)
└── README.md
```

---

## Endpoints da API

### `GET /api/sync-matches`
Dispara a sincronização de todas as ligas (ou uma específica) com o Firestore.

| Query param | Tipo    | Padrão | Descrição |
|-------------|---------|--------|-----------|
| `league`    | string  | todas  | Sincronizar apenas uma liga (ex: `?league=euro`) |
| `limit`     | integer | 50     | Quantidade de registros históricos por liga (máx: 1500) |

**Proteção**: requer `Authorization: Bearer <CRON_SECRET>` ou header `x-vercel-cron: 1`.

**Resposta 200:**
```json
{
  "message": "Sincronização concluída.",
  "leagues": ["euro", "copa", "super", "expressar", "primeiro"],
  "synced": 312,
  "created": 45,
  "updated": 267,
  "perLeague": {
    "euro": { "synced": 62, "created": 10, "updated": 52, "apiLastUpdated": "2025-11-21 14:30:00" }
  }
}
```

---

### `GET /api/last-updated`
Retorna metadados da última sincronização por liga (lidos da coleção `league_meta` do Firestore).

| Query param | Tipo   | Padrão | Descrição |
|-------------|--------|--------|-----------|
| `league`    | string | todas  | Filtrar uma liga específica |

**Proteção**: mesma autenticação do `sync-matches`.

**Resposta 200:**
```json
{
  "status": true,
  "queried": ["euro", "copa"],
  "data": {
    "euro": {
      "league": "euro",
      "lastSyncedAt": "2025-11-21T23:00:00.000Z",
      "apiLastUpdated": "2024-11-21 14:30:00",
      "lastSyncStats": { "synced": 62, "created": 10, "updated": 52 }
    }
  }
}
```

---

## Estrutura do Firestore

### Coleção `virtual_matches`
Documento ID: `{league}_{matchId}` (ex: `euro_731284`)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `matchId` | string | ID original da API |
| `league` | string | Nome da liga |
| `type` | string | `"history"` ou `"next"` |
| `homeTeam` / `awayTeam` | string | Times |
| `score` | map | `{ home, away }` — placar final |
| `scoreHt` | map | `{ home, away }` — placar HT |
| `odds` | map | Todas as odds retornadas pela API |
| `firstScorer` | string | Primeiro time a marcar |
| `lastScorer` | string | Último time a marcar |
| `htFtWinner` | string | Vencedor HT/FT |
| `matchCreatedAt` | string | Timestamp da API |
| `lastSyncedAt` | timestamp | Última sincronização |
| `createdAt` | timestamp | Primeira inserção no Firestore |
| `updatedAt` | timestamp | Última atualização |

### Coleção `league_meta`
Documento ID: `{league}` (ex: `euro`)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `league` | string | Nome da liga |
| `lastSyncedAt` | timestamp | Quando foi sincronizado |
| `apiLastUpdated` | string | Resposta da API `/last-updated` |
| `lastSyncStats` | map | `{ synced, created, updated }` |

---

## Ligas Suportadas

| Liga | Identificador |
|------|--------------|
| Euro | `euro` |
| Copa | `copa` |
| Super | `super` |
| Express | `expressar` |
| Premier | `primeiro` |

---

## Setup — Node.js / Vercel

### 1. Instalar dependências

```bash
cd football-monitor
npm install
```

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env.local
# Edite .env.local com seus valores reais
```

### 3. Obter credenciais Firebase

1. Acesse [Firebase Console](https://console.firebase.google.com)
2. Projeto → Configurações → Contas de Serviço
3. Clique em **"Gerar nova chave privada"** → baixa `serviceAccountKey.json`
4. Copie o conteúdo **completo** do arquivo
5. Cole como valor de `FIREBASE_SERVICE_ACCOUNT` no `.env.local`

### 4. Obter chave da API RapidAPI

1. Acesse [RapidAPI — Futebol Virtual Bet365](https://rapidapi.com)
2. Inscreva-se e copie a `X-RapidAPI-Key`
3. Cole em `FOOTBALL_API_KEY` no `.env.local`

### 5. Rodar localmente

```bash
npm run dev

# Em outro terminal, testar o sync (todas as ligas, 5 registros):
curl -s -H "Authorization: Bearer super_secret_cron_token_123" \
  "http://localhost:3000/api/sync-matches?limit=5" | jq .

# Testar uma liga específica:
curl -s -H "Authorization: Bearer super_secret_cron_token_123" \
  "http://localhost:3000/api/sync-matches?league=euro&limit=10" | jq .

# Verificar status de sincronização:
curl -s -H "Authorization: Bearer super_secret_cron_token_123" \
  "http://localhost:3000/api/last-updated" | jq .
```

### 6. Deploy na Vercel

```bash
npm install -g vercel
vercel deploy
```

Adicione as variáveis de ambiente na Vercel:
- `FIREBASE_SERVICE_ACCOUNT` → JSON completo do serviceAccountKey
- `FOOTBALL_API_KEY` → chave RapidAPI
- `CRON_SECRET` → string aleatória (`openssl rand -hex 32`)

O Cron roda automaticamente toda hora (Plano Hobby) ou a cada 30 min (Plano Pro — altere `vercel.json`).

---

## Setup — Python (Análise Local)

### 1. Criar ambiente virtual

```bash
cd analysis
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate
```

### 2. Instalar dependências

```bash
pip install google-cloud-firestore pandas numpy python-dotenv
```

### 3. Rodar análise

```bash
# Todas as ligas:
python analysis/virtual_matches_analysis.py

# Uma liga específica:
python analysis/virtual_matches_analysis.py euro
```

O script vai:
- Conectar ao Firestore e exibir status de sincronização por liga
- Exportar todas as partidas históricas para análise
- Exibir estatísticas: gols, BTTS, over/under, resultados HT/FT, viradas
- Exibir análise de odds: probabilidades implícitas, margem do bookmaker, calibração de favorito
- Exibir relatório de próximos jogos com odds formatadas
- Salvar `output/virtual_matches_history_YYYYMMDD.csv`
- Salvar `output/virtual_matches_next_YYYYMMDD.csv`
- Salvar `output/summary_YYYYMMDD.json`

---

## Variáveis de Ambiente

| Variável | Usada por | Descrição |
|----------|-----------|-----------|
| `FIREBASE_SERVICE_ACCOUNT` | Node.js + Python | JSON do serviceAccountKey.json |
| `FOOTBALL_API_KEY` | Node.js (Vercel) | Chave RapidAPI |
| `CRON_SECRET` | Node.js | Token de proteção da rota |

---

## Segurança

- `serviceAccountKey.json` **nunca** deve ser commitado — está no `.gitignore`
- O `.env.local` também está no `.gitignore`
- As rotas `/api/sync-matches` e `/api/last-updated` só aceitam chamadas do Vercel Cron (`x-vercel-cron: 1`) ou com o `CRON_SECRET` no header `Authorization`

---

## Frequência do Cron

| Plano Vercel | Schedule atual | Frequência |
|-------------|----------------|------------|
| Hobby | `0 * * * *` | 1x por hora |
| Pro | Alterar para `*/30 * * * *` | A cada 30 min |
| Pro | Alterar para `*/10 * * * *` | A cada 10 min |

Para mudar, edite o campo `schedule` em `vercel.json`.

---

## Arquivos Legados (raiz do workspace)

> ⚠️ Os arquivos na raiz (`/files/`) são versões antigas e **não devem ser editados**:
> - `route.ts` → obsoleto, use `football-monitor/app/api/sync-matches/route.ts`
> - `firestore_analysis.py` → script para Brasileirão real, não para Futebol Virtual
