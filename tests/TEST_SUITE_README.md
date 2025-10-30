# 🧪 Comprehensive Exchange Test Suite

This test suite provides comprehensive testing for all registered exchanges in the trading backend system.

## 📋 Features

- **REST API Testing**: OHLC, Open Interest, Funding Rates
- **WebSocket Testing**: Real-time streams with timeout handling
- **Health Checks**: Exchange connectivity verification
- **Detailed Reporting**: JSON results with analysis tools
- **Flexible Configuration**: Test specific exchanges or skip certain tests

## 🚀 Quick Start

### Run All Tests
```bash
python test_all_exchanges.py
```

### Test Specific Exchanges
```bash
python test_all_exchanges.py --exchanges binance,bybit
```

### Skip WebSocket Tests
```bash
python test_all_exchanges.py --skip-ws
```

### Custom Output File
```bash
python test_all_exchanges.py --output my_results.json
```

## 📊 Analyzing Results

### View Analysis
```bash
python analyze_test_results.py test_results.json
```

### Detailed Analysis
```bash
python analyze_test_results.py test_results.json --detailed
```

### Export Summary
```bash
python analyze_test_results.py test_results.json --export
```

## 📁 Output Files

- **`test_results.json`**: Complete test results in JSON format
- **`test_summary.txt`**: Human-readable summary (when using --export)

## 🔍 Test Coverage

### REST API Endpoints
- ✅ **OHLC Data**: Historical candlestick data
- ✅ **Open Interest**: Futures market open interest
- ✅ **Funding Rates**: Perpetual futures funding rates

### WebSocket Streams
- ✅ **OHLC Stream**: Real-time candlestick updates
- ✅ **Trades Stream**: Live trade execution data
- ✅ **Liquidations Stream**: Liquidation events

### Exchange Features
- ✅ **Health Checks**: API connectivity verification
- ✅ **Capabilities**: Feature support detection
- ✅ **Error Handling**: Comprehensive error reporting

## 📈 Sample Output

```
📊 TEST SUMMARY
================================================================================
🕐 Test Run: 2024-01-15T10:30:00Z
🏢 Exchanges Tested: 3
🧪 Total Tests: 18
✅ Passed: 15
❌ Failed: 2
⏭️  Skipped: 1
📈 Success Rate: 83.3%

📋 Exchange Details:
--------------------------------------------------------------------------------

🔍 BINANCE:
  Health: ✅ healthy
  Tests: 6✅ 0❌ 0⏭️
  Features: ohlc, funding_rate, open_interest, liquidations, large_trades

🔍 BYBIT:
  Health: ✅ healthy
  Tests: 5✅ 1❌ 0⏭️
  Features: ohlc, funding_rate, open_interest, liquidations, large_trades

🔍 HYPERLIQUID:
  Health: ✅ healthy
  Tests: 4✅ 0❌ 2⏭️
  Features: ohlc, funding_rate, open_interest, large_trades
```

## 🛠️ Command Line Options

### test_all_exchanges.py
- `--exchanges`: Comma-separated list of exchanges to test
- `--output`: Output file for test results (default: test_results.json)
- `--skip-ws`: Skip WebSocket tests
- `--verbose`: Enable verbose logging

### analyze_test_results.py
- `results_file`: Path to test results JSON file
- `--detailed`: Show detailed analysis
- `--export`: Export summary to text file

## 🔧 Troubleshooting

### Common Issues

1. **WebSocket Timeouts**: Some exchanges may have slower WebSocket responses
   - Solution: Increase timeout in test configuration

2. **API Rate Limits**: Exchanges may throttle requests
   - Solution: Add delays between tests or use testnet endpoints

3. **Missing Dependencies**: Required packages not installed
   - Solution: Install requirements: `pip install -r requirements.txt`

### Debug Mode

Enable verbose logging to see detailed test execution:
```bash
python test_all_exchanges.py --verbose
```

## 📝 Test Results Format

The JSON output includes:
- Test run metadata (timestamp, statistics)
- Per-exchange results (health, capabilities, test outcomes)
- Detailed error messages and data samples
- WebSocket message counts and timeouts

## 🤝 Contributing

To add new test cases:
1. Extend the `ExchangeTestSuite` class
2. Add new test methods following the existing pattern
3. Update the analysis tools if needed
4. Test with all supported exchanges

## 📚 Related Files

- `test_all_exchanges.py`: Main test suite
- `analyze_test_results.py`: Results analyzer
- `test_bybit.py`: Bybit-specific tests
- `test_hyperliquid.py`: Hyperliquid-specific tests
- `core/exchange_manager.py`: Exchange management
- `core/exchange_interface.py`: Exchange interface definition
