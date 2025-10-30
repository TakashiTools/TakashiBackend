Websocket
WebSocket endpoints are available for real-time data streaming and as an alternative to HTTP request sending on the Hyperliquid exchange. The WebSocket URLs by network are:

Mainnet: wss://api.hyperliquid.xyz/ws 


Connecting
To connect to the WebSocket API, you must establish a WebSocket connection to the respective URL based on your desired network. Once connected, you can start sending subscription messages to receive real-time data updates.

Example from command line:

$ wscat -c  wss://api.hyperliquid.xyz/ws
Connected (press CTRL+C to quit)
>  { "method": "subscribe", "subscription": { "type": "trades", "coin": "SOL" } }
< {"channel":"subscriptionResponse","data":{"method":"subscribe","subscription":{"type":"trades","coin":"SOL"}}}


Subscriptions
This page describes subscribing to data streams using the WebSocket API.

Subscription messages
To subscribe to specific data feeds, you need to send a subscription message. The subscription message format is as follows:


Copy
{
  "method": "subscribe",
  "subscription": { ... }
}
The subscription ack provides a snapshot of previous data for time series data (e.g. user fills). These snapshot messages are tagged with isSnapshot: true and can be ignored if the previous messages were already processed.

The subscription object contains the details of the specific feed you want to subscribe to. Choose from the following subscription types and provide the corresponding properties:

allMids:

Subscription message: { "type": "allMids", "dex": "<dex>" }

Data format: AllMids 

The dex field represents the perp dex to source mids from.

Note that the dex field is optional. If not provided, then the first perp dex is used. Spot mids are only included with the first perp dex.

notification:

Subscription message: { "type": "notification", "user": "<address>" }

Data format: Notification

webData2

Subscription message: { "type": "webData2", "user": "<address>" }

Data format: WebData2

candle:

Subscription message: { "type": "candle", "coin": "<coin_symbol>", "interval": "<candle_interval>" }

 Supported intervals: "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "8h", "12h", "1d", "3d", "1w", "1M"

Data format: Candle[]

l2Book:

Subscription message: { "type": "l2Book", "coin": "<coin_symbol>" }

Optional parameters: nSigFigs: int, mantissa: int

Data format: WsBook

trades:

Subscription message: { "type": "trades", "coin": "<coin_symbol>" }

Data format: WsTrade[]

orderUpdates:

Subscription message: { "type": "orderUpdates", "user": "<address>" }

Data format: WsOrder[]

userEvents: 

Subscription message: { "type": "userEvents", "user": "<address>" }

Data format: WsUserEvent

userFills: 

Subscription message: { "type": "userFills", "user": "<address>" }

Optional parameter:  aggregateByTime: bool 

Data format: WsUserFills

userFundings: 

Subscription message: { "type": "userFundings", "user": "<address>" }

Data format: WsUserFundings

userNonFundingLedgerUpdates: 

Subscription message: { "type": "userNonFundingLedgerUpdates", "user": "<address>" }

Data format: WsUserNonFundingLedgerUpdates

activeAssetCtx: 

Subscription message: { "type": "activeAssetCtx", "coin": "coin_symbol>" }

Data format: WsActiveAssetCtx or WsActiveSpotAssetCtx 

activeAssetData: (only supports Perps)

Subscription message: { "type": "activeAssetData", "user": "<address>", "coin": "coin_symbol>" }

Data format: WsActiveAssetData

userTwapSliceFills: 

Subscription message: { "type": "userTwapSliceFills", "user": "<address>" }

Data format: WsUserTwapSliceFills

userTwapHistory: 

Subscription message: { "type": "userTwapHistory", "user": "<address>" }

Data format: WsUserTwapHistory

bbo :

Subscription message: { "type": "bbo", "coin": "<coin>" }

Data format: WsBbo

Data formats
The server will respond to successful subscriptions with a message containing the channel property set to "subscriptionResponse", along with the data field providing the original subscription. The server will then start sending messages with the channel property set to the corresponding subscription type e.g. "allMids" and the data field providing the subscribed data.

The data field format depends on the subscription type:

AllMids: All mid prices.

Format: AllMids { mids: Record<string, string> }

Notification: A notification message.

Format: Notification { notification: string }

WebData2: Aggregate information about a user, used primarily for the frontend.

Format: WebData2

WsTrade[]: An array of trade updates.

Format: WsTrade[]

WsBook: Order book snapshot updates.

Format: WsBook { coin: string; levels: [Array<WsLevel>, Array<WsLevel>]; time: number; }

