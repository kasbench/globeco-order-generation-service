#!/usr/bin/env python3
"""Debug script for CORS configuration issue."""

import os
import sys

sys.path.append('src')

# Test CORS parsing
cors_value = os.environ.get(
    'CORS_ORIGINS',
    'http://localhost:3000,http://localhost:8080,http://localhost:8189,*',
)
print(f"Raw CORS value: {cors_value}")

# Test the validator function
try:
    from src.config import Settings

    print("Settings import successful")

    # Test the validator
    parsed = Settings.parse_cors_origins(cors_value)
    print(f"Parsed CORS: {parsed}")

    # Try creating settings directly
    settings = Settings(cors_origins=cors_value)
    print(f"Settings CORS: {settings.cors_origins}")

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
