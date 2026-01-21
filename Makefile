
start:
	docker compose up

build:
	docker compose down
	docker rmi registry-api --force
	docker builder prune -f
	docker compose build --no-cache

logs:
	docker-compose logs -f api


nats-sub:
	docker run -it natsio/nats-box nats sub -s nats://host.docker.internal:4222 test_topic

nats-pub:
	docker run -it natsio/nats-box nats pub -s nats://host.docker.internal:4222 test_topic "this is a test message"

nats-js-sub:
	docker run -it natsio/nats-box nats sub -s nats://host.docker.internal:4223 test_topic

nats-js-pub:
	docker run -it natsio/nats-box nats pub -s nats://host.docker.internal:4223 test_topic "this is a test message"