# Backend Guide: Adding Binance Proxy Endpoints for Perps Dashboard

## Overview

The Perps Dashboard frontend currently calls Binance API directly. To move these calls through your backend (for rate limiting, caching, CORS, etc.), you need to add proxy endpoints following your existing backend pattern.

## Current Frontend API Calls

The frontend makes 3 types of calls to Binance:

1. **24h Ticker Data** - `GET /fapi/v1/ticker/24hr`
   - Returns: Array of ticker objects for all symbols
   - Used for: Initial chart display, sorting, filtering

2. **Mark Price & Funding Rate** - `GET /fapi/v1/premiumIndex` (no symbol = all symbols)
   - Returns: Array of mark price objects for all symbols
   - Used for: Funding rate sorting

3. **Klines (OHLC)** - `GET /fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}`
   - Returns: Array of candle arrays `[openTime, open, high, low, close, volume, ...]`
   - Used for: Chart data (150 symbols × multiple calls)

## Required Backend Endpoints

Based on your existing backend pattern (`/{exchange}/...`), add these endpoints:

### 1. GET `/binance/tickers/24hr`

**Purpose:** Proxy for Binance 24h ticker data (all symbols)

**Request:**
```
GET /binance/tickers/24hr
```

**Response:** Array of ticker objects (exact Binance format)
```json
[
  {
    "symbol": "BTCUSDT",
    "priceChange": "100.50",
    "priceChangePercent": "1.25",
    "weightedAvgPrice": "8100.00",
    "lastPrice": "8100.00",
    "lastQty": "0.1",
    "openPrice": "8000.00",
    "highPrice": "8200.00",
    "lowPrice": "7900.00",
    "volume": "1000.5",
    "quoteVolume": "8100500.00",
    "openTime": 1234567890000,
    "closeTime": 1234654290000,
    "firstId": 100,
    "lastId": 200,
    "count": 100
  }
]
```

**Backend Implementation (FastAPI):**
```python
@router.get("/binance/tickers/24hr")
async def get_binance_tickers_24hr():
    """
    Proxy endpoint for Binance 24h ticker data.
    Returns ticker statistics for all symbols.
    """
    BINANCE_API = "https://fapi.binance.com/fapi/v1"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BINANCE_API}/ticker/24hr",
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()  # Return as-is
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json() if e.response.headers.get("content-type") == "application/json" else e.response.text
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to Binance API: {str(e)}"
        )
```

**Note:** You could also add caching here (e.g., 5-10 seconds) since this data doesn't change frequently.

---

### 2. GET `/binance/mark-prices`

**Purpose:** Proxy for Binance mark price and funding rate data (all symbols)

**Request:**
```
GET /binance/mark-prices
```

**Response:** Array of mark price objects (exact Binance format)
```json
[
  {
    "symbol": "BTCUSDT",
    "markPrice": "8100.00",
    "indexPrice": "8095.50",
    "estimatedSettlePrice": "8098.00",
    "lastFundingRate": "0.0001",
    "interestRate": "0.0001",
    "nextFundingTime": 1234567890000,
    "time": 1234567890000
  }
]
```

**Backend Implementation (FastAPI):**
```python
@router.get("/binance/mark-prices")
async def get_binance_mark_prices():
    """
    Proxy endpoint for Binance mark price and funding rate data.
    Returns mark price info for all symbols (no symbol parameter = all).
    """
    BINANCE_API = "https://fapi.binance.com/fapi/v1"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BINANCE_API}/premiumIndex",
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()  # Return as-is
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json() if e.response.headers.get("content-type") == "application/json" else e.response.text
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to Binance API: {str(e)}"
        )
```

**Note:** You already have `/binance/funding/{symbol}` for single symbols, but this endpoint returns ALL symbols at once (more efficient for the dashboard).

---

### 3. GET `/binance/klines/{symbol}/{interval}` (Already Exists!)

**Good News:** You already have this endpoint! 

