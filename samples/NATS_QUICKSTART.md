# NATS JetStream Quick Start Guide

This guide will help you quickly set up and test the NATS JetStream connectors.

## Prerequisites

- Docker and Docker Compose running
- NATS JetStream server running (included in docker-compose.yml on port 4223)
- Timeplus instance running

## Step-by-Step Setup

### 1. Create the JetStream Stream

Before using the JetStream connectors, you must create the stream:

```bash
make nats-js-stream-create
```

This creates a stream named `EVENTS` with the following configuration:
- **Subjects**: `events.>` (matches all subjects starting with "events.")
- **Storage**: File-based (persistent)
- **Retention**: Limits-based (keeps messages until limits are reached)
- **Max Age**: 1 year
- **Replicas**: 1

### 2. Verify the Stream

Check that the stream was created successfully:

```bash
# List all streams
make nats-js-stream-list

# Get detailed info about the EVENTS stream
make nats-js-stream-info
```

### 3. Test Publishing to JetStream

Publish a test message:

```bash
make nats-js-stream-pub
```

### 4. Subscribe to Messages (Optional)

In a separate terminal, monitor incoming messages:

```bash
make nats-js-stream-sub
```

## Using the Connectors in Timeplus

### Reading from JetStream

```sql
-- View all messages from JetStream
SELECT nats_subject, message_data, sequence, received_at
FROM nats_jetstream_read_connector;

-- Filter by subject pattern
SELECT *
FROM nats_jetstream_read_connector
WHERE nats_subject LIKE 'events.orders%';

-- Parse JSON messages
SELECT
  nats_subject,
  message_data:event_type AS event_type,
  message_data:user_id AS user_id,
  sequence,
  received_at
FROM nats_jetstream_read_connector;
```

### Writing to JetStream

```sql
-- Insert a simple message
INSERT INTO nats_jetstream_write_connector(message_string)
VALUES ('Hello from Timeplus!');

-- Insert JSON data
INSERT INTO nats_jetstream_write_connector(message_string)
VALUES ('{"event": "user_login", "user_id": 123, "timestamp": "2024-01-01T00:00:00Z"}');

-- Stream processing: read from one stream, transform, write to JetStream
INSERT INTO nats_jetstream_write_connector(message_string)
SELECT
  to_json_string(map(
    'event_type', event_type,
    'count', count(),
    'window', to_string(window_start)
  )) AS message_string
FROM tumble(event_stream, timestamp, 1m)
GROUP BY window_start, event_type;
```

## Advanced Usage

### Configure Different Streams

You can modify the connector YAML files to use different streams:

**For reading (nats-jetstream-read-connector.yaml):**
```python
stream_name = "MY_STREAM"        # Your stream name
consumer_name = "my_consumer"    # Unique consumer name
filter_subject = "myapp.events"  # Optional subject filter
```

**For writing (nats-jetstream-write-connector.yaml):**
```python
stream_name = "MY_STREAM"           # Your stream name
publish_subject = "myapp.events"    # Subject to publish to
wait_for_ack = True                 # Wait for acknowledgment (recommended)
```

### Create Custom Streams

Create a stream with custom configuration:

```bash
docker run -it natsio/nats-box nats stream add MY_STREAM \
  --subjects "myapp.>" \
  --storage file \
  --retention limits \
  --max-msgs=1000000 \
  --max-bytes=10GB \
  --max-age=30d \
  --server nats://host.docker.internal:4223
```

### Message Acknowledgment

The read connector automatically acknowledges messages after successful processing. If an error occurs:
- Messages are negatively acknowledged (NACK)
- JetStream will redeliver the message
- This ensures at-least-once delivery guarantee

### Consumer Position

The consumer maintains its position in the stream:
- On restart, it continues from where it left off
- Old messages can be replayed by creating a new consumer with a different name
- Set `deliver_policy` to control starting position (all, new, last, by sequence, by time)

## Troubleshooting

### Error: "stream not found"

This means the JetStream stream hasn't been created yet. Run:
```bash
make nats-js-stream-create
```

### Error: Connection refused

Check that the NATS JetStream server is running:
```bash
docker ps | grep nats-server-js
```

If not running, start it:
```bash
docker compose up -d nats-js
```

### Messages not appearing

1. Verify the stream exists: `make nats-js-stream-info`
2. Check the subject matches: Stream subject is `events.>`, publish to `events.*`
3. Test with CLI: `make nats-js-stream-pub` then `make nats-js-stream-sub`

## Cleanup

To delete the stream and all its messages:

```bash
make nats-js-stream-delete
```

## Useful Commands Reference

| Command | Description |
|---------|-------------|
| `make nats-js-stream-create` | Create the EVENTS stream |
| `make nats-js-stream-list` | List all streams |
| `make nats-js-stream-info` | Show EVENTS stream details |
| `make nats-js-stream-delete` | Delete the EVENTS stream |
| `make nats-js-stream-pub` | Publish test message |
| `make nats-js-stream-sub` | Subscribe to messages |

## Further Reading

- [NATS JetStream Documentation](https://docs.nats.io/nats-concepts/jetstream)
- [NATS Python Client](https://github.com/nats-io/nats.py)
- [Timeplus Documentation](https://docs.timeplus.com)
