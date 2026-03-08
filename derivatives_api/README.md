# Xmore Derivatives Pricing API

FastAPI service wrapping the `derivatives/` module. Runs as a separate Render worker service. The Express server (`web-ui/server.js`) proxies to it internally via `DERIVATIVES_API_URL`.

## Run locally

```bash
cd d:/Moto/Xmore
uvicorn derivatives_api.main:app --reload --port 8001
```

API docs auto-generated at: http://localhost:8001/docs

## Render configuration

Add a second service entry in `render.yaml`:

```yaml
- type: web
  name: xmore-derivatives-api
  env: python
  buildCommand: pip install -r derivatives_api/requirements.txt -r requirements.txt
  startCommand: uvicorn derivatives_api.main:app --host 0.0.0.0 --port $PORT
  envVars:
    - key: PYTHON_VERSION
      value: "3.11"
```

Then add `DERIVATIVES_API_URL` to the main `trading-dashboard` service environment variables, pointing to the internal URL of the `xmore-derivatives-api` service (e.g. `https://xmore-derivatives-api.onrender.com`).

## Key endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/price/bsm` | Black-Scholes-Merton price + full Greeks (delta, gamma, theta, vega, rho, vanna, volga) |
| POST | `/price/binomial` | CRR binomial tree (European & American) |
| POST | `/price/asian` | Monte Carlo Asian option (arithmetic or geometric averaging) |
| POST | `/price/barrier` | Monte Carlo barrier option (up/down, in/out) |
| GET | `/brief/{ticker}` | Human-readable options brief: ATM call/put prices, straddle cost, delta, theta, vega |

All POST endpoints accept JSON bodies matching the schemas in `derivatives_api/schemas.py`. Interactive docs (Swagger UI) are available at `/docs`.
