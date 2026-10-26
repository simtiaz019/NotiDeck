.PHONY: install frontend test check build serve
install:
	python -m pip install -e '.[dev]'
	npm --prefix frontend ci
frontend:
	npm --prefix frontend run build
test:
	pytest
	npm --prefix frontend test
check:
	ruff check src tests
	mypy src/notideck
build: frontend
	python -m build
serve:
	notideck serve
