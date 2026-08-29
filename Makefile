.PHONY: dev test seed db-migrate db-psql up down lint clean

dev:            ## run API locally (demo mode)
	cd backend && uvicorn app.main:app --reload --port 8000

test:           ## run the test suite
	cd backend && python -m pytest -q

fresh-demo:     ## wipe + reseed the demo database and boot the API
	cd backend && rm -f socialos.db && uvicorn app.main:app --reload --port 8000

up:             ## production-ish stack (postgres + redis + api + adminer)
	docker compose up -d --build
	@echo "Run migrations:  docker compose run --rm migrate"
	@echo "                 (or) psql $$DATABASE_URL -f backend/app/db/migrations/0001_init.sql"

down:
	docker compose down

migrate:
	docker compose run --rm migrate

psql:
	docker compose exec db psql -U socialos_app -d socialos

key:            ## generate a vault master key
	@python3 -c "import secrets; print(secrets.token_hex(32))"

clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; true
