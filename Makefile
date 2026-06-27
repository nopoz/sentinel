.PHONY: setup up reset test mermaid

setup:
	cp .env.example .env

up:
	docker compose up --build

reset:
	@curl -fs -X POST http://localhost:8000/reset >/dev/null 2>&1 \
		&& echo "demo state reset" \
		|| echo "reset failed: is the stack running? start it with 'make up'"

test:
	pytest

mermaid:
	python -m app.scripts.export_mermaid
