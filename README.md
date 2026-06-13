# ⚽ Football Monitor

Pipeline de monitoramento de partidas de futebol com ingestão automática via Vercel Cron e análise local com Python/Pandas.

## Arquitetura

```
API Football → Vercel Cron (Next.js) → Firestore → Python/Pandas
```

---

## Estrutura do Projeto

```
football-monitor/
├── app/
│   └── api/
│       └── sync-matches/
│           └── route.ts        ← Handler do Cron (ingestão)
├── analysis/
│   ├── firestore_analysis.py   ← Script de análise Python
│   ├── requirements.txt        ← Dependências Python
│   └── output/                 ← CSVs gerados (gitignored)
├── .env.example                ← Template de variáveis de ambiente
├── .gitignore
├── package.json
├── vercel.json                 ← Configuração do Cron (23:00 UTC diário)
└── README.md
```

---

## Setup — Node.js / Vercel

### 1. Instalar dependências

```bash
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

### 4. Obter chave da API Football

1. Acesse [RapidAPI — API-Football](https://rapidapi.com/api-sports/api/api-football)
2. Inscreva-se no plano gratuito (100 req/dia)
3. Copie a `X-RapidAPI-Key` para `FOOTBALL_API_KEY`

### 5. Rodar localmente

```bash
npm run dev

# Em outro terminal, testar o sync:
npm run sync:local
```

### 6. Deploy na Vercel

```bash
npm install -g vercel
vercel deploy
```

Na Vercel, adicione as 3 variáveis de ambiente:
- `FIREBASE_SERVICE_ACCOUNT` → JSON completo do serviceAccountKey
- `FOOTBALL_API_KEY` → chave da API
- `CRON_SECRET` → string aleatória (`openssl rand -hex 32`)

O Cron roda automaticamente todo dia às **23:00 UTC (20:00 BRT)**.

---

## Setup — Python (Análise Local)

### 1. Criar ambiente virtual

```bash
cd analysis
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# ou: .venv\Scripts\activate  # Windows
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Configurar variáveis (mesmo `.env.local` do projeto raiz)

O script Python lê automaticamente o `.env.local` na raiz do projeto. Certifique-se de que `FIREBASE_SERVICE_ACCOUNT` está preenchido.

### 4. Rodar análise

```bash
# A partir da raiz do projeto:
python analysis/firestore_analysis.py
```

O script vai:
- Conectar ao Firestore
- Exportar todas as partidas para um DataFrame
- Limpar e normalizar os dados
- Exibir estatísticas no terminal
- Salvar `analysis/output/matches_clean_YYYYMMDD.csv`
- Salvar `analysis/output/summary_YYYYMMDD.json`

---

## Variáveis de Ambiente

| Variável | Usada por | Descrição |
|---|---|---|
| `FIREBASE_SERVICE_ACCOUNT` | Node.js + Python | JSON do serviceAccountKey.json |
| `FOOTBALL_API_KEY` | Node.js (Vercel) | Chave da API-Football |
| `CRON_SECRET` | Node.js + testes locais | Token de proteção da rota |

---

## Segurança

- `serviceAccountKey.json` **nunca** deve ser commitado — está no `.gitignore`
- O `.env.local` também está no `.gitignore`
- A rota `/api/sync-matches` só aceita chamadas do Vercel Cron (`x-vercel-cron: 1`) ou com o `CRON_SECRET` no header `Authorization`

---

## Próximos Passos Sugeridos

- **Paginação Firestore**: Ao crescer a base, use `limit()` + `start_after()` no Python para não ler milhares de docs de uma vez
- **Outliers**: Implemente detecção de outliers com IQR na contagem de escanteios (função `detect_outliers` já incluída no script)
- **Dashboard**: Conecte o DataFrame a um Streamlit ou Metabase para visualizações
- **Múltiplas ligas**: Parametrize o Cron para varrer mais de uma liga por execução