WsOrder: User order updates.

Format: WsOrder[]

WsUserEvent: User events that are not order updates

Format: WsUserEvent { "fills": [WsFill] | "funding": WsUserFunding | "liquidation": WsLiquidation | "nonUserCancel": [WsNonUserCancel] }

WsUserFills : Fills snapshot followed by streaming fills

WsUserFundings : Funding payments snapshot followed by funding payments on the hour

WsUserNonFundingLedgerUpdates: Ledger updates not including funding payments: withdrawals, deposits, transfers, and liquidations

WsBbo : Bbo updates that are sent only if the bbo changes on a block

For the streaming user endpoints such as WsUserFills,WsUserFundings the first message has isSnapshot: true and the following streaming updates have isSnapshot: false. 

Data type definitions
Here are the definitions of the data types used in the WebSocket API:


Copy
interface WsTrade {
  coin: string;
  side: string;
  px: string;
  sz: string;
  hash: string;
  time: number;
  // tid is 50-bit hash of (buyer_oid, seller_oid). 
  // For a globally unique trade id, use (block_time, coin, tid)
  tid: number;  
  users: [string, string] // [buyer, seller]
}

// Snapshot feed, pushed on each block that is at least 0.5 since last push
interface WsBook {
  coin: string;
  levels: [Array<WsLevel>, Array<WsLevel>];
  time: number;
}

interface WsBbo {
  coin: string;
  time: number;
  bbo: [WsLevel | null, WsLevel | null];
}

interface WsLevel {
  px: string; // price
  sz: string; // size
  n: number; // number of orders
}

interface Notification {
  notification: string;
}

interface AllMids {
  mids: Record<string, string>;
}

interface Candle {
  t: number; // open millis
  T: number; // close millis
  s: string; // coin
  i: string; // interval
  o: number; // open price
  c: number; // close price
  h: number; // high price
  l: number; // low price
  v: number; // volume (base unit)
  n: number; // number of trades
}

type WsUserEvent = {"fills": WsFill[]} | {"funding": WsUserFunding} | {"liquidation": WsLiquidation} | {"nonUserCancel" :WsNonUserCancel[]};

interface WsUserFills {
  isSnapshot?: boolean;
  user: string;
  fills: Array<WsFill>;
}

interface WsFill {
  coin: string;
  px: string; // price
  sz: string; // size
  side: string;
  time: number;
  startPosition: string;
  dir: string; // used for frontend display
  closedPnl: string;
  hash: string; // L1 transaction hash
  oid: number; // order id
  crossed: boolean; // whether order crossed the spread (was taker)
  fee: string; // negative means rebate
  tid: number; // unique trade id
  liquidation?: FillLiquidation;
  feeToken: string; // the token the fee was paid in
  builderFee?: string; // amount paid to builder, also included in fee
}

interface FillLiquidation {
  liquidatedUser?: string;
  markPx: number;
  method: "market" | "backstop";
}

interface WsUserFunding {
  time: number;
  coin: string;
  usdc: string;
  szi: string;
  fundingRate: string;
}

interface WsLiquidation {
  lid: number;
  liquidator: string;
  liquidated_user: string;
  liquidated_ntl_pos: string;
  liquidated_account_value: string;
}

interface WsNonUserCancel {
  coin: String;
  oid: number;
}

interface WsOrder {
  order: WsBasicOrder;
  status: string; // See https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint#query-order-status-by-oid-or-cloid for a list of possible values
  statusTimestamp: number;
}

interface WsBasicOrder {
  coin: string;
  side: string;
  limitPx: string;
  sz: string;
  oid: number;
  timestamp: number;
  origSz: string;
  cloid: string | undefined;
}

interface WsActiveAssetCtx {
  coin: string;
  ctx: PerpsAssetCtx;
}

interface WsActiveSpotAssetCtx {
  coin: string;
  ctx: SpotAssetCtx;
}

type SharedAssetCtx = {
  dayNtlVlm: number;
  prevDayPx: number;
  markPx: number;
  midPx?: number;
};

type PerpsAssetCtx = SharedAssetCtx & {
  funding: number;
  openInterest: number;
  oraclePx: number;
};

type SpotAssetCtx = SharedAssetCtx & {
  circulatingSupply: number;
};

interface WsActiveAssetData {
  user: string;
  coin: string;
  leverage: Leverage;
  maxTradeSzs: [number, number];
  availableToTrade: [number, number];
}

interface WsTwapSliceFill {
  fill: WsFill;
  twapId: number;
}

