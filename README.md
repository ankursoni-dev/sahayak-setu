# SahayakSetu (सहायक सेतु) 🚀🇮🇳
### **Empowering Every Indian: A Zero-Cost, Multilingual Voice AI Bridge for Government Welfare.**

[![Live Demo](https://img.shields.io/badge/Live-Demo-brightgreen)](https://sahayak-setu.vercel.app)
[![Challenge](https://img.shields.io/badge/Challenge-Accessibility_%26_Societal_Impact-blue)](#)
[![Stack](https://img.shields.io/badge/Stack-Voice--First_Dual--Brain_AI-orange)](#)
[![Status](https://img.shields.io/badge/Status-Hackathon--demo-yellow)](#)

---

## 🏗️ The Mission: Bridging the "Inclusion Gap"
**Track:** *Voice AI Agent for Accessibility & Societal Impact*

**The Problem:** India has 1,200+ government schemes, yet millions remain unaware of their eligibility because documentation is overwhelmingly stored in complex English PDFs. For the last-mile citizen—especially the rural, elderly, or non-literate—this creates a **Digital & Linguistic Barrier** to their basic rights.

**The Solution:** SahayakSetu is a **demo-hardened**, voice-first digital concierge built with production-style patterns (grounding, timeouts, quotas) to dismantle the 'last-mile' information barrier. By combining high-precision Vector RAG with real-time script-aware intelligence, we enable citizens to translate complex government bureaucracy into clear, actionable roadmaps in their native dialect—reimagining the relationship between citizen and state from a passive search for 'answers' to an empowered pursuit of 'action'.

---

## 🔗 Quick Links
- **Frontend (Production)**: [https://sahayak-setu.vercel.app](https://sahayak-setu.vercel.app)
- **Backend (Render API)**: [https://sahayaksetu-backend-3kxl.onrender.com/health](https://sahayaksetu-backend-3kxl.onrender.com/health)
- **Knowledge Base**: [38 Verified Scheme Chunks (Qdrant)](/scripts/ingest.py)

### Render / free tier cold starts (demo killer)

Serverless hosts **spin down** idle services; the first request after idle can take **30–60+ seconds**. **No repo change fixes this by itself.** Use an external uptime monitor to `GET` your `/health` or `/ready` URL **every 10–14 minutes** (e.g. [UptimeRobot](https://uptimerobot.com), Better Stack, or a cron) so the instance stays warm before demos and judging.

---

## 🛠️ The 5-Step Pipeline: How It Happens

### **Step 1: Regional Voice Capture (STT)** 🎤
*   **What**: The system captures the user's voice in 6 core Indian languages.
*   **How**: Using **Vapi.ai** integrated with **Azure Neural STT**, we achieve sub-second latency for regional dialects, supporting real-time "interim results" for a responsive UI.

### **Step 2: Semantic Intelligence (Vector Search)** 🔍
*   **What**: We don't just search keywords; we search **meaning**.
*   **How**: User queries are converted into 384-dimensional dense vectors using **FastEmbed**. These are searched against a **Qdrant Vector Database** containing **35+ high-precision, verified government scheme chunks** with a strict **0.2 similarity threshold** to ensure precise grounding.

### **Step 3: Intelligence Fusion & Memory (The Dual-Brain)** 🧠⚡
*   **What**: Heavyweight reasoning and **conversational continuity**.
*   **How**: We use **Gemini 2.0 Flash** as our primary brain. Our system maintains an in-memory **Session Store** that preserves context across exchanges, allowing for natural follow-up questions like *"What about my documents?"*. If rate limits are hit, we instantly fall back to **Groq (Llama 3.3 70B)**.

### **Step 4: Linguistic Mirroring (Cultural Adaptation)** 🔄🇮🇳
*   **What**: The AI responds in the exact language & script used by the user.
*   **How**: A custom-prompted **Master Orchestrator** detects the query script and mirrors the response. If the query is Hindi/Kannada/Bengali, the answer is fluently mirrored in that specific script with total empathy.

### **Step 5: Script-Aware Neural Voice (TTS)** 🔊
*   **What**: High-fidelity regional speech response.
*   **How**: Our frontend uses a **RegEx Script Detector** to analyze the AI's response text. It then forces the browser to load the matching regional neural voice (e.g., Azure Swara for Hindi), ensuring that technical data is read with a perfect cultural accent.

---

## 🛡️ Why SahayakSetu? (The Competitive Moat)
Judges often ask: *"How is this different from Google Voice Search?"* 

1. **Synthesized Action vs. Blue Links**: SahayakSetu provides a **verified action plan** (Eligibility ➜ Benefits ➜ Next Step), not just a list of websites to read.
2. **"Expert" RAG vs. General Crawling**: We search a high-confidence, curated Vector DB of verified scheme documentation with code-enforced grounding.
3. **Conversational Continuity**: Unlike static QA bots, our **Active History Store** allows users to have a back-and-forth dialogue about their welfare options.
4. **Trust Infrastructure**: Every answer is tagged with a **Semantic Match %**, proving the transparency and source-grounding of the AI's logic.

---

## 🎯 Societal Impact & Scalability
- **Grounding-first transparency**: Every response includes a **semantic match %** tied to retrieved catalogue text (this is *retrieval* confidence, not a legal guarantee). The main answer path is grounded and verified; some action-plan fields are model-generated with URL filtering — see limitation below.
- **In-Memory Scalability**: Optimized for low-footprint deployment on Render Free Tier (~200MB RAM usage).
- **Sustainable Scaling**: Built entirely on **Free Tier infrastructure** (Google AI Studio, Groq Free, Qdrant Cloud), making it viable for 100% free deployment to millions of citizens.

### Known Limitation (current demo scope)
- `AgentPlan` fields like `documents_needed` and criteria explanations are model-generated from grounded sources; they are filtered for source references/URLs, but not yet claim-by-claim grounded with the same strict verifier used for final answer claims.

---

## 🚀 Setup & Installation

Choose **Option A** (Docker — recommended, zero dependency headaches) or **Option B** (bare-metal Python).

---

### Option A — Docker Compose (Recommended)

Docker bundles the backend, Qdrant vector DB, and Redis cache together. You only need Docker Desktop installed.

#### 1. Clone the repo
```bash
git clone https://github.com/bansalbhunesh/SahayakSetu.git
cd SahayakSetu
```

#### 2. Create your `.env` file
Copy the template and fill in your API keys:
```bash
cp .env.example .env   # or manually create .env
```

Minimum required keys:
```env
# At least one LLM key is required (Gemini preferred, Groq as fallback)
GEMINI_API_KEY=your_google_ai_studio_key
GROQ_API_KEY=your_groq_key          # fallback if Gemini quota runs out

# Qdrant — use the Docker URL below when running via docker-compose
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=                     # leave blank for local Docker Qdrant

# App settings
ENV=development
MODERATION_STRICT=false
SESSION_SECRET=any_random_string_here
REDIS_URL=redis://localhost:6379/0
FRONTEND_ORIGIN=http://127.0.0.1:5500
```

> **Get API keys:**
> - Gemini: [aistudio.google.com/apikey](https://aistudio.google.com/apikey) (free tier available)
> - Groq: [console.groq.com](https://console.groq.com) (free tier, very fast)

#### 3. Start all services
```bash
docker-compose up -d
```
This starts three containers: `backend` (port 8000), `qdrant` (port 6333), `redis` (port 6379).

Wait ~15 seconds for the backend to finish loading the embedding model, then verify:
```bash
curl http://localhost:8000/health
# Expected: {"status":"online","model":"gemini-2.0-flash",...}
```

#### 4. Ingest the knowledge base into Qdrant
Run this once (and re-run whenever you update `scripts/data/schemes.json`). The default
mode is **upsert** (idempotent — safe to re-run; chunks keep stable hash-derived IDs):
```bash
QDRANT_URL=http://localhost:6333 QDRANT_API_KEY= python scripts/ingest.py
```
For a clean rebuild (drops the collection first), pass `--recreate`. Against a non-local
Qdrant the script will prompt for confirmation; pass `--yes` in CI to skip the prompt.
You should see: `[SUCCESS] Repository ready!`

#### 5. Open the frontend
Open `frontend/index.html` directly in your browser, or use a live server (e.g. VS Code Live Server extension on port 5500). Make sure `FRONTEND_ORIGIN` in `.env` matches whatever address you use.

#### 6. Test the API (optional)
```bash
curl -s -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "PM Kisan benefits eligibility", "language": "en"}'
```

---

### Option B — Bare-Metal Python (No Docker)

Use this if you prefer to run without Docker. You'll need Python 3.12+ and either a local Qdrant binary or a Qdrant Cloud account.

#### 1. Clone & install dependencies
```bash
git clone https://github.com/bansalbhunesh/SahayakSetu.git
cd SahayakSetu
pip install -r requirements.txt
```

#### 2. Set up Qdrant
- **Cloud (easiest):** Create a free cluster at [cloud.qdrant.io](https://cloud.qdrant.io). Copy the cluster URL and API key.
- **Local binary:** Download from [qdrant.tech/documentation/guides/installation](https://qdrant.tech/documentation/guides/installation/) and run `./qdrant` (listens on `localhost:6333`).

#### 3. Create your `.env` file
```env
GEMINI_API_KEY=your_google_ai_studio_key
GROQ_API_KEY=your_groq_key

# For Qdrant Cloud:
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key

# For local Qdrant binary:
# QDRANT_URL=http://localhost:6333
# QDRANT_API_KEY=

ENV=development
MODERATION_STRICT=false
SESSION_SECRET=any_random_string_here
REDIS_URL=redis://localhost:6379/0   # optional; remove if no Redis
FRONTEND_ORIGIN=http://127.0.0.1:5500
```

#### 4. Ingest the knowledge base
```bash
python scripts/ingest.py
```

#### 5. Start the backend
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 6. Open the frontend
Open `frontend/index.html` in your browser or via VS Code Live Server.

---

### Re-ingesting after adding new schemes

Whenever you edit `scripts/data/schemes.json` (to add or update schemes), re-run the ingest script:

```bash
# Docker:
QDRANT_URL=http://localhost:6333 QDRANT_API_KEY= python scripts/ingest.py

# Bare-metal (keys already in .env):
python scripts/ingest.py
```

Then flush the Redis answer cache so stale responses don't persist:
```bash
# Docker:
docker exec sahayaksetu-redis-1 redis-cli FLUSHALL

# Bare-metal:
redis-cli FLUSHALL
```

---

### Stopping & restarting

```bash
# Stop all containers
docker-compose down

# Start again (skips image rebuild if nothing changed)
docker-compose up -d

# Force rebuild after code changes
docker-compose up -d --build
```

---

### Environment variables reference

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes* | Google AI Studio key for Gemini 2.0 Flash |
| `GROQ_API_KEY` | Yes* | Groq key for Llama 3.3 70B fallback |
| `QDRANT_URL` | Yes | `http://qdrant:6333` (Docker) or Qdrant Cloud URL |
| `QDRANT_API_KEY` | No | Leave blank for local Docker Qdrant |
| `REDIS_URL` | Yes | `redis://redis:6379/0` (Docker) or local Redis |
| `REDIS_QUOTA_STRICT` | No | When unset: strict in `ENV=production` (Redis errors deny LLM quotas). Set `false` for fail-open if Redis is optional. |
| `SESSION_SECRET` | Yes | Any random string for session signing |
| `ENV` | No | `development` or `production` |
| `MODERATION_STRICT` | No | `false` (dev) / `true` (prod — fails closed on LLM errors) |
| `AGENT_PLAN_CALL_TIMEOUT_S` | No | Max seconds for action-plan JSON LLM calls (default `90`) |
| `NEAR_MISS_SCORE_FLOOR` | No | Min retrieval score for near-miss rows (default `0.15`) |
| `VAPI_WEBHOOK_MAX_SKEW_S` | No | Max age skew for signed webhook JSON timestamps (default `300` seconds) |
| `VAPI_WEBHOOK_REQUIRE_TIMESTAMP` | No | If `true`, webhook JSON must include a parseable `createdAt` / `timestamp` |
| `RATE_LIMIT_USE_REDIS` | No | When `true` (default in `ENV=production`), use `REDIS_URL` for SlowAPI limits. Override with `RATE_LIMIT_STORAGE_URI`. |
| `FRONTEND_ORIGIN` | No | URL of frontend for CORS (e.g. `http://127.0.0.1:5500`) |
| `VAPI_API_KEY` | No | Only needed for voice call feature via Vapi.ai |
| `VAPI_ASSISTANT_ID` | No | Only needed for voice call feature |
| `VAPI_WEBHOOK_SECRET` | No | Validates incoming Vapi webhook signatures |

*At least one of `GEMINI_API_KEY` or `GROQ_API_KEY` is required.

---

### End-to-end UI tests (Playwright)

From the repo root (requires Node 18+):

```bash
npm ci
npx playwright install chromium
npm run test:e2e
```

Tests serve the static `frontend/` folder and **mock** `POST /api/search`, so no local backend is required.

**Streaming:** `POST /api/search/stream` returns **`application/x-ndjson`**: first line `{"type":"meta","trace_id":"..."}`; while the LLM runs, zero or more lines `{"type":"token","text":"..."}` (Gemini or Groq streaming); final line `{"type":"complete","data":{...same shape as /api/search...}}`. **Cache hits** emit `{"type":"phase","name":"cache_hit"}` then a single `token` with the cached answer when present, then `complete` (no LLM). Errors use `{"type":"error","status_code":...,"detail":...}`.

---

### Deploying to production

- **Backend → Render:** Push to `main`; Render auto-deploys via `render.yaml`. Set all env vars in the Render dashboard. Set `MODERATION_STRICT=true` and `QDRANT_URL` to your Qdrant Cloud URL.
- **Frontend → Vercel:** Run `vercel --prod` from the repo root. `vercel.json` handles all routing.
- After deploying backend, update `BACKEND_URL` in your `.env` and re-deploy frontend so it points to the live API.

---

*Built for Hackblr 2026 — Bridging the gap for a Digital, Inclusive India.* 🇮🇳🏆
