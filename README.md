# AIOps Microservices Lab

Comparative study of two AIOps agent architectures for automated fault diagnosis in microservices: **Event-Driven** (reactive) vs. **Continuous Polling** (proactive).

Both agents use **Google Gemini 2.5 Flash** to perform Root Cause Analysis (RCA) on Docker container logs and deliver diagnostic reports via **Discord** (ChatOps).

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Google Online Boutique                          │
│  frontend ── checkoutservice ── cartservice ── redis-cart           │
│      │            │                                                 │
│      └── productcatalog, currency, shipping, payment, email, ad     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ docker metrics
                          ┌────▼────┐
                          │Telegraf │ :9273
                          └────┬────┘
                               │ scrape
                          ┌────▼──────┐
                          │Prometheus │
                          └────┬──────┘
                               │ alerts
                        ┌──────▼──────┐
                        │Alertmanager │
                        └──────┬──────┘
                               │ webhook
                      ┌────────▼─────────┐
                      │  Event-Driven    │
                      │  AI Agent        │──────────┐
                      │  (analyzer.py)   │          │
                      └──────────────────┘          │
                                                    ▼
┌──────────────────────┐                   ┌──────────────────┐
│  Continuous Polling  │                   │  Discord (RCA +  │
│  AI Agent            │──────────────────▶│  FinOps Metrics) │
│(continuous_analyzer) │                   └──────────────────┘
└──────────┬───────────┘
           │ polls every 30s
           ▼
   Docker API (logs)
```

### AIOps Approaches

| Feature             | Event-Driven                             | Continuous Polling           |
| ------------------- | ---------------------------------------- | ---------------------------- |
| **Trigger**         | Prometheus alert via webhook             | Polling every 30 seconds     |
| **Entry Point**     | `analyzer.py`                            | `continuous_analyzer.py`     |
| **Idle Cost**       | $0 (no API calls)                        | Continuous token consumption |
| **Log Source**      | Last 200 lines from monitored containers | Delta logs since last poll   |
| **Normal Behavior** | No action                                | Responds `STATUS: NORMAL`    |

## Directory Structure

```
├── docker-compose.yml          # Full stack: Online Boutique + monitoring + AI agents
├── llm-trigger/                # AI agent source code
│   ├── analyzer.py             # Event-Driven agent
│   ├── continuous_analyzer.py  # Continuous Polling agent
│   ├── alert_toggle.py         # CLI tool to enable/disable Alertmanager silences
│   ├── bots/
│   │   └── discord_bot.py      # Discord ChatOps notification module
│   ├── Dockerfile
│   └── requirements.txt
├── load-tests/                 # K6 chaos engineering scenarios
│   ├── baseline.js             # Normal traffic
│   ├── cpu-spike.js            # CPU saturation via rapid checkout requests
│   ├── error-spike.js          # Business logic errors (HTTP 500s)
│   ├── oom-test.js             # Memory exhaustion via 2MB payloads
│   └── chaos-spike.js          # Combined CPU + error + memory pressure
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml      # Scrape config (Telegraf + self)
│   │   ├── alert.rules.yml     # PromQL alert rules (CPU and OOM isolation)
│   │   └── alertmanager.yaml   # Webhook routing to AI agent
│   └── telegraf/
│       └── telegraf.conf       # Docker metrics exporter
├── results/                    # Raw experiment data (5 runs × 5 scenarios × 2 agents)
│   ├── ai-agent/
│   │   └── logs/
│   │       ├── baseline-logs/
│   │       ├── error-spike-logs/
│   │       ├── chaos-spike-logs/
│   │       ├── cpu-spike-logs/
│   │       └── oom-test-logs/
│   └── ai-agent-continuous/
│       └── logs/
│           ├── baseline-logs/
│           ├── error-spike-logs/
│           ├── chaos-spike-logs/
│           ├── cpu-spike-logs/
│           └── oom-test-logs/
└── scripts/                    # Automation scripts for running experiments
    ├── run-ai-agent.sh         # Orchestrates N runs with the Event-Driven agent
    ├── run-ai-agent-continuous.sh  # Orchestrates N runs with the Continuous agent
    └── aggregate-logs.sh       # Aggregates and deduplicates results across runs

```

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [K6](https://k6.io/docs/getting-started/installation/) (or run via `docker run grafana/k6`)
- A Google Gemini API key
- A Discord webhook URL (for ChatOps alerts)

## Quick Start

1. **Clone and configure:**

   ```bash
   git clone https://github.com/albougleux/aiops-microservices-lab.git
   cd aiops-microservices-lab
   cp .env.example .env
   # Edit .env with your GEMINI_API_KEY and DISCORD_WEBHOOK_URL values
   ```

2. **Start the Event-Driven agent stack:**

   ```bash
   docker compose up -d --build
   ```

3. **Start the Continuous Polling agent (alternative):**

   ```bash
   docker compose --profile continuous up -d --build
   ```

4. **Run a load test:**
   ```bash
   docker run --rm -i grafana/k6 run -e TARGET_HOST=<YOUR_HOST_IP> - < load-tests/cpu-spike.js
   ```

## Experiment Scripts

The `scripts/` directory contains orchestration scripts for repeatable multi-run experiments:

```bash
# Event-Driven agent: 5 runs of the OOM test
export TARGET_HOST=<YOUR_HOST_IP>
bash scripts/run-ai-agent.sh oom-test 5

# Continuous agent: 5 runs of the CPU spike test
export TARGET_HOST=<YOUR_HOST_IP>
bash scripts/run-ai-agent-continuous.sh cpu-spike 5

# Aggregate results from all runs into a single markdown file
bash scripts/aggregate-logs.sh oom-test ai-agent 5
```

### Environment Variables for Scripts

| Variable             | Default                     | Description                                           |
| -------------------- | --------------------------- | ----------------------------------------------------- |
| `TARGET_HOST`        | _(required)_                | IP address of the remote host running the lab         |
| `SSH_KEY`            | _(required)_                | Path to SSH private key                               |
| `SSH_USER`           | _(required)_                | SSH login user                                        |
| `REMOTE_USER`        | _(required)_                | User on the remote machine that owns the Docker stack |
| `REMOTE_PROJECT_DIR` | `~/aiops-microservices-lab` | Path to the project on the remote host                |

## Alert Toggle

Manually enable or disable Prometheus alerts via Alertmanager silences:

```bash
docker exec ai-agent python alert_toggle.py disable HighMemory_OOM_Risk
docker exec ai-agent python alert_toggle.py enable HighMemory_OOM_Risk
```

## License

This project was developed as part of an academic thesis on AIOps for the Software Engineering postgraduate program.

## Acknowledgments

This project and its documentation were built with the assistance of AI tools.