interface WsUserTwapSliceFills {
  isSnapshot?: boolean;
  user: string;
  twapSliceFills: Array<WsTwapSliceFill>;
}

interface TwapState {
  coin: string;
  user: string;
  side: string;
  sz: number;
  executedSz: number;
  executedNtl: number;
  minutes: number;
  reduceOnly: boolean;
  randomize: boolean;
  timestamp: number;
}

type TwapStatus = "activated" | "terminated" | "finished" | "error";
interface WsTwapHistory {
  state: TwapState;
  status: {
    status: TwapStatus;
    description: string;
  };
  time: number;
}

interface WsUserTwapHistory {
  isSnapshot?: boolean;
  user: string;
  history: Array<WsTwapHistory>;
}
Please note that the above data types are in TypeScript format, and their usage corresponds to the respective subscription types.

Examples
Here are a few examples of subscribing to different feeds using the subscription messages:

Subscribe to all mid prices:


Copy
{ "method": "subscribe", "subscription": { "type": "allMids" } }
Subscribe to notifications for a specific user:


Copy
{ "method": "subscribe", "subscription": { "type": "notification", "user": "<address>" } }
Subscribe to web data for a specific user:


Copy
{ "method": "subscribe", "subscription": { "type": "webData", "user": "<address>" } }
Subscribe to candle updates for a specific coin and interval:


Copy
{ "method": "subscribe", "subscription": { "type": "candle", "coin": "<coin_symbol>", "interval": "<candle_interval>" } }
Subscribe to order book updates for a specific coin:


Copy
{ "method": "subscribe", "subscription": { "type": "l2Book", "coin": "<coin_symbol>" } }
Subscribe to trades for a specific coin:


Copy
{ "method": "subscribe", "subscription": { "type": "trades", "coin": "<coin_symbol>" } }
Unsubscribing from WebSocket feeds
To unsubscribe from a specific data feed on the Hyperliquid WebSocket API, you need to send an unsubscribe message with the following format:


Copy
{
  "method": "unsubscribe",
  "subscription": { ... }
}
The subscription object should match the original subscription message that was sent when subscribing to the feed. This allows the server to identify the specific feed you want to unsubscribe from. By sending this unsubscribe message, you inform the server to stop sending further updates for the specified feed.

Please note that unsubscribing from a specific feed does not affect other subscriptions you may have active at that time. To unsubscribe from multiple feeds, you can send multiple unsubscribe messages, each with the appropriate subscription details.

Timeouts and heartbeats
This page describes the measures to keep WebSocket connections alive.

The server will close any connection if it hasn't sent a message to it in the last 60 seconds. If you are subscribing to a channel that doesn't receive messages every 60 seconds, you can send heartbeat messages to keep your connection alive. The format for these messages are:


Copy
{ "method": "ping" }
The server will respond with:


Copy
{ "channel": "pong" }


Perpetuals
The section documents the info endpoints that are specific to perpetuals. See Rate limits section for rate limiting logic and weights.

Retrieve all perpetual dexs
POST https://api.hyperliquid.xyz/info

Headers
Name
Type
Description
Content-Type*

String

"application/json"

Request Body
Name
Type
Description
type*

String

"perpDexs"

200: OK Successful Response

Copy
[
  null,
  {
    "name": "test",
    "fullName": "test dex",
    "deployer": "0x5e89b26d8d66da9888c835c9bfcc2aa51813e152",
    "oracleUpdater": null,
    "feeRecipient": null,
    "assetToStreamingOiCap": [["COIN1", "100000.0"], ["COIN2", "200000.0"]]
  }
]
Retrieve perpetuals metadata (universe and margin tables)
POST https://api.hyperliquid.xyz/info

Headers
Name
Type
Description
Content-Type*

String

"application/json"

Request Body
Name
Type
Description
type*

String

"meta"

dex

String

Perp dex name. Defaults to the empty string which represents the first perp dex.

200: OK Successful Response

