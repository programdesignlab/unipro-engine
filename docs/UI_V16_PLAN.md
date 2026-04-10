# MomentumEdge — v16 UI Implementation Plan

## Current State

The frontend at `/Users/arvbsnt/Developer/uniproai` is a **pnpm + Turbo monorepo** with:
- `apps/web` — React 19 + Vite + React Router v7
- `packages/ui` — Shared components (shadcn-style, Base UI + CVA + Tailwind v4)
- 7 pages: Dashboard, Watchlist, Stock Detail, Sectors, Screener, Market Regime, Sign In
- 8 API hooks consuming the v7 backend
- OKLch theme system with dark/light mode

**Goal:** Add v16 features to the existing UI. Keep the same look and feel. No redesign — extend what's there.

---

## What's New in v16 Backend (4 new endpoints + changes to existing)

### New Endpoints
| Endpoint | Data |
|----------|------|
| `GET /api/v1/strategy/info` | Strategy name, version, hash, feature flags |
| `GET /api/v1/strategy/params` | Full YAML config as JSON |
| `GET /api/v1/exclusions` | Why stocks were filtered out (audit trail) |
| `GET /api/v1/turnaround-watch` | Early turnaround candidates |

### Changed Endpoints
| Endpoint | What Changed |
|----------|-------------|
| `/api/v1/scores/{symbol}` | New field: `strategy_hash` |
| `/api/v1/watchlist` | Score ranges changed: fundamental -20/+30 (was -5/+20) |
| `/api/v1/regime` | Regime classifications now from YAML (same 5 levels) |

---

## Implementation Plan

### Phase A: Types + API Hooks + Utils (foundation)

**Files to modify:**

#### 1. `apps/web/src/lib/types.ts` — Add new interfaces

```typescript
// NEW types
interface StrategyInfo {
  name: string;
  version: string;
  description: string;
  strategy_hash: string;
  exit_framework: string;
  hard_blocks: number;
  scoring_modules: number;
  exit_phases: number;
  cascade_layers: number;
  monster_enabled: boolean;
  fast_crash_enabled: boolean;
}

interface ExclusionEntry {
  date: string;
  symbol: string;
  block_name: string;
  reason: string;
  data_missing: boolean;
  strategy_hash: string;
}

interface TurnaroundCandidate {
  stock_id: number;
  symbol: string;
  sector: string;
  detected_date: string;
  eps_trend: (number | null)[];
  revenue_growth_yoy: number | null;
  suppressed: boolean;
  suppression_reason: string | null;
  status: string;
}

// UPDATE existing
interface WatchlistEntry {
  // ... existing fields ...
  strategy_hash?: string;        // NEW
}

interface ScoreBreakdown {
  // ... existing fields ...
  strategy_hash?: string;        // NEW
}
```

#### 2. `apps/web/src/lib/api.ts` — Add 4 new hooks

```typescript
export function useStrategyInfo()     // → GET /api/v1/strategy/info
export function useExclusions(date?)  // → GET /api/v1/exclusions?date=...
export function useTurnaroundWatch()  // → GET /api/v1/turnaround-watch
export function useStrategyParams()   // → GET /api/v1/strategy/params
```

#### 3. `apps/web/src/lib/utils.ts` — Update score ranges

```typescript
// UPDATE compositeScorePct — new fundamental range is wider
// UPDATE regimeAllocation — add portfolio_heat from strategy
// ADD: formatStrategyHash(hash) → truncated display
// ADD: exclusionReasonLabel(reason) → human-readable
// ADD: turnaroundStatusColor(status) → color mapping
```

---

### Phase B: Update Existing Pages

#### 4. Dashboard (`pages/dashboard.tsx`)

**Add:**
- Strategy version badge in header area (small pill: "v16.0.0 [1e0974f]")
- Fast crash warning banner (if regime signals show crash — already has crash_warning field)
- Update fundamental score range display from ±20 to -20/+30 in score distribution

**No structural changes** — dashboard layout stays the same.

#### 5. Watchlist (`pages/watchlist.tsx`)

**Add:**
- `strategy_hash` column (compact, last 8 chars) — optional, can be tooltip
- Update fundamental_bonus display to handle -20/+30 range
- Score bar needs wider fundamental range

**Modify `components/score-bar.tsx`:**
- `StackedScoreBar` — update fundamental max from 20 to 30, min from -5 to -20
- `ScoreGauge` for fundamental — update min/max props

#### 6. Stock Detail (`pages/stock-detail.tsx`)

