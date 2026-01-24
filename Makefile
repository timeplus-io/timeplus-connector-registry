
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

# Create JetStream stream
nats-js-stream-create:
	docker run --rm natsio/nats-box nats stream add EVENTS \
		--subjects "events.>" \
		--storage file \
		--retention limits \
		--discard old \
		--max-msgs=-1 \
		--max-bytes=-1 \
		--max-age=1y \
		--max-msg-size=-1 \
		--max-msgs-per-subject=-1 \
		--max-consumers=-1 \
		--replicas=1 \
		--defaults \
		--server nats://host.docker.internal:4223

# List JetStream streams
nats-js-stream-list:
	docker run --rm natsio/nats-box nats stream list --server nats://host.docker.internal:4223

# Get stream info
nats-js-stream-info:
	docker run --rm natsio/nats-box nats stream info EVENTS --server nats://host.docker.internal:4223

# Delete JetStream stream
nats-js-stream-delete:
	docker run --rm natsio/nats-box nats stream delete EVENTS --force --server nats://host.docker.internal:4223

# Publish to JetStream
nats-js-stream-pub:
	docker run --rm natsio/nats-box nats pub events.data "Test message from JetStream" --server nats://host.docker.internal:4223

# Subscribe to JetStream stream (interactive)
nats-js-stream-sub:
	docker run --rm -it natsio/nats-box nats sub events.> --server nats://host.docker.internal:4223