**Existing:** `GET /binance/ohlc/{symbol}/{interval}?limit=...`

**Current Frontend Usage:**
- Calls: `GET /fapi/v1/klines?symbol=BTCUSDT&interval=5m&limit=12`
- Returns: Raw Binance klines format `[[openTime, open, high, low, close, volume, ...], ...]`

**Your Backend Returns:**
- Format: `OHLC[]` objects with structured fields

**Decision Needed:**
You have two options:

#### Option A: Add Raw Klines Endpoint (Keep Frontend Code Simple)
Add a new endpoint that returns raw Binance format:

```python
@router.get("/binance/klines/{symbol}/{interval}")
async def get_binance_klines_raw(
    symbol: str,
    interval: str,
    limit: int = Query(500, ge=1, le=1500)
):
    """
    Proxy endpoint for Binance klines (raw format).
    Returns raw Binance klines array format for compatibility.
    """
    BINANCE_API = "https://fapi.binance.com/fapi/v1"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BINANCE_API}/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()  # Return raw Binance format
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json() if e.response.headers.get("content-type") == "application/json" else e.response.text
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to Binance API: {str(e)}"
        )
```

#### Option B: Use Existing OHLC Endpoint (Requires Frontend Changes)
Modify frontend to use your existing `/binance/ohlc/{symbol}/{interval}` endpoint and transform the `OHLC[]` format to match what the frontend expects.

**Recommendation:** Option A (add raw klines endpoint) - keeps frontend changes minimal.

---

## Summary of Required Endpoints

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/binance/tickers/24hr` | GET | Get all 24h ticker data | **NEED TO ADD** |
| `/binance/mark-prices` | GET | Get all mark price/funding data | **NEED TO ADD** |
| `/binance/klines/{symbol}/{interval}` | GET | Get raw klines data | **NEED TO ADD** (or use existing `/ohlc` with frontend changes) |

---

## Frontend Changes Required

Once backend endpoints are added, update `PerpsDashboardPage.jsx`:

**Before:**
```javascript
const BINANCE_API = "https://fapi.binance.com/fapi/v1";

const fetchTickerData = async () => {
  const response = await axios.get(`${BINANCE_API}/ticker/24hr`);
  return response.data;
};
```

**After:**
```javascript
// Use your backend API base URL (from vite.config.js or env)
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const fetchTickerData = async () => {
  const response = await axios.get(`${API_BASE}/binance/tickers/24hr`);
  return response.data;
};

const fetchMarkPriceData = async () => {
  const response = await axios.get(`${API_BASE}/binance/mark-prices`);
  return response.data;
};

const fetchKlines = async (symbol, range) => {
  const { interval, limit } = getIntervalAndLimitForRange(range);
  const response = await axios.get(
    `${API_BASE}/binance/klines/${symbol}/${interval}`,
    { params: { limit } }
  );
  return response.data;
};
```

---

## Benefits of Backend Proxy

1. **Rate Limiting** - Control API calls centrally
2. **Caching** - Cache ticker/mark price data (changes slowly)
3. **Error Handling** - Centralized error handling and retries
4. **CORS** - No CORS issues
5. **API Key Management** - If Binance requires API keys in future
6. **Monitoring** - Track API usage and errors
7. **Transformation** - Optionally transform data format if needed

---

## Implementation Priority

1. **High Priority:**
   - `/binance/tickers/24hr` - Used immediately on page load
   - `/binance/mark-prices` - Used for sorting

2. **Medium Priority:**
   - `/binance/klines/{symbol}/{interval}` - Used for chart data (can batch/cache)

---

## Testing

Test endpoints match Binance response format:

```bash
# Test tickers
curl "http://localhost:8000/binance/tickers/24hr" | jq '.[0]'

# Test mark prices
curl "http://localhost:8000/binance/mark-prices" | jq '.[0]'

# Test klines
curl "http://localhost:8000/binance/klines/BTCUSDT/5m?limit=12" | jq '.[0]'
```

Expected: Same format as Binance API responses.

