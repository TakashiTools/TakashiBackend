Get Kline
Query for historical klines (also known as candles/candlesticks). Charts are returned in groups based on the requested interval.

Covers: Spot / USDT contract / USDC contract / Inverse contract

HTTP Request
GET /v5/market/kline

Request Parameters
Parameter	Required	Type	Comments
category	false	string	Product type. spot,linear,inverse
When category is not passed, use linear by default
symbol	true	string	Symbol name, like BTCUSDT, uppercase only
interval	true	string	Kline interval. 1,3,5,15,30,60,120,240,360,720,D,W,M
start	false	integer	The start timestamp (ms)
end	false	integer	The end timestamp (ms)
limit	false	integer	Limit for data size per page. [1, 1000]. Default: 200
Response Parameters
Parameter	Type	Comments
category	string	Product type
symbol	string	Symbol name
list	array	
An string array of individual candle
Sort in reverse by startTime
> list[0]: startTime	string	Start time of the candle (ms)
> list[1]: openPrice	string	Open price
> list[2]: highPrice	string	Highest price
> list[3]: lowPrice	string	Lowest price
> list[4]: closePrice	string	Close price. Is the last traded price when the candle is not closed
> list[5]: volume	string	Trade volume
USDT or USDC contract: unit is base coin (e.g., BTC)
Inverse contract: unit is quote coin (e.g., USD)
> list[6]: turnover	string	Turnover.
USDT or USDC contract: unit is quote coin (e.g., USDT)
Inverse contract: unit is base coin (e.g., BTC)
RUN >>
Request Example
HTTP
Python
Go
Java
Node.js
GET /v5/market/kline?category=inverse&symbol=BTCUSD&interval=60&start=1670601600000&end=1670608800000 HTTP/1.1
Host: api-testnet.bybit.com

