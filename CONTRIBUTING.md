# Contributing to TokenWise

Thank you for your interest in contributing to TokenWise! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/<your-username>/TokenWise.git
   cd TokenWise
   ```
3. Install development dependencies:
   ```bash
   make dev
   ```

## Development Workflow

### Running Tests

```bash
make test
```

### Linting

```bash
make lint
```

### Type Checking

```bash
make typecheck
```

### Formatting

```bash
make format
```

## Code Style

- We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting
- Type hints are required for all public functions
- Docstrings follow Google style

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with clear, descriptive commits
3. Add or update tests for any new functionality
4. Ensure all checks pass: `make all`
5. Open a pull request with a clear description of the changes

## Adding a New Model

To add pricing for a new LLM model:

1. Add the model's pricing to `MODEL_PRICING` in `src/tokenwise/config.py`
2. Add the context window size to `MODEL_CONTEXT_WINDOWS` in `src/tokenwise/config.py`
3. If the model uses a new tokenizer family, add a ratio to `TOKENIZER_RATIOS`
4. Add a test to verify the new model works correctly

## Reporting Issues

- Use GitHub Issues to report bugs
- Include Python version, OS, and a minimal reproducible example
- Check existing issues before creating a new one

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
