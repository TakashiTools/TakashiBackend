# Contributing to TAKASHI

Thank you for your interest in contributing to TAKASHI Multi-Exchange Market Data API!

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Adding a New Exchange](#adding-a-new-exchange)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Questions?](#questions)

---

## Code of Conduct

This project adheres to a code of conduct to foster an open and welcoming environment. By participating, you are expected to uphold this code.

**Key Principles:**
- Be respectful and inclusive
- Accept constructive criticism gracefully
- Focus on what is best for the community
- Show empathy towards other community members

---

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates.

**When reporting a bug, include:**
- Clear, descriptive title
- Steps to reproduce the issue
- Expected vs. actual behavior
- Code samples if applicable
- Python version, OS, and relevant environment details
- Screenshots or logs if helpful

**Template:**
```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
1. Start server with '...'
2. Make request to '...'
3. See error

**Expected behavior**
What you expected to happen.

**Environment:**
- OS: [e.g., Windows 11, Ubuntu 22.04]
- Python version: [e.g., 3.11.5]
- Package versions: [paste from `pip freeze`]

**Additional context**
Any other relevant information.
```

### Suggesting Features

We love feature suggestions! Before submitting:
- Check if the feature already exists
- Search existing feature requests
- Clearly explain the use case and benefits

**Template:**
```markdown
**Feature Description**
Clear description of the proposed feature.

**Use Case**
Why is this feature valuable? Who will benefit?

**Proposed Implementation**
How might this work? (if you have ideas)

**Alternatives Considered**
What other solutions have you considered?
```

### Code Contributions

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Commit with clear messages (`git commit -m 'Add amazing feature'`)
5. Push to your fork (`git push origin feature/amazing-feature`)
6. Open a Pull Request

---

## Development Setup

### Prerequisites

- **Python 3.11+** (3.12 recommended)
- **Git**
- **Virtual environment tool**

### Setup Steps

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/TakashiBackend.git
cd TakashiBackend

# Add upstream remote
git remote add upstream https://github.com/TakashiTools/TakashiBackend.git

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies (if available)
pip install black mypy ruff pytest pytest-asyncio pytest-cov

# Copy environment file
cp .env.example .env

# Run tests
pytest

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Keep Your Fork Updated

```bash
# Fetch latest from upstream
git fetch upstream

# Merge into your main
git checkout main
git merge upstream/main

# Push to your fork
git push origin main
```

---

## Pull Request Process

### Before Submitting

- [ ] Code follows project style guidelines
- [ ] Tests added for new features
- [ ] All tests pass (`pytest`)
- [ ] Documentation updated (if applicable)
- [ ] Code formatted with `black`
- [ ] No linting errors (`ruff check .`)
- [ ] Type hints added (`mypy` compatible)
- [ ] Commit messages are clear and descriptive

### PR Guidelines

1. **Title:** Use clear, descriptive titles
   - Good: `Add Kraken exchange connector`
   - Bad: `Update files`

2. **Description:** Explain WHAT and WHY
   ```markdown
   ## Changes
   - Added Kraken exchange connector
   - Implemented REST API client
   - Added WebSocket support
   
   ## Motivation
   Adds support for Kraken exchange as requested in #123
   
   ## Testing
   - Added unit tests for API client
   - Manually tested all endpoints
   - Verified WebSocket streams work correctly
   ```

3. **Link Issues:** Reference related issues
   - `Fixes #123`
   - `Closes #456`
   - `Related to #789`

4. **Keep it Focused:** One feature/fix per PR

5. **Request Reviews:** Tag relevant maintainers

### PR Review Process

1. Automated checks must pass (CI/CD)
2. At least one maintainer review required
3. Address review feedback promptly
4. Maintainer merges after approval

---

## Coding Standards

### Python Style

We follow **PEP 8** with modifications:

- **Line length:** 120 characters
- **Formatter:** black (automatically formats code)
- **Linter:** ruff (catches common issues)
- **Type checker:** mypy (ensures type safety)

### Code Formatting

```bash
# Format code
black .

# Check linting
ruff check .

# Type check
mypy core/ exchanges/ services/
```

### Type Hints

Always use type hints:

```python
from typing import List, Optional, Dict

async def fetch_data(
    symbol: str,
    limit: int = 500,
    filters: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """Fetch data with proper type hints."""
    pass
```

### Docstrings

Use Google-style docstrings:

```python
def complex_function(param1: str, param2: int) -> bool:
    """
    One-line summary of what the function does.
    
    More detailed explanation if needed. Can span multiple
    lines and include examples.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When invalid input is provided
        RuntimeError: When operation fails
    
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result)
        True
    """
    pass
```

### Async/Await

- Use async/await for I/O operations
- Use `asyncio.gather()` for concurrent requests
- Always close resources (use context managers)

```python
# Good
async with aiohttp.ClientSession() as session:
    async with session.get(url) as resp:
        data = await resp.json()

# Bad
session = aiohttp.ClientSession()
resp = await session.get(url)
data = await resp.json()
# session never closed!
```

### Error Handling

```python
# Be specific with exceptions
try:
    data = await fetch_data()
except aiohttp.ClientError as e:
    logger.error(f"HTTP error: {e}")
    raise
except asyncio.TimeoutError:
    logger.error("Request timed out")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

---

## Adding a New Exchange

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for detailed guide on adding exchange connectors.

**Quick Checklist:**
- [ ] Create `exchanges/{exchange}/` directory
- [ ] Implement `api_client.py` (REST)
- [ ] Implement `ws_client.py` (WebSocket)
- [ ] Create `__init__.py` with `{Exchange}Exchange` class
- [ ] Register in `ExchangeManager`
- [ ] Add unit tests
- [ ] Add integration tests
- [ ] Update documentation

---

## Testing Guidelines

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=. --cov-report=html

# Specific test
pytest tests/unit/test_binance_api_client.py -v

# By pattern
pytest -k "test_ohlc" -v
```

### Writing Tests

**Unit Test Structure:**
```python
import pytest
from module import function


def test_function_success():
    """Test successful operation."""
    result = function(valid_input)
    assert result == expected_output


def test_function_invalid_input():
    """Test error handling."""
    with pytest.raises(ValueError):
        function(invalid_input)


@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await async_function()
    assert result is not None
```

**Test Coverage Goals:**
- Minimum 80% coverage for new code
- 100% coverage for critical paths
- Test both success and failure cases
- Test edge cases and boundary conditions

---

## Documentation

### When to Update Docs

- Adding new features
- Changing API endpoints
- Modifying configuration options
- Adding new dependencies
- Changing deployment process

### Documentation Files

- **README.md** - Project overview and quick start
- **docs/API_REFERENCE.md** - Complete API documentation
- **docs/DEVELOPMENT.md** - Developer guide
- **docs/ARCHITECTURE.md** - System architecture (if available)
- **CHANGELOG.md** - Version history

### Documentation Style

- Use clear, concise language
- Include code examples
- Add diagrams where helpful
- Keep formatting consistent
- Test all code examples

---

## Commit Message Guidelines

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat:** New feature
- **fix:** Bug fix
- **docs:** Documentation changes
- **style:** Code style changes (formatting, etc.)
- **refactor:** Code refactoring
- **test:** Adding or updating tests
- **chore:** Maintenance tasks

### Examples

```
feat(exchanges): add Kraken exchange connector

- Implement REST API client
- Add WebSocket support
- Add unit tests

Closes #123
```

```
fix(binance): handle rate limit errors correctly

Previously, rate limit errors would cause the connection
to close. Now implements exponential backoff retry.

Fixes #456
```

---

## Questions?

- **General questions:** [GitHub Discussions](https://github.com/TakashiTools/TakashiBackend/discussions)
- **Bug reports:** [GitHub Issues](https://github.com/TakashiTools/TakashiBackend/issues)
- **Security issues:** Email security@your-domain.com

---

## Recognition

Contributors will be recognized in:
- [CONTRIBUTORS.md](CONTRIBUTORS.md)
- Release notes
- Project README

Thank you for contributing!

