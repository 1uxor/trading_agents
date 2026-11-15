# Trading Agents Platform

A multi-agent algorithmic trading system with AI-powered strategies, real-time market data, mandatory risk management, and a React-based dashboard. Supports paper trading out of the box and optional MetaTrader 5 integration for live markets.

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (async), SQLite
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS
- **AI/ML:** OpenAI, Anthropic (Claude), Google Gemini, Ollama (local), HuggingFace
- **Broker:** Paper trading (default), MetaTrader 5 (optional)

## Project Structure

```
trading_agents/
├── backend/
│   ├── agent/           # Agent core logic, runner, commentary
│   ├── api/             # FastAPI routes (agents, market, risk, backtest, ws)
│   ├── broker/          # Broker adapters (paper, MT5)
│   ├── market_data/     # Data providers (synthetic, MT5, cache)
│   ├── strategies/      # Trading strategies & combiner
│   ├── models/          # LLM/ML providers (OpenAI, Anthropic, Gemini, Ollama, HF)
│   ├── risk/            # Risk manager (mandatory validation)
│   ├── backtest/        # Backtesting engine & metrics
│   ├── logging_/        # Trade & event logging
│   ├── config.py        # App settings (pydantic-settings)
│   ├── database.py      # SQLAlchemy ORM
│   └── main.py          # FastAPI entry point
├── frontend/
│   └── src/
│       ├── api/         # API client & WebSocket hook
│       ├── components/  # React components (Dashboard, WarRoom, etc.)
│       └── types/       # TypeScript definitions
├── configs/
│   └── example_agent.yaml
├── tests/               # pytest suite
├── pyproject.toml       # Python dependencies
└── .env.example         # Environment variable template
```

## Prerequisites

- Python 3.11 or higher
- Node.js 18 or higher
- MetaTrader 5 (optional, only for live trading)

## Setup & Installation

### 1. Clone the repository

```bash
git clone <repo-url>
cd trading_agents
```

### 2. Create and activate a Python virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
# Core dependencies
pip install -e .

# With LLM support (OpenAI, Anthropic, Gemini)
pip install -e ".[llm]"

# With HuggingFace forecasting models
pip install -e ".[hf]"

# With dev/test tools
pip install -e ".[dev]"

# Everything
pip install -e ".[llm,hf,dev]"
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your settings:

| Variable | Description | Default |
|---|---|---|
| `MT5_LOGIN` | MetaTrader 5 account number | _(optional)_ |
| `MT5_PASSWORD` | MetaTrader 5 password | _(optional)_ |
| `MT5_SERVER` | MetaTrader 5 server name | _(optional)_ |
| `MT5_PATH` | Path to MT5 terminal executable | _(optional)_ |
| `LIVE_TRADING` | Enable live trading (requires MT5) | `false` |
| `OPENAI_API_KEY` | OpenAI API key | _(optional)_ |
| `ANTHROPIC_API_KEY` | Anthropic API key | _(optional)_ |
| `GEMINI_API_KEY` | Google Gemini API key | _(optional)_ |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `HF_TOKEN` | HuggingFace token | _(optional)_ |
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./trading_agents.db` |
| `MAX_RISK_PER_TRADE_PCT` | Max risk per trade (% of equity) | `1.0` |
| `MAX_OPEN_POSITIONS_PER_AGENT` | Max positions per agent | `3` |
| `MAX_OPEN_POSITIONS_GLOBAL` | Max positions across all agents | `10` |
| `MAX_DAILY_LOSS_PCT` | Daily loss limit before kill switch | `5.0` |
| `MAX_LOT_SIZE` | Maximum lot size per order | `1.0` |
| `HOST` | Backend server host | `0.0.0.0` |
| `PORT` | Backend server port | `8000` |

No API keys are required to run in paper trading mode with rule-based strategies (e.g., `no_model` provider).

### 5. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

## Running the Application

### Start the backend

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Start the frontend (in a separate terminal)

```bash
cd frontend
npm run dev
```

### Access the application

| URL | Description |
|---|---|
| http://localhost:5173 | Web dashboard |
| http://localhost:8000/docs | Swagger API docs |
| http://localhost:8000/api/health | Health check |
| ws://localhost:8000/ws | WebSocket (live commentary) |

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# With coverage report
pytest tests/ --cov=backend --cov-report=html
```

## Available Trading Strategies

| Strategy | Key | Description |
|---|---|---|
| MA Crossover | `ma_crossover` | Generates signals on moving average crossovers |
| RSI Mean Reversion | `rsi_reversion` | Buys oversold, sells overbought based on RSI |
| Breakout | `breakout` | Detects price breakouts from consolidation ranges |
| Forecast Driven | `forecast_driven` | Uses ML model predictions to generate signals |
| LLM Discretionary | `llm_discretionary` | Delegates trade decisions to an LLM |

Strategies can be combined per agent using a **Strategy Combiner** with modes: `MAJORITY_VOTE`, `WEIGHTED_SUM`, `OR`, `AND`.

## Agent Configuration

Agents can be created via the web UI or with YAML config files. See `configs/example_agent.yaml`:

```yaml
id: demo-rsi-01
name: RSI Hunter
color: "#E74C3C"
symbols: [EURUSD]
timeframe: H1
model_provider: no_model
model_config: {}
strategies:
  - name: rsi_reversion
    params:
      rsi_period: 14
      oversold: 30
      overbought: 70
      atr_sl_mult: 1.5
      atr_tp_mult: 2.0
risk_profile:
  max_risk_per_trade_pct: 1.0
  max_open_positions: 3
  max_lot_size: 0.1
  max_daily_loss_pct: 5.0
schedule_seconds: 60
enabled: true
```

## Key Features

- **Multi-Agent** — Run multiple independent agents simultaneously, each with its own strategy and risk profile
- **Mandatory Risk Management** — Every order passes through the risk manager; no trade can bypass validation; mandatory stop-loss on all orders
- **Kill Switch** — Automatically closes all positions and stops all agents if the daily loss limit is hit
- **Real-Time Commentary** — Agents stream their reasoning and decisions over WebSocket
- **Backtesting** — Walk-forward analysis engine with performance metrics (Sharpe, max drawdown, win rate)
- **Paper Trading** — Starts with a simulated $10,000 account and synthetic market data by default
- **Live Trading** — Opt-in MetaTrader 5 integration with explicit `LIVE_TRADING=true` flag
- **LLM Integration** — Plug in OpenAI, Claude, Gemini, or a local Ollama model for AI-driven strategies

## API Overview

| Endpoint Group | Base Path | Key Operations |
|---|---|---|
| Agents | `/api/agents` | CRUD, start/stop/pause, commentary |
| Market Data | `/api/market` | Symbols, OHLCV, live prices |
| Risk | `/api/risk` | Limits, open positions |
| Account | `/api/account` | Balance, equity, kill switch |
| Backtest | `/api/backtest` | Run backtests on agent configs |
| Strategies | `/api/strategies` | List available strategies & params |
