
start:
	docker compose up

build:
	docker compose down
	docker rmi registry-api --force
	docker builder prune -f
	docker compose build --no-cache

logs:
	docker-compose logs -f api