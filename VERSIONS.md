# Pinned System & Component Versions

Every model and driver version used in Reflex Arc must be recorded as an exact string, never as "latest", in every `StepRecord` and run summary.

| Component | Pinned Version / Release | Pinned Date | Notes |
| :--- | :--- | :--- | :--- |
| **macOS** | Darwin 24 (macOS 15 Sequoia / Apple Silicon) | Sep 23, 2026 | Host platform |
| **Python** | 3.13.5 (Virtualenv) | Sep 23, 2026 | Orchestrator runtime |
| **Cua Driver** | Pinned on install | Week 0 | `CuaDriver.app` daemon |
| **Decision Stand-in (`kev`)** | `kev-0.5b` (v0.1.0) | Sep 23, 2026 | Local `POST /v1/systemone` provider |
| **Decision Remote (`Jev`)** | Pending Access / Registration | Week 1–2 | Pinned once first API call is made |
| **Planner Cortex Model** | `openai/gpt-4o-mini` (via OpenRouter) | Week 3 | Vision-capable recovery & text typing |
| **Audio STT (Voice)** | `mlx-whisper` | Week 3 | Local push-to-talk transcription on Apple Silicon |
