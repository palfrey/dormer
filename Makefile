build:
	python -m build

.PHONY: build

testpypi:
	twine upload -r testpypi dist/*

pypi:
	twine upload dist/*

sync:
	uv sync

type-check: sync
	uv run mypy .

coverage: sync
	uv run coverage run --branch -m pytest -vvv

test-watch: sync
	uv run ptw --now . -vvv --exitfirst --failed-first