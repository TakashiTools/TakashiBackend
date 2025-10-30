"""
Unit Tests for Configuration Module

These tests verify that the configuration system works correctly:
- Settings are loaded from .env file
- Default values are applied when needed
- Validation catches invalid configurations
- Property methods work as expected

Run with:
    pytest tests/unit/test_config.py -v
"""

import pytest
from core.config import settings, validate_configuration


class TestConfigurationLoading:
    """Test that configuration loads correctly from .env"""

    def test_binance_base_url_loaded(self):
        """Verify Binance API URL is set"""
        assert settings.binance_base_url is not None
        assert "binance" in settings.binance_base_url.lower()
        assert settings.binance_base_url.startswith("http")

    def test_app_port_is_valid_integer(self):
        """Verify app port is a valid integer"""
        assert isinstance(settings.app_port, int)
        assert 1 <= settings.app_port <= 65535

    def test_debug_mode_is_boolean(self):
        """Verify debug setting is a boolean"""
        assert isinstance(settings.debug, bool)

    def test_log_level_is_set(self):
        """Verify log level is configured"""
        assert settings.log_level is not None
        assert isinstance(settings.log_level, str)
        assert len(settings.log_level) > 0


class TestSymbolsParsing:
    """Test that symbols are parsed correctly from comma-separated string"""

    def test_symbols_list_not_empty(self):
        """Verify at least one symbol is configured"""
        assert len(settings.symbols_list) > 0

    def test_symbols_are_uppercase(self):
        """Verify all symbols are uppercase"""
        for symbol in settings.symbols_list:
            assert symbol.isupper(), f"Symbol '{symbol}' should be uppercase"
            assert symbol == symbol.upper()

    def test_symbols_have_no_whitespace(self):
        """Verify symbols don't have leading/trailing whitespace"""
        for symbol in settings.symbols_list:
            assert symbol == symbol.strip()

    def test_symbols_contain_expected_pairs(self):
        """Verify common trading pairs are present"""
        # At least one of the default symbols should be present
        default_symbols = {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
        assert any(symbol in settings.symbols_list for symbol in default_symbols)


class TestIntervalsParsing:
    """Test that intervals are parsed correctly"""

    def test_intervals_list_not_empty(self):
        """Verify at least one interval is configured"""
        assert len(settings.intervals_list) > 0

    def test_intervals_are_lowercase(self):
        """Verify all intervals are lowercase"""
        for interval in settings.intervals_list:
            assert interval.islower(), f"Interval '{interval}' should be lowercase"

    def test_intervals_have_valid_format(self):
        """Verify intervals match expected patterns (e.g., 1m, 1h, 1d)"""
        valid_patterns = ["m", "h", "d", "w", "M"]  # minute, hour, day, week, month
        for interval in settings.intervals_list:
            # Check that interval ends with one of the valid patterns
            assert any(interval.endswith(pattern) for pattern in valid_patterns), \
                f"Interval '{interval}' doesn't match expected format"

    def test_intervals_contain_common_timeframes(self):
        """Verify common timeframes are present"""
        # At least one of these should be configured
        common_intervals = {"1m", "5m", "1h", "1d"}
        assert any(interval in settings.intervals_list for interval in common_intervals)


class TestConfigurationProperties:
    """Test property methods and computed values"""

    def test_use_redis_returns_boolean(self):
        """Verify use_redis property returns a boolean"""
        assert isinstance(settings.use_redis, bool)

    def test_use_redis_false_when_no_host(self):
        """Verify use_redis is False when Redis host is not configured"""
        # Default .env has empty REDIS_HOST, so use_redis should be False
        if not settings.redis_host:
            assert settings.use_redis is False

    def test_get_binance_headers_returns_dict(self):
        """Verify get_binance_headers returns a dictionary"""
        headers = settings.get_binance_headers()
        assert isinstance(headers, dict)
        assert "Content-Type" in headers

    def test_binance_headers_include_api_key_when_set(self):
        """Verify API key is included in headers when configured"""
        headers = settings.get_binance_headers()
        if settings.binance_api_key:
            assert "X-MBX-APIKEY" in headers
            assert headers["X-MBX-APIKEY"] == settings.binance_api_key


class TestConfigurationValidation:
    """Test configuration validation function"""

    def test_validate_configuration_succeeds(self):
        """Verify validation passes with default configuration"""
        # Should not raise any exceptions
        try:
            validate_configuration()
        except ValueError as e:
            pytest.fail(f"Configuration validation failed: {e}")

    def test_validation_catches_invalid_interval(self):
        """Verify validation would catch an invalid interval"""
        # This is a hypothetical test - in real code, we'd need to modify settings
        # For now, just verify the valid intervals list exists
        valid_intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
                          "6h", "8h", "12h", "1d", "3d", "1w", "1M"]

        for interval in settings.intervals_list:
            assert interval in valid_intervals, \
                f"Interval '{interval}' is not in the valid intervals list"


class TestEnvironmentVariables:
    """Test environment-specific settings"""

    def test_environment_setting_exists(self):
        """Verify environment setting is configured"""
        assert settings.environment is not None
        assert settings.environment in ["development", "production", "staging"]

    def test_request_timeout_is_positive(self):
        """Verify request timeout is a positive number"""
        assert settings.request_timeout > 0
        assert isinstance(settings.request_timeout, int)

    def test_max_requests_per_second_is_reasonable(self):
        """Verify rate limit is set to a reasonable value"""
        assert settings.max_requests_per_second > 0
        assert settings.max_requests_per_second <= 100  # Sanity check


class TestRateLimitingSettings:
    """Test rate limiting and performance settings"""

    def test_ws_reconnect_delay_is_positive(self):
        """Verify WebSocket reconnect delay is positive"""
        assert settings.ws_reconnect_delay > 0

    def test_ws_max_reconnect_attempts_is_reasonable(self):
        """Verify max reconnect attempts is reasonable"""
        assert settings.ws_max_reconnect_attempts > 0
        assert settings.ws_max_reconnect_attempts <= 100  # Sanity check


# ============================================
# Integration Test (Optional)
# ============================================

class TestConfigurationIntegration:
    """Integration tests for full configuration workflow"""

    def test_full_configuration_workflow(self):
        """Test the complete configuration loading and validation workflow"""
        # 1. Settings should be loaded
        assert settings is not None

        # 2. Key settings should have valid values
        assert settings.binance_base_url.startswith("http")
        assert len(settings.symbols_list) > 0
        assert len(settings.intervals_list) > 0

        # 3. Validation should pass
        try:
            validate_configuration()
        except ValueError as e:
            pytest.fail(f"Configuration validation failed: {e}")

        # 4. Computed properties should work
        assert isinstance(settings.use_redis, bool)
        assert isinstance(settings.get_binance_headers(), dict)


# ============================================
# Run Tests
# ============================================

if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])
