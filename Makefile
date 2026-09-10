.PHONY: help install run test lint format check migrate makemigrations createsuperuser docker-up docker-down docker-logs docker-test

help: ## Mostra esta ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Instala dependências com Poetry
	poetry install

run: ## Roda o servidor de desenvolvimento
	poetry run python manage.py runserver

test: ## Roda os testes com coverage
	poetry run pytest --cov=apps --cov=core --cov-report=term-missing

lint: ## Roda o linter (Ruff)
	poetry run ruff check .

format: ## Formata o código (Ruff)
	poetry run ruff format .

check: ## Verifica o projeto Django
	poetry run python manage.py check

migrate: ## Roda as migrations
	poetry run python manage.py migrate

makemigrations: ## Cria novas migrations
	poetry run python manage.py makemigrations

createsuperuser: ## Cria um superusuário
	poetry run python manage.py createsuperuser

docker-up: ## Sobe os containers (dev)
	docker compose up -d --build

docker-down: ## Para os containers
	docker compose down

docker-logs: ## Mostra logs dos containers
	docker compose logs -f

docker-test: ## Roda testes dentro do container
	docker compose exec api pytest --cov=apps --cov=core --cov-report=term-missing
