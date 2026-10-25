# Integration review: what was found and fixed

## Bugs
| # | Where | Problem | Fix |
|---|---|---|---|
# Integration review: what was found and fixed

## Bugs
| # | Where | Problem | Fix |
|---|---|---|---|
| 1 | `frontend/src/hooks/useAsync.ts` | `alive` ref never reset to `true`; React StrictMode (on in `main.tsx`) unmounts/remounts in dev, so **every page hung on loading in `npm run dev`** | Reset on mount. Regression test `useAsync.test.tsx` (fails on the old code) |
| 2 | `/hygiene/frames` | UI allows 1-120 frames, API accepted 1-60 -> 422 | Limit aligned to 120; test |
| 3 | `config.py` | `.env` read from the cwd, re-read on every call and leaked into `os.environ`; a real `.env` broke a unit test | Loaded once from `backend/.env`; `FOODVERSE_SKIP_DOTENV`; tests isolated |
| 4 | LLM client | `content: null`/list/empty, truncated reasoning output, non-object JSON caused 500s | Clear `ProviderError`s and fallbacks; tests |
| 5 | Photo features with a text-only model (e.g. Groq `gpt-oss-20b`) | Every photo request failed with HTTP 400 | `LLM_VISION_MODEL`; features reported "not configured" instead of failing |
| 6 | Intake log / dashboard | "Today" used the server clock: wrong day for users ahead of a UTC host; logging could be rejected as "future date" | Client sends local date; server tolerates +1 day; `?today=` on dashboard |
| 7 | `Freshness.tsx` | duplicate React keys | Index added |
| 8 | `api.ts` | 30 s default timeout < 45 s LLM timeout; manual multipart header | 60 s; header removed |
| 9 | `/kitchen/scale` | malformed recipe -> 500 | Validated -> 422 |
| 10 | Health probes | `HEAD` returned 405 | GET+HEAD, plus dependency-free `/healthz` |
| 11 | `CORS_ORIGINS` | trailing slash silently never matched | Normalised |

| 12 | Freshness | Colour heuristic flagged a fresh multi-dish meal on a dark table as "signs of deterioration" | With a vision model configured, the AI judges the photo (safety rules enforced in code: no positive verdict for meat/fish/dairy/cooked meals, deterioration needs a named visible sign, never "safe"). The colour fallback now returns "uncertain" for cooked/other foods. Tests added |

## Deployment readiness added
Dockerfiles (non-root, healthcheck, workers + proxy headers), `docker-compose.yml`, nginx (SPA fallback, `/api` proxy,
upload limit, caching, security headers), Netlify/Vercel rewrites, SQLite WAL + busy timeout, per-IP rate limiting,
request-size guard (413), docs off in production, startup config warnings, bounded dependency ranges (unused `pandas`
removed), GitHub Actions CI, `.env` ignore rules.

## Verified
Backend 124 tests, frontend 6 tests, typecheck, production build; every endpoint exercised with the UI's payloads against
a production-mode backend (2 workers) behind real nginx serving the built frontend.
Not verified: the Docker images themselves (no Docker in the sandbox), live Groq/Gemini calls, real food photos.
| 2 | `/hygiene/frames` | UI allows 1-120 frames, API accepted 1-60 -> 422 | Limit aligned to 120; test |
| 3 | `config.py` | `.env` read from the cwd, re-read on every call and leaked into `os.environ`; a real `.env` broke a unit test | Loaded once from `backend/.env`; `FOODVERSE_SKIP_DOTENV`; tests isolated |
| 4 | LLM client | `content: null`/list/empty, truncated reasoning output, non-object JSON caused 500s | Clear `ProviderError`s and fallbacks; tests |
| 5 | Photo features with a text-only model (e.g. Groq `gpt-oss-20b`) | Every photo request failed with HTTP 400 | `LLM_VISION_MODEL`; features reported "not configured" instead of failing |
| 6 | Intake log / dashboard | "Today" used the server clock: wrong day for users ahead of a UTC host; logging could be rejected as "future date" | Client sends local date; server tolerates +1 day; `?today=` on dashboard |
| 7 | `Freshness.tsx` | duplicate React keys | Index added |
| 8 | `api.ts` | 30 s default timeout < 45 s LLM timeout; manual multipart header | 60 s; header removed |
| 9 | `/kitchen/scale` | malformed recipe -> 500 | Validated -> 422 |
| 10 | Health probes | `HEAD` returned 405 | GET+HEAD, plus dependency-free `/healthz` |
| 11 | `CORS_ORIGINS` | trailing slash silently never matched | Normalised |

## Deployment readiness added
Dockerfiles (non-root, healthcheck, workers + proxy headers), `docker-compose.yml`, nginx (SPA fallback, `/api` proxy,
upload limit, caching, security headers), Netlify/Vercel rewrites, SQLite WAL + busy timeout, per-IP rate limiting,
request-size guard (413), docs off in production, startup config warnings, bounded dependency ranges (unused `pandas`
removed), GitHub Actions CI, `.env` ignore rules.

## Verified
Backend 124 tests, frontend 6 tests, typecheck, production build; every endpoint exercised with the UI's payloads against
a production-mode backend (2 workers) behind real nginx serving the built frontend.
Not verified: the Docker images themselves (no Docker in the sandbox), live Groq/Gemini calls, real food photos.
