# Frontend verification procedure

Automated: `cd frontend && npm test` (Vitest: API envelope validation and error normalisation) and `npm run typecheck`.
Everything below is a **manual checklist**; run it with the backend up (and again with it stopped).

## API error states
| Scenario | How to trigger | Expected |
|---|---|---|
| Backend down | Stop uvicorn, reload any page | Sidebar shows "API unreachable"; Overview shows an error alert with Retry; no blank screen |
| Unsupported file | Drop a `.gif` / `.pdf` on any dropzone | Inline error before any request is sent |
| Oversize file | Pick an image larger than the limit shown in Settings | Inline error naming the limit |
| Server rejects file | Rename a text file to `.png` and upload | Alert with the server's message (HTTP 415/422) |
| Timeout | Throttle network to offline mid-upload | "Request timed out / cannot reach" alert, buttons re-enabled |
| Malformed response | Point `VITE_API_BASE_URL` at a non-FoodVerse JSON server | "Unexpected format" alert, nothing rendered as a result |
| No providers | Leave `LLM_PROVIDER=none` and no weights | Food: "no model configured" + manual picker; Kitchen: amber "local fallback" label; Hygiene: "no detector" and score "-" |
| Impossible allergies | Meal Planner: vegan + soy, gluten, nuts, sesame + many avoids | "Please adjust your preferences" alert; no plan produced |

## Flows
1. Food Scanner: upload -> result (or manual selection) -> Save -> appears in Reports -> Log -> appears on Overview "Today".
2. Freshness: upload with category "meat" -> never "No visible deterioration"; safety notice always visible.
3. Hygiene: upload video -> Preview frames -> Analyse -> Download report -> Save.
4. Kitchen: find recipes -> change servings (quantities update) -> tick steps -> chat -> Save recipe.
5. Meal Planner: save profile -> generate weekly -> swap a meal -> tick shopping items -> reload page (state persists).
6. Reports: filter, expand, download JSON, delete.

## Responsive & accessibility
- Widths 360 px, 768 px, 1280 px: sidebar becomes a drawer below 1024 px; no horizontal scroll; cards stack.
- Keyboard only: Tab reaches the skip link, nav, dropzones (Enter/Space opens picker), tabs, and all buttons with a visible focus ring.
- Toggle dark mode and check contrast on badges and alerts. OS "reduce motion" disables transitions.
- Screen reader: results regions are `aria-live`, progress bars expose `role=progressbar`, charts have text labels.
