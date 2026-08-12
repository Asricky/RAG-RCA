.PHONY: data test dev
data:
	python scripts/generate_synthetic_data.py
test:
	cd backend && .venv/Scripts/python.exe -m pytest -q
	cd frontend && npm run build
dev:
	docker compose up --build
