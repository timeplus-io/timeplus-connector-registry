# Sample Connector Manifests

This directory contains sample connector.yaml files that can be published to the registry.

## Table of Contents
- [NATS Connectors](#nats-connectors)
  - [NATS Core Read/Write](#nats-core-readwrite)
  - [NATS JetStream Read/Write](#nats-jetstream-readwrite)
- [Kafka Connectors](#kafka-connectors)
- [HTTP Webhook](#http-webhook-sink)

## NATS Connectors

### NATS Core Read/Write

Basic NATS pub/sub connectors for real-time messaging.

**Files:**
- `nats-read-connector.yaml` - Subscribe to NATS subjects
- `nats-write-connector.yaml` - Publish to NATS subjects

**Setup:**
```bash
# The NATS server is already running in docker-compose on port 4222

# Subscribe to messages (in a separate terminal)
make nats-sub

# Publish test messages
make nats-pub
```

**Usage:**
```sql
-- Read from NATS
SELECT nats_subject, message_data, received_at
FROM nats_read_connector;

-- Write to NATS
INSERT INTO nats_write_connector(message_string)
VALUES ('Hello from Timeplus!');
```

### NATS JetStream Read/Write

NATS JetStream connectors with message persistence, guaranteed delivery, and replay capabilities.

**Files:**
- `nats-jetstream-read-connector.yaml` - Consume from JetStream streams
- `nats-jetstream-write-connector.yaml` - Publish to JetStream streams

**Setup:**
```bash
# 1. Create the JetStream stream (required before using the connectors)
make nats-js-stream-create

# 2. Verify the stream was created
make nats-js-stream-list

# 3. Get detailed stream info
make nats-js-stream-info

# 4. Publish test messages to JetStream
make nats-js-stream-pub

# 5. Subscribe to JetStream messages (in a separate terminal)
make nats-js-stream-sub
```

**Available Makefile Commands:**
- `nats-js-stream-create` - Create the EVENTS stream with default configuration
- `nats-js-stream-list` - List all JetStream streams
- `nats-js-stream-info` - Get detailed info about the EVENTS stream
- `nats-js-stream-delete` - Delete the EVENTS stream
- `nats-js-stream-pub` - Publish a test message to events.data subject
- `nats-js-stream-sub` - Subscribe to all events.* subjects

**Usage:**
```sql
-- Read from JetStream (includes sequence numbers for ordering)
SELECT nats_subject, message_data, sequence, received_at
FROM nats_jetstream_read_connector;

-- Write to JetStream with guaranteed delivery
INSERT INTO nats_jetstream_write_connector(message_string)
VALUES ('Persistent message in JetStream');

-- Stream processing: read, transform, and write back to JetStream
INSERT INTO nats_jetstream_write_connector(message_string)
SELECT
  to_json_string(map(
    'subject', nats_subject,
    'processed_at', to_string(now()),
    'original_data', message_data
  )) AS message_string
FROM nats_jetstream_read_connector
WHERE message_data ILIKE '%important%';
```

**Key Differences from NATS Core:**
- **Persistence**: Messages are stored and can be replayed
- **Guaranteed Delivery**: Acknowledgment ensures messages aren't lost
- **Ordering**: Sequence numbers track message order
- **Durable Consumers**: Maintain position in the stream across restarts
- **Stream Configuration**: Pre-configured streams with retention policies

---

## Kafka Connectors

## Kafka JSON Reader

A simple Kafka consumer that reads JSON messages.

```yaml
# kafka-json-reader.yaml
apiVersion: v1
kind: Connector

metadata:
  name: kafka-json-reader
  namespace: timeplus
  version: 1.0.0
  displayName: Kafka JSON Reader
  description: Read JSON messages from a Kafka topic as a stream
  authors:
    - name: Timeplus Team
      email: support@timeplus.com
  license: Apache-2.0
  homepage: https://github.com/timeplus-io/connectors
  repository: https://github.com/timeplus-io/connectors

spec:
  category: source
  mode: streaming
  
  tags:
    - kafka
    - json
    - streaming
    - message-queue
  
  compatibility:
    protonVersion: ">=3.0.0"
    pythonVersion: ">=3.9"
  
  dependencies:
    - kafka-python>=2.0.2
  
  schema:
    columns:
      - name: value
        type: int32
        description: The message value

  functions:
    read:
      name: py_kafka_read
      description: Read JSON messages from Kafka

  configTemplate:
    - name: bootstrap_servers
      description: Kafka broker addresses
      example: "k1:9092"
    - name: topic
      description: Kafka topic to consume
      example: "py_read"
    - name: group_id
      description: Consumer group ID
      example: "py_kafka_read_probe"

  pythonCode: |
    from kafka import KafkaConsumer
    import json
    
    def py_kafka_read():
        consumer = KafkaConsumer(
            "py_read",
            bootstrap_servers="k1:9092",
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            group_id="py_kafka_read_probe",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        try:
            for msg in consumer:
                yield [msg.value["value"]]
        finally:
            consumer.close()

  examples:
    - title: Basic Read
      description: Read all messages from the configured topic
      code: |
        SELECT * FROM kafka_json_reader;
    
    - title: Filtered Read
      description: Read with a filter condition
      code: |
        SELECT * FROM kafka_json_reader WHERE value > 100;
```

## Kafka Bidirectional

A Kafka connector that supports both reading and writing.

```yaml
# kafka-bidirectional.yaml
apiVersion: v1
kind: Connector

metadata:
  name: kafka-bidirectional
  namespace: timeplus
  version: 1.0.0
  displayName: Kafka Bidirectional Connector
  description: Read from and write to Kafka topics
  authors:
    - name: Timeplus Team
      email: support@timeplus.com
  license: Apache-2.0

spec:
  category: bidirectional
  mode: streaming
  
  tags:
    - kafka
    - json
    - streaming
    - bidirectional
  
  compatibility:
    protonVersion: ">=3.0.0"
    pythonVersion: ">=3.9"
  
  dependencies:
    - kafka-python>=2.0.2
  
  schema:
    columns:
      - name: value
        type: int32
        description: The message value

  functions:
    read:
      name: py_kafka_read
      description: Read messages from Kafka 'py_read' topic
    write:
      name: py_kafka_sink
      description: Write messages to Kafka 'py_write' topic

  configTemplate:
    - name: bootstrap_servers
      description: Kafka broker addresses
      example: "k1:9092"
    - name: read_topic
      description: Topic to read from
      example: "py_read"
    - name: write_topic
      description: Topic to write to
      example: "py_write"

  pythonCode: |
    from kafka import KafkaConsumer, KafkaProducer
    import json
    
    def py_kafka_read():
        consumer = KafkaConsumer(
            "py_read",
            bootstrap_servers="k1:9092",
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            group_id="py_kafka_read_probe",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        try:
            for msg in consumer:
                yield [msg.value["value"]]
        finally:
            consumer.close()
    
    def py_kafka_sink(values):
        producer = KafkaProducer(
            bootstrap_servers="k1:9092",
            value_serializer=lambda v: json.dumps({"value": v}).encode("utf-8"),
        )
        try:
            for v in values:
                producer.send("py_write", v)
            producer.flush()
        finally:
            producer.close()

  examples:
    - title: Read from Kafka
      code: SELECT * FROM kafka_bidirectional;
    - title: Write to Kafka
      code: INSERT INTO kafka_bidirectional VALUES (42);
    - title: Stream Processing
      code: |
        INSERT INTO kafka_bidirectional
        SELECT value * 2 FROM kafka_bidirectional WHERE value > 10;
```

## HTTP Webhook Sink

A sink that posts data to an HTTP endpoint.

```yaml
# http-webhook-sink.yaml
apiVersion: v1
kind: Connector

metadata:
  name: http-webhook-sink
  namespace: timeplus
  version: 1.0.0
  displayName: HTTP Webhook Sink
  description: Post data to an HTTP webhook endpoint
  authors:
    - name: Timeplus Team
      email: support@timeplus.com
  license: Apache-2.0

spec:
  category: sink
  mode: streaming
  
  tags:
    - http
    - webhook
    - rest
    - sink
  
  compatibility:
    protonVersion: ">=3.0.0"
    pythonVersion: ">=3.9"
  
  dependencies:
    - requests>=2.28.0
  
  schema:
    columns:
      - name: payload
        type: string
        description: JSON payload to send

  functions:
    write:
      name: http_webhook_sink
      description: POST payload to configured webhook URL

  configTemplate:
    - name: webhook_url
      description: Target webhook URL
      example: "https://webhook.site/xxx"

  pythonCode: |
    import requests
    import json
    
    WEBHOOK_URL = "https://webhook.site/your-webhook-id"
    
    def http_webhook_sink(values):
        for row in values:
            payload = row[0]
            try:
                data = json.loads(payload) if isinstance(payload, str) else payload
            except json.JSONDecodeError:
                data = {"message": payload}
            
            requests.post(
                WEBHOOK_URL,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

  examples:
    - title: Send JSON payload
      code: |
        INSERT INTO http_webhook_sink(payload) 
        VALUES ('{"event": "alert", "severity": "high"}');
    
    - title: Stream events to webhook
      code: |
        INSERT INTO http_webhook_sink(payload)
        SELECT to_json_string(map('event', event_name, 'time', now()))
        FROM events_stream;
```