Copy
{
    "universe": [
        {
            "name": "BTC",
            "szDecimals": 5,
            "maxLeverage": 50
        },
        {
            "name": "ETH",
            "szDecimals": 4,
            "maxLeverage": 50
        },
        {
            "name": "HPOS",
            "szDecimals": 0,
            "maxLeverage": 3,
            "onlyIsolated": true
        },
        {
            "name": "LOOM",
            "szDecimals": 1,
            "maxLeverage": 3,
            "onlyIsolated": true,
            "isDelisted": true
        }
    ],
    "marginTables": [
        [
            50,
            {
                "description": "",
                "marginTiers": [
                    {
                        "lowerBound": "0.0",
                        "maxLeverage": 50
                    }
                ]
            }
        ],
        [
            51,
            {
                "description": "tiered 10x",
                "marginTiers": [
                    {
                        "lowerBound": "0.0",
                        "maxLeverage": 10
                    },
                    {
                        "lowerBound": "3000000.0",
                        "maxLeverage": 5
                    }
                ]
            }
        ]
    ]
}
Retrieve perpetuals asset contexts (includes mark price, current funding, open interest, etc.)
POST https://api.hyperliquid.xyz/info

Headers
Name
Type
Description
Content-Type*

String

"application/json"

Request Body
Name
Type
Description
type*

String

"metaAndAssetCtxs"

200: OK Successful Response

Copy
[
{
     "universe": [
        {
            "name": "BTC",
            "szDecimals": 5,
            "maxLeverage": 50
        },
        {
            "name": "ETH",
            "szDecimals": 4,
            "maxLeverage": 50
        },
        {
            "name": "HPOS",
            "szDecimals": 0,
            "maxLeverage": 3,
            "onlyIsolated": true
        }
    ]
},
[
    {
        "dayNtlVlm":"1169046.29406",
         "funding":"0.0000125",
         "impactPxs":[
            "14.3047",
            "14.3444"
         ],
         "markPx":"14.3161",
         "midPx":"14.314",
         "openInterest":"688.11",
         "oraclePx":"14.32",
         "premium":"0.00031774",
         "prevDayPx":"15.322"
    },
    {
         "dayNtlVlm":"1426126.295175",
         "funding":"0.0000125",
         "impactPxs":[
            "6.0386",
            "6.0562"
         ],
         "markPx":"6.0436",
         "midPx":"6.0431",
         "openInterest":"1882.55",
         "oraclePx":"6.0457",
         "premium":"0.00028119",
         "prevDayPx":"6.3611"
      },
      {
         "dayNtlVlm":"809774.565507",
         "funding":"0.0000125",
         "impactPxs":[
            "8.4505",
            "8.4722"
         ],
         "markPx":"8.4542",
         "midPx":"8.4557",
         "openInterest":"2912.05",
         "oraclePx":"8.4585",
         "premium":"0.00033694",
         "prevDayPx":"8.8097"
      }
]
]
Retrieve user's perpetuals account summary
POST https://api.hyperliquid.xyz/info

See a user's open positions and margin summary for perpetuals trading

Headers
Name
Type
Description
Content-Type*

"application/json"

Request Body
Name
Type
Description
type*

String

"clearinghouseState"

user*

String

Onchain address in 42-character hexadecimal format; e.g. 0x0000000000000000000000000000000000000000.

dex

String

Perp dex name. Defaults to the empty string which represents the first perp dex.

200: OK Successful Response

Copy
{
  "assetPositions": [
    {
      "position": {
        "coin": "ETH",
        "cumFunding": {
          "allTime": "514.085417",
          "sinceChange": "0.0",
          "sinceOpen": "0.0"
        },
        "entryPx": "2986.3",
        "leverage": {
          "rawUsd": "-95.059824",
          "type": "isolated",
          "value": 20
        },
        "liquidationPx": "2866.26936529",
        "marginUsed": "4.967826",
        "maxLeverage": 50,
        "positionValue": "100.02765",
        "returnOnEquity": "-0.0026789",
        "szi": "0.0335",
        "unrealizedPnl": "-0.0134"
      },
      "type": "oneWay"
    }
  ],
  "crossMaintenanceMarginUsed": "0.0",
  "crossMarginSummary": {
    "accountValue": "13104.514502",
    "totalMarginUsed": "0.0",
    "totalNtlPos": "0.0",
    "totalRawUsd": "13104.514502"
  },
  "marginSummary": {
    "accountValue": "13109.482328",
    "totalMarginUsed": "4.967826",
    "totalNtlPos": "100.02765",
    "totalRawUsd": "13009.454678"
  },
  "time": 1708622398623,
  "withdrawable": "13104.514502"
}
Retrieve a user's funding history or non-funding ledger updates
POST https://api.hyperliquid.xyz/info

Note: Non-funding ledger updates include deposits, transfers, and withdrawals.

Headers
Name
Type
Description
Content-Type*

String

"application/json"

Request Body
Name
Type
Description
type*

String

"userFunding" or "userNonFundingLedgerUpdates"

user*

String

Address in 42-character hexadecimal format; e.g. 0x0000000000000000000000000000000000000000.