**Add to Scores tab:**
- Strategy hash badge
- Monster score display (if > 0) — small card or badge showing monster score + active/inactive
- Gain phase indicator (prove_it / let_it_run / working_compounder / monster_run) — if position exists

**Add to Fundamentals tab:**
- New signals visible: PEAD/SUE, promoter buying/selling, OCF quality, debtors
- Expand the score gauge range to -20/+30

**No structural changes** — keep the 4-tab layout.

#### 7. Market Regime (`pages/market-regime.tsx`)

**Add:**
- Fast crash detector status card (enabled/disabled, last triggered, threshold)
- Bull entry protocol status (if recovering from Bear — show current phase B1-B4)
- Strategy info card (version, hash, exit framework)

**Update:**
- Position Sizing Rules grid — add portfolio_heat column
- Breadth signals — values unchanged, display same

#### 8. Screener (`pages/screener.tsx`)

**Add columns (from new Stock fields):**
- `pledge_pct` — promoter pledge %
- `beta` — stock beta
- `is_psu` — PSU badge

**Add filter:**
- PSU/non-PSU filter option

---

### Phase C: New Pages

#### 9. Exclusions Page (NEW)

**Route:** `/exclusions`

**Layout:**
- Date picker (defaults to latest)
- Table: date | symbol | block_name | reason | data_missing badge
- Filter by block name (dropdown: market_cap, liquidity, surveillance, eps_junk, ocf_quality, pledge, sebi_fine, ipo_age)
- Summary stats: total excluded, by-block breakdown (small bar chart or badges)

**Components needed:** Reuse existing Table from `packages/ui`, Badge, Select.

#### 10. Turnaround Watch Page (NEW)

**Route:** `/turnaround`

**Layout:**
- Card grid or table of candidates
- Per candidate: symbol, sector, detected_date, revenue_growth, EPS trend sparkline
- Suppressed entries shown greyed out with reason badge
- Status badge: watching / cleared / expired

**Components needed:** Table, Badge, small sparkline (could be a simple CSS bar chart of 8 EPS values).

#### 11. Strategy Page (NEW — optional, could be part of settings)

**Route:** `/strategy`

**Layout:**
- Strategy info card (name, version, hash, feature flags)
- Collapsible sections showing YAML config as formatted JSON
- Read-only — no editing

---

### Phase D: Navigation + Wiring

#### 12. `components/layout.tsx`

**Update header nav:**
- Add "Exclusions" link
- Add "Turnaround" link
- Add strategy version pill in header (right side, near theme toggle)

#### 13. `App.tsx`

**Add routes:**
```tsx
<Route path="/exclusions" element={<ExclusionsPage />} />
<Route path="/turnaround" element={<TurnaroundPage />} />
<Route path="/strategy" element={<StrategyPage />} />
```

---

## File Change Summary

| File | Action | Complexity |
|------|--------|------------|
| `lib/types.ts` | Add 3 interfaces, update 2 | S |
| `lib/api.ts` | Add 4 hooks | S |
| `lib/utils.ts` | Update score ranges, add 3 helpers | S |
| `components/score-bar.tsx` | Update fundamental range | S |
| `pages/dashboard.tsx` | Add strategy badge, crash banner | S |
| `pages/watchlist.tsx` | Update score ranges | S |
| `pages/stock-detail.tsx` | Add monster/phase display, widen fundamental gauge | M |
| `pages/market-regime.tsx` | Add fast crash card, bull entry status, strategy info | M |
| `pages/screener.tsx` | Add pledge/beta/PSU columns + filter | S |
| `pages/exclusions.tsx` | **NEW** — exclusion audit table | M |
| `pages/turnaround.tsx` | **NEW** — turnaround watch cards | M |
| `pages/strategy.tsx` | **NEW** — strategy info display | S |
| `components/layout.tsx` | Add nav links, strategy pill | S |
| `App.tsx` | Add 3 routes | S |

**Total: 14 file changes (3 new pages, 11 updates)**

---

## Build Order

1. **Phase A** (types + hooks + utils) — no visible changes, just wiring
2. **Phase B** (update existing pages) — incremental, each page independent
3. **Phase C** (new pages) — can be done in parallel
4. **Phase D** (navigation) — final wiring

Phases B and C can be parallelized. Each page update is independent.

---

## What Stays the Same

- Overall layout structure (header + content area)
- Color system (OKLch theme, regime colors, score heat maps)
- Component library (Card, Table, Badge, Tabs, Select, Button)
- Authentication flow (better-auth + JWT)
- Responsive design approach
- Dark/light theme toggle
- All existing pages keep their structure — only extended
