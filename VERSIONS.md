# Pinned System & Component Versions

Every model and driver version used in Reflex Arc must be recorded as an exact string, never as "latest", in every `StepRecord` and run summary.

| Component | Pinned Version / Release | Pinned Date | Notes |
| :--- | :--- | :--- | :--- |
| **macOS** | Darwin 24 (macOS 15 Sequoia / Apple Silicon) | Sep 23, 2026 | Host platform |
| **Python** | 3.12.x (Virtualenv) | Sep 23, 2026 | Orchestrator runtime (3.13 incompatible with mlx-whisper) |
| **Cua Driver** | `cua-driver==0.28.2` | Sep 23, 2026 | Python SDK package |
| **Decision Stand-in (`kev`)** | `kev-0.5b` (v0.1.0) | Sep 23, 2026 | Local `POST /v1/systemone` provider |
| **Decision Remote (`Jev`)** | Pending Access / Registration | Week 1–2 | Pinned once first API call is made |
| **Planner Cortex Model** | `openai/gpt-4o-mini` (via OpenRouter) | Week 3 | Vision-capable recovery & text typing |
| **Audio STT (Voice)** | `mlx-whisper>=0.2.0` | Sep 23, 2026 | Local push-to-talk transcription on Apple Silicon |
| **Orchestration** | `langgraph==1.2.12` | Sep 23, 2026 | State machine for loop controller |
| **TypeSafe SDK** | `typesafe-sdk==0.7.1` | Sep 23, 2026 | Jev/kev API client (requires pydantic>=2.12.0) |
| **Pydantic** | `pydantic==2.13.5` | Sep 23, 2026 | Data validation (typesafe-sdk requires >=2.12.0) |
| **FastAPI** | `fastapi==0.141.1` | Sep 23, 2026 | Web server for run console |
| **OpenAI** | `openai==3.19.0` | Sep 23, 2026 | OpenRouter API client |
| **HTTPX** | `httpx==0.28.1` | Sep 23, 2026 | HTTP client for API calls |