startTime*

int

Start time in milliseconds, inclusive

endTime

int

End time in milliseconds, inclusive. Defaults to current time.

200: OK Successful Response

Copy
[
    {
        "delta": {
            "coin":"ETH",
            "fundingRate":"0.0000417",
            "szi":"49.1477",
            "type":"funding",
            "usdc":"-3.625312"
        },
        "hash":"0xa166e3fa63c25663024b03f2e0da011a00307e4017465df020210d3d432e7cb8",
        "time":1681222254710
    },
    ...
]
Retrieve historical funding rates
POST https://api.hyperliquid.xyz/info

Headers
Name
Type
Description
Content-Type*

String

"application/json"

Request Body
Name
Type
Description
type*

String

"fundingHistory"

coin*

String

Coin, e.g. "ETH"

startTime*

int

Start time in milliseconds, inclusive

endTime

int

End time in milliseconds, inclusive. Defaults to current time.

200: OK

Copy
[
    {
        "coin":"ETH",
        "fundingRate": "-0.00022196",
        "premium": "-0.00052196",
        "time":1683849600076
    }
]
Retrieve predicted funding rates for different venues
POST https://api.hyperliquid.xyz/info

Headers
Name
Type
Description
Content-Type*

String

"application/json"

Request Body
Name
Type
Description
type*

String

"predictedFundings"

200: OK Successful Response

Copy
[
  [
    "AVAX",
    [
      [
        "BinPerp",
        {
          "fundingRate": "0.0001",
          "nextFundingTime": 1733961600000
        }
      ],
      [
        "HlPerp",
        {
          "fundingRate": "0.0000125",
          "nextFundingTime": 1733958000000
        }
      ],
      [
        "BybitPerp",
        {
          "fundingRate": "0.0001",
          "nextFundingTime": 1733961600000
        }
      ]
    ]
  ],...
]
Query perps at open interest caps
POST https://api.hyperliquid.xyz/info

Headers
Name
Type
Description
Content-Type*

String

"application/json"

Request Body
Name
Type
Description
type*

String

"perpsAtOpenInterestCap"

200: OK Successful Response

Copy
["BADGER","CANTO","FTM","LOOM","PURR"]
Retrieve information about the Perp Deploy Auction
POST https://api.hyperliquid.xyz/info

Headers
Name
Type
Description
Content-Type*

String

"application/json"

Request Body
Name
Type
Description
type*

String

"perpDeployAuctionStatus"

200: OK Successful Response

Copy
{
  "startTimeSeconds": 1747656000,
  "durationSeconds": 111600,
  "startGas": "500.0",
  "currentGas": "500.0",
  "endGas": null
}
Retrieve User's Active Asset Data
POST https://api.hyperliquid.xyz/info

Headers
Name
Type
Description
Content-Type*

String

"application/json"

Request Body
Name
Type
Description
type*

String

"activeAssetData"

user*

String

Address in 42-character hexadecimal format; e.g. 0x0000000000000000000000000000000000000000.

coin*

String

Coin, e.g. "ETH". See here for more details.

200: OK

Copy
{
  "user": "0xb65822a30bbaaa68942d6f4c43d78704faeabbbb",
  "coin": "APT",
  "leverage": {
    "type": "cross",
    "value": 3
  },
  "maxTradeSzs": ["24836370.4400000013", "24836370.4400000013"],
  "availableToTrade": ["37019438.0284740031", "37019438.0284740031"],
  "markPx": "4.4716"
}
Retrieve Builder-Deployed Perp Market Limits
POST https://api.hyperliquid.xyz/info

Headers
Name
Type
Description
Content-Type*

String

"application/json"

Request Body
Name
Type
Description
type*

String

"perpDexLimits"

dex*

String

Perp dex name of builder-deployed dex market. The empty string is not allowed.

200: OK

Copy
{
  "totalOiCap": "10000000.0",
  "oiSzCapPerPerp": "10000000000.0",
  "maxTransferNtl": "100000000.0",
  "coinToOiCap": [["COIN1", "100000.0"], ["COIN2", "200000.0"]],
}
Get Perp Market Status
POST https://api.hyperliquid.xyz/info

Headers
Name
Type
Description
Content-Type*

String

"application/json"

Request Body
Name
Type
Description
type*

String

"perpDexStatus"

dex*

String

Perp dex name of builder-deployed dex market. The empty string represents the first perp dex.

200: OK

Copy
{
  "totalNetDeposit": "4103492112.4478230476"
}