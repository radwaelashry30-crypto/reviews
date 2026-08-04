.PHONY: install backend frontend test typecheck build docker-build docker-up docker-down

install:
	pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest -q

typecheck:
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build

docker-build:
	docker compose build

docker-up:
	docker compose up

docker-down:
	docker compose down
