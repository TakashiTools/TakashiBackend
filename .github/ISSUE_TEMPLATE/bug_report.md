---
name: Bug Report
about: Create a report to help us improve
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description

A clear and concise description of what the bug is.

## To Reproduce

Steps to reproduce the behavior:
1. Start server with '...'
2. Make request to '...'
3. Observe response '...'
4. See error

## Expected Behavior

A clear and concise description of what you expected to happen.

## Actual Behavior

A clear and concise description of what actually happened.

## Code Sample

```python
# Minimal code to reproduce the issue
import asyncio
from app.main import app

async def test():
    # Your code here
    pass

asyncio.run(test())
```

## Error Messages / Logs

```
Paste any error messages or logs here
```

## Environment

**Server:**
- OS: [e.g., Ubuntu 22.04, Windows 11]
- Python version: [e.g., 3.11.5]
- FastAPI version: [e.g., 0.110.0]
- Deployment: [e.g., Local, Railway, Docker]

**Client (if applicable):**
- Browser: [e.g., Chrome 120, Firefox 121]
- JavaScript runtime: [e.g., Node.js 20.0.0]

**Dependencies:**
```bash
# Output from: pip freeze | grep -E "fastapi|aiohttp|pydantic|websockets"
fastapi==0.110.0
aiohttp==3.9.0
pydantic==2.6.0
websockets==12.0
```

## Configuration

**Relevant `.env` settings:**
```env
# Only include relevant non-sensitive settings
LOG_LEVEL=INFO
SUPPORTED_SYMBOLS=BTCUSDT,ETHUSDT
# etc.
```

## Screenshots

If applicable, add screenshots to help explain your problem.

## Additional Context

Add any other context about the problem here. For example:
- Does this happen consistently or intermittently?
- Did this work in a previous version?
- Are there any workarounds?
- Related issues or PRs?

## Possible Solution

(Optional) If you have ideas on how to fix the bug, share them here.

## Checklist

- [ ] I have searched existing issues to avoid duplicates
- [ ] I have provided all relevant information above
- [ ] I have tested on the latest version
- [ ] I can reproduce this issue consistently

