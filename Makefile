.PHONY: install dev test lint typecheck format run clean all

all: install lint typecheck test

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --tb=short --cov=tokenwise --cov-report=html

lint:
	ruff check src/ tests/

typecheck:
	mypy src/tokenwise/ --ignore-missing-imports

format:
	ruff format src/ tests/

run:
	python -m tokenwise --help

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info .pytest_cache .mypy_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
