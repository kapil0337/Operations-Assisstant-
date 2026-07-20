.PHONY: up down migrate seed test eval logs worker token restart

up:
	docker compose up -d --build

down:
	docker compose down

restart:
	docker compose restart app worker

migrate:
	docker compose run --rm migrate

seed:
	docker compose run --rm seed

dev:
	uvicorn app.main:app --reload --port 8000

worker:
	python -m arq app.queue.worker.WorkerSettings

token:
	curl -s -X POST http://localhost:8000/token \
		-H "Content-Type: application/json" \
		-d '{"user_id":"dev","tenant_id":"default","scopes":["chat","admin"],"api_key":"dev-key-change-me"}' \
		| python -m json.tool

test:
	python -m pytest -q

eval:
	docker compose run --rm --name evalrun app python -m evals.run_evals || true
	docker cp evalrun:/srv/evals/results.md ./evals/results.md 2>/dev/null || true
	docker rm evalrun 2>/dev/null || true

logs:
	docker compose logs -f --tail=100 app worker
