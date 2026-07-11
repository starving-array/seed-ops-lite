# External Requirements — Signups, API Keys & Accounts

## When You Need Each Thing

| # | Task | External Work Needed | When |
|---|------|---------------------|------|
| 1 | Run with **Fireworks AI** | Sign up → get API key | **Now** (for AMD hackathon) |
| 2 | Run with **Gemini** | Get Google API key | Optional |
| 3 | Run with **Vertex AI** | GCP project + location | Optional |
| 4 | Run with **Anthropic** | Sign up → get API key | Optional |
| 5 | Run with **OpenAI** | Sign up → get API key | Optional |
| 6 | Run with **Ollama** (local) | Install Ollama on your machine | Optional |
| 7 | Run with **ROCm** (AMD GPU) | AMD Linux machine or AMD Developer Cloud | **For Gemma prize** |
| 8 | Build & run **Docker** | Install Docker Desktop | **Now** (submission requirement) |
| 9 | Deploy **public demo URL** | AMD Developer Cloud or cloud VM | **Before submission** |

---

## 1. Fireworks AI (for AMD Hackathon)

**What you get:** Hosted Gemma models via API (AMD-backed infrastructure).

```bash
# 1. Go to https://fireworks.ai
# 2. Sign up (GitHub or email)
# 3. Go to API Keys page → Create new key
# 4. Add to .env:
FIREWORKS_API_KEY=fw_3aBcDeFgHiJkLmNoPqRsTuVwXyZ
```

Available Gemma models on Fireworks:
- `accounts/fireworks/models/gemma2-9b`
- `accounts/fireworks/models/gemma2-2b`

---

## 2. Google Gemini (free tier available)

```bash
# 1. Go to https://aistudio.google.com/app/apikey
# 2. Click "Create API Key"
# 3. Add to .env:
GOOGLE_API_KEY=AIzaSy...
# 4. Set provider:
LLM_PROVIDER=gemini
```

---

## 3. AMD ROCm (for the $2,000 Gemma Prize)

**Requires Linux with AMD GPU.**

```bash
# Option A: AMD Developer Cloud (free credits)
# 1. Apply at https://developer.amd.com/amd-development-cloud
# 2. Provision an instance with MI250/MI300 GPU
# 3. Install Docker + ROCm

# Option B: Physical AMD GPU machine
# Install ROCm: https://rocm.docs.amd.com
# Verify:
rocm-smi --showproductname

# In .env:
ROCm_ENABLED=true

# Download a Gemma model:
python scripts/download_model.py download gemma-2-9b-it
```

---

## 4. Docker (mandatory for submission)

```bash
# Download & install Docker Desktop:
# https://www.docker.com/products/docker-desktop/

# Build CPU image:
docker build -t safeseedops -f docker/Dockerfile .

# Build ROCm image (on AMD Linux machine):
docker build -t safeseedops:rocm -f docker/Dockerfile.rocm .

# Run with Docker Compose:
docker compose up -d
# App available at: http://localhost:8000
```

---

## Quick Start Checklist

- [ ] Sign up at [fireworks.ai](https://fireworks.ai) → add `FIREWORKS_API_KEY` to `.env`
- [ ] Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [ ] Run `docker compose up -d`
- [ ] Try: `curl http://localhost:8000/health`
- [ ] (Optional) Apply for [AMD Developer Cloud](https://developer.amd.com/amd-development-cloud) for ROCm/Gemma prize
