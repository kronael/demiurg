.PHONY: build test smoke clean run right lint image install

build:
	uv sync --dev

install:
	uv tool install --editable .
	mkdir -p ~/.claude/skills/ship
	cp skill/SKILL.md skill/prompt.md ~/.claude/skills/ship/

test:
	uv run pytest -v

smoke:
	uv run pytest -v -m smoke

lint:
	uv run pre-commit run -a

right:
	uv run pyright ship/

image:
	docker build -t ship .

clean:
	rm -rf __pycache__ ship/__pycache__
	rm -rf .pytest_cache
	rm -rf .ship/