Response Example
{
    "retCode": 0,
    "retMsg": "OK",
    "result": {
        "symbol": "BTCUSD",
        "category": "inverse",
        "list": [
            [
                "1670608800000",
                "17071",
                "17073",
                "17027",
                "17055.5",
                "268611",
                "15.74462667"
            ],
            [
                "1670605200000",
                "17071.5",
                "17071.5",
                "17061",
                "17071",
                "4177",
                "0.24469757"
            ],
            [
                "1670601600000",
                "17086.5",
                "17088",
                "16978",
                "17071.5",
                "6356",
                "0.37288112"
            ]
        ]
    },
    "retExtInfo": {},
    "time": 1672025956592


    Get Funding Rate History
Query for historical funding rates. Each symbol has a different funding interval. For example, if the interval is 8 hours and the current time is UTC 12, then it returns the last funding rate, which settled at UTC 8.

To query the funding rate interval, please refer to the instruments-info endpoint.

Covers: USDT and USDC perpetual / Inverse perpetual

info
Passing only startTime returns an error.
Passing only endTime returns 200 records up till endTime.
Passing neither returns 200 records up till the current time.
HTTP Request
GET /v5/market/funding/history

Request Parameters
Parameter	Required	Type	Comments
category	true	string	Product type. linear,inverse
symbol	true	string	Symbol name, like BTCUSDT, uppercase only
startTime	false	integer	The start timestamp (ms)
endTime	false	integer	The end timestamp (ms)
limit	false	integer	Limit for data size per page. [1, 200]. Default: 200
Response Parameters
Parameter	Type	Comments
category	string	Product type
list	array	Object
> symbol	string	Symbol name
> fundingRate	string	Funding rate
> fundingRateTimestamp	string	Funding rate timestamp (ms)
RUN >>
Request Example
HTTP
Python
GO
Java
Node.js
GET /v5/market/funding/history?category=linear&symbol=ETHPERP&limit=1 HTTP/1.1
Host: api-testnet.bybit.com

Response Example
{
    "retCode": 0,
    "retMsg": "OK",
    "result": {
        "category": "linear",
        "list": [
            {
                "symbol": "ETHPERP",
                "fundingRate": "0.0001",
                "fundingRateTimestamp": "1672041600000"
            }
        ]
    },
    "retExtInfo": {},
    "time": 1672051897447
}  I THINK THIS CAN BE USED FOR BOTH LIVE AND HISTORIAL??


Get Open Interest
Get the open interest of each symbol.

Covers: USDT contract / USDC contract / Inverse contract

info
The upper limit time you can query is the launch time of the symbol.
HTTP Request
GET /v5/market/open-interest

Request Parameters
Parameter	Required	Type	Comments
category	true	string	Product type. linear,inverse
symbol	true	string	Symbol name, like BTCUSDT, uppercase only
intervalTime	true	string	Interval time. 5min,15min,30min,1h,4h,1d
startTime	false	integer	The start timestamp (ms)
endTime	false	integer	The end timestamp (ms)
limit	false	integer	Limit for data size per page. [1, 200]. Default: 50
cursor	false	string	Cursor. Used to paginate
Response Parameters
Parameter	Type	Comments
category	string	Product type
symbol	string	Symbol name
list	array	Object
> openInterest	string	Open interest. The value is the sum of both sides.
The unit of value, e.g., BTCUSD(inverse) is USD, BTCUSDT(linear) is BTC
> timestamp	string	The timestamp (ms)
nextPageCursor	string	Used to paginate
RUN >>
Request Example
HTTP
Python
GO
Java
Node.js
GET /v5/market/open-interest?category=inverse&symbol=BTCUSD&intervalTime=5min&startTime=1669571100000&endTime=1669571400000 HTTP/1.1
Host: api-testnet.bybit.com

Response Example
{
    "retCode": 0,
    "retMsg": "OK",
    "result": {
        "symbol": "BTCUSD",
        "category": "inverse",
        "list": [
            {
                "openInterest": "461134384.00000000",
                "timestamp": "1669571400000"
            },
            {
                "openInterest": "461134292.00000000",
                "timestamp": "1669571100000"
            }
        ],
        "nextPageCursor": ""
    },
    "retExtInfo": {},
    "time": 1672053548579
}


FOR WS


onnect
WebSocket public stream:

Mainnet:
Spot: wss://stream.bybit.com/v5/public/spot
USDT, USDC perpetual & USDT Futures: wss://stream.bybit.com/v5/public/linear
Inverse contract: wss://stream.bybit.com/v5/public/inverse
Spread trading: wss://stream.bybit.com/v5/public/spread
USDT/USDC Options: wss://stream.bybit.com/v5/public/option

IP Limits
Do not frequently connect and disconnect the connection.
Do not build over 500 connections in 5 minutes. This is counted per WebSocket domain.
Public channel - Args limits
Regardless of Perpetual, Futures, Options or Spot, for one public connection, you cannot have length of "args" array over 21,000 characters.

Spot can input up to 10 args for each subscription request sent to one connection
Options can input up to 2000 args for a single connection
No args limit for Futures and Spread for now
How to Send the Heartbeat Packet
How to Send

// req_id is a customised ID, which is optional
ws.send(JSON.stringify({"req_id": "100001", "op": "ping"}));

Pong message example of public channels

Spot
Linear/Inverse
Option/Spread
{
    "success": true,
    "ret_msg": "pong",
    "conn_id": "0970e817-426e-429a-a679-ff7f55e0b16a",
    "op": "ping"
}

Pong message example of private channels

{
    "req_id": "test",
    "op": "pong",
    "args": [
        "1675418560633"
    ],
    "conn_id": "cfcb4ocsvfriu23r3er0-1b"
}

caution
To avoid network or program issues, we recommend that you send the ping heartbeat packet every 20 seconds to maintain the WebSocket connection.

How to Subscribe to Topics
Understanding WebSocket Filters
How to subscribe with a filter

// Subscribing level 1 orderbook
{
    "req_id": "test", // optional
    "op": "subscribe",
    "args": [
        "orderbook.1.BTCUSDT"
    ]
}

Subscribing with multiple symbols and topics is supported.

{
    "req_id": "test", // optional
    "op": "subscribe",
    "args": [
        "orderbook.1.BTCUSDT",
        "publicTrade.BTCUSDT",
        "orderbook.1.ETHUSDT"
    ]
}

Understanding WebSocket Filters: Unsubscription
You can dynamically subscribe and unsubscribe from topics without unsubscribing from the WebSocket like so:

{
    "op": "unsubscribe",
    "args": [
        "publicTrade.ETHUSD"
    ],
    "req_id": "customised_id"
}

Understanding the Subscription Response
Topic subscription response message example

Private
Public Spot
Linear/Inverse
Option/Spread
{
    "success": true,
    "ret_msg": "",
    "op": "subscribe",
    "conn_id": "cejreassvfrsfvb9v1a0-2m"
}



LIQUIDATIONS 

All Liquidation
Subscribe to the liquidation stream, push all liquidations that occur on Bybit.

Covers: USDT contract / USDC contract / Inverse contract

Push frequency: 500ms

Topic:
allLiquidation.{symbol} e.g., allLiquidation.BTCUSDT

Response Parameters
Parameter	Type	Comments
topic	string	Topic name
type	string	Data type. snapshot
ts	number	The timestamp (ms) that the system generates the data
data	Object	
> T	number	The updated timestamp (ms)
> s	string	Symbol name
> S	string	Position side. Buy,Sell. When you receive a Buy update, this means that a long position has been liquidated
> v	string	Executed size
> p	string	Bankruptcy price
Subscribe Example
from pybit.unified_trading import WebSocket
from time import sleep
ws = WebSocket(
    testnet=True,
    channel_type="linear",
)
def handle_message(message):
    print(message)
ws.all_liquidation_stream("ROSEUSDT", handle_message)
while True:
    sleep(1)

Message Example
{
    "topic": "allLiquidation.ROSEUSDT",
    "type": "snapshot",
    "ts": 1739502303204,
    "data": [
        {
            "T": 1739502302929,
            "s": "ROSEUSDT",
            "S": "Sell",
            "v": "20000",
            "p": "0.04499"
        }
    ]
}

BIG TRADES

Trade
Subscribe to the recent trades stream.

After subscription, you will be pushed trade messages in real-time.

Push frequency: real-time

Topic:
publicTrade.{symbol}
Note: option uses baseCoin, e.g., publicTrade.BTC

note
For Futures and Spot, a single message may have up to 1024 trades. As such, multiple messages may be sent for the same seq.

Response Parameters
Parameter	Type	Comments
id	string	Message id. Unique field for option
topic	string	Topic name
type	string	Data type. snapshot
ts	number	The timestamp (ms) that the system generates the data
data	array	Object. Sorted by the time the trade was matched in ascending order
> T	number	The timestamp (ms) that the order is filled
> s	string	Symbol name
> S	string	Side of taker. Buy,Sell
> v	string	Trade size
> p	string	Trade price
> L	string	Direction of price change. Unique field for Perps & futures
> i	string	Trade ID
> BT	boolean	Whether it is a block trade order or not
> RPI	boolean	Whether it is a RPI trade or not
> seq	integer	cross sequence
> mP	string	Mark price, unique field for option
> iP	string	Index price, unique field for option
> mIv	string	Mark iv, unique field for option
> iv	string	iv, unique field for option
Subscribe Example
from pybit.unified_trading import WebSocket
from time import sleep
ws = WebSocket(
    testnet=True,
    channel_type="linear",
)
def handle_message(message):
    print(message)
ws.trade_stream(
    symbol="BTCUSDT",
    callback=handle_message
)
while True:
    sleep(1)

Response Example
{
    "topic": "publicTrade.BTCUSDT",
    "type": "snapshot",
    "ts": 1672304486868,
    "data": [
        {
            "T": 1672304486865,
            "s": "BTCUSDT",
            "S": "Buy",
            "v": "0.001",
            "p": "16578.50",
            "L": "PlusTick",
            "i": "20f43950-d8dd-5b31-9112-a178eb6023af",
            "BT": false,
            "seq": 1783284617
        }
    ]
}