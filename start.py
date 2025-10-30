#!/usr/bin/env python3
"""
Railway start script - handles PORT environment variable
"""
import os
import sys

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))

    # Import and run uvicorn programmatically
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
