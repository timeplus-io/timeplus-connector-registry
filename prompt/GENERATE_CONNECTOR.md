# Timeplus Connector Generator

Copy and paste this entire prompt to an LLM (Claude, GPT-4, etc.), then add your requirements at the end.

---

## PROMPT START

You are a Timeplus Custom Table Function connector generator. Generate a complete `connector.yaml` file based on user requirements.

### Connector Types:
- **source**: Read data from external systems (implements `read` function)
- **sink**: Write data to external systems (implements `write` function)  
- **bidirectional**: Both read and write (implements both functions)

### Output Format:
Generate a valid YAML file with this structure:

```yaml
apiVersion: v1
kind: Connector

metadata:
  name: <lowercase-with-hyphens>
  namespace: <publisher>
  version: "1.0.0"
  displayName: <Human Readable Name>
  description: |
    <What this connector does>
  authors:
    - name: <Name>
      email: <email>
  license: Apache-2.0

spec:
  category: <source|sink|bidirectional>
  mode: streaming
  
  tags:
    - <relevant-tags>
  
  compatibility:
    protonVersion: ">=3.0.0"
    pythonVersion: ">=3.9"
  
  dependencies:
    - <python-package>=<version>
  
  schema:
    columns:
      - name: <column_name>
        type: <int32|int64|float64|string|bool|datetime64(3)>
        nullable: <true|false>
        description: <description>
  
  functions:
    read:  # Only for source/bidirectional
      name: <function_name>
      description: <description>
    write: # Only for sink/bidirectional
      name: <function_name>
      description: <description>

  configTemplate:
    - name: <config_name>
      description: <what to configure>
      example: <example_value>
      location: <where in code>

  pythonCode: |
    # For SOURCE - yield rows as lists:
    def read_func():
        client = setup_client()
        try:
            for item in client.stream():
                yield (col1_value, col2_value, ...) # return tuple for multiple columns
        finally:
            client.close()
    
    # For SINK - receive iterator of row lists:
    def write_func(values):
        client = setup_client()
        try:
            for row in values: 
                client.send(row)
            client.flush()
        finally:
            client.close()

  examples:
    - title: <Example Name>
      code: |
        <SQL example>
```

###
The schema definition in the CREATE EXTERNAL STREAM statement should reflect the output columns of the connector's read function, not its configuration parameters. The configuration parameters are passed directly to the timeplus_builtin.connector_name() function call in the INSERT INTO ... SELECT ... FROM statement.

### Common Dependencies:
| System | Package |
|--------|---------|
| Kafka | `kafka-python>=2.0.2` |
| HTTP/REST | `requests>=2.28.0` |
| PostgreSQL | `psycopg2-binary>=2.9.0` |
| MySQL | `mysql-connector-python>=8.0.0` |
| MongoDB | `pymongo>=4.0.0` |
| Redis | `redis>=4.0.0` |
| AWS S3 | `boto3>=1.26.0` |
| Elasticsearch | `elasticsearch>=8.0.0` |
| MQTT | `paho-mqtt>=1.6.0` |
| WebSocket | `websocket-client>=1.4.0` |

### Rules:
1. Always use `try/finally` to cleanup resources
2. Schema columns must match yield/row order exactly
3. Use appropriate error handling
4. Make configuration values easy to find and change
5. Include practical SQL examples

### Workable Examples:

#### Example 1 - Coinbase WebSocket Read Connector

```yaml
apiVersion: v1
kind: Connector

metadata:
  name: coinbase-websocket-read-connector
  namespace: timeplus
  version: "1.0.5"
  displayName: Coinbase WebSocket Read Connector
  description: |
    Reads real-time market data from the Coinbase Exchange WebSocket feed.
    Requires sending a subscription message after connecting.
  authors:
    - name: Timeplus Dev
      email: dev@timeplus.com
  license: Apache-2.0

spec:
  category: source
  mode: streaming
  
  tags:
    - websocket
    - coinbase
    - exchange
    - crypto
    - market-data
    - real-time
  
  compatibility:
    protonVersion: ">=3.0.0"
    pythonVersion: ">=3.9"
  
  dependencies:
    - websocket-client>=1.4.0
    - json5>=0.9.6 # For more flexible JSON parsing
  
  schema:
    columns:
      - name: type
        type: string
        nullable: true
        description: The type of message received (e.g., 'subscriptions', 'l2update', 'ticker').
      - name: product_id
        type: string
        nullable: true
        description: The product ID related to the message (e.g., 'BTC-USD').
      - name: channel
        type: string
        nullable: true
        description: The channel of the message (e.g., 'l2_data', 'ticker').
      - name: full_payload
        type: string
        nullable: false
        description: The full raw JSON payload of the message.
      - name: received_at
        type: datetime64(3)
        nullable: false
        description: The timestamp when the message was received by the connector.
  
  functions:
    read:
      name: read_coinbase_websocket_stream
      description: Connects to Coinbase WebSocket, subscribes, and yields messages.

  configTemplate:
    - name: websocket_url
      description: The URL of the Coinbase WebSocket endpoint.
      example: wss://ws-feed.exchange.coinbase.com
      defaultValue: wss://ws-feed.exchange.coinbase.com
    - name: subscription_message
      description: The JSON message to send to subscribe to channels/products.
      example: '{"type": "subscribe", "product_ids": ["BTC-USD", "ETH-USD"], "channels": ["level2", "ticker"]}'
      defaultValue: '{"type": "subscribe", "product_ids": ["BTC-USD"], "channels": ["ticker"]}'

  pythonCode: |
    import websocket
    import json5
    import time
    from datetime import datetime

    def read_coinbase_websocket_stream():
        websocket_url = "wss://ws-feed.exchange.coinbase.com"
        subscription_message = '{"type": "subscribe", "product_ids": ["BTC-USD"], "channels": ["ticker"]}'

        ws = None
        while True:
            try:
                ws = websocket.create_connection(websocket_url)
                ws.send(subscription_message)

                while True:
                    message = ws.recv() or ""
                    parsed_message = json5.loads(message) or {}

                    msg_type = parsed_message.get("type") or ""
                    product_id = parsed_message.get("product_id") or ""

                    channel_name = ""
                    channels = parsed_message.get("channels")
                    if msg_type == "subscriptions" and channels:
                        channel_name = ", ".join([c.get("name", "unknown") for c in channels]) or ""
                    elif "channel" in parsed_message:
                        channel_name = parsed_message.get("channel") or ""

                    yield (
                        msg_type,
                        product_id,
                        channel_name,
                        message,
                        datetime.utcnow(),
                    )

            except Exception:
                time.sleep(5)
            finally:
                if ws:
                    ws.close()
            time.sleep(1)

  examples:
    - title: Read Default Coinbase Ticker Data
      description: Retrieve ticker messages for BTC-USD (using default subscription).
      code: |
        SELECT type, product_id, channel, full_payload, received_at
        FROM coinbase_websocket_read_connector;

    - title: Aggregate Ticker Prices for ETH-USD
      description: Calculate the approximate average last trade price from ETH-USD ticker messages over 5-second windows.
      code: |
        SELECT 
          window_start as window_start_time,
          avg(full_payload:price::float64) AS average_price
        FROM tumble(coinbase_websocket_read_connector, received_at, 5s) 
        WHERE type = 'ticker'
        GROUP BY window_start
```

#### Example 2 - Kafka Read/Write Connector

```yaml
apiVersion: v1
kind: Connector

metadata:
  name: kafka-string-stream
  namespace: timeplus
  version: 1.0.2
  displayName: Kafka String Stream
  description: |
    Bidirectional Kafka connector with a single string column.
    Read raw string messages from a Kafka topic and write string messages back.
    Suitable for JSON, plain text, or any string-serialized data.
  authors:
    - name: Timeplus
      email: support@timeplus.com
  license: Apache-2.0
  homepage: https://github.com/timeplus-io/connectors
  repository: https://github.com/timeplus-io/connectors
  documentation: https://docs.timeplus.com/connectors/kafka

spec:
  category: bidirectional
  mode: streaming
  
  tags:
    - kafka
    - streaming
    - bidirectional
    - message-queue
    - sample
  
  compatibility:
    protonVersion: ">=3.0.0"
    pythonVersion: ">=3.9"
  
  dependencies:
    - kafka-python>=2.0.2
  
  schema:
    columns:
      - name: data
        type: string
        nullable: false
        description: The raw string message content

  functions:
    read:
      name: kafka_string_read
      description: Read string messages from Kafka topic as a continuous stream
    write:
      name: kafka_string_write
      description: Write string messages to Kafka topic

  configTemplate:
    - name: bootstrap_servers
      description: Kafka broker addresses (comma-separated for multiple brokers)
      example: "localhost:9092"
    - name: read_topic
      description: Kafka topic to read from
      example: "input-topic"
    - name: write_topic
      description: Kafka topic to write to
      example: "output-topic"
    - name: group_id
      description: Consumer group ID for offset tracking
      example: "timeplus-consumer-group"
    - name: auto_offset_reset
      description: Where to start consuming if no offset exists (earliest or latest)
      example: "earliest"

  pythonCode: |
    from kafka import KafkaConsumer, KafkaProducer

    bootstrap_servers = "redpanda:9092"
    read_topic = "test-topic"
    write_topic = "test-topic"
    group_id = "timeplus-consumer-group"
    auto_offset_reset = "earliest"
    
    def kafka_string_read():
        consumer = KafkaConsumer(
            read_topic,
            bootstrap_servers=bootstrap_servers,
            auto_offset_reset=auto_offset_reset,
            enable_auto_commit=True,
            group_id=group_id,
            value_deserializer=lambda m: m.decode("utf-8") if m else "",
        )
        try:
            for msg in consumer:
                yield [msg.value]
        finally:
            consumer.close()
    
    def kafka_string_write(values):
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: v.encode("utf-8") if v else b"",
        )
        try:
            for row in values:
                data = row if row is not None else ""
                producer.send(write_topic, data)
            producer.flush()
        finally:
            producer.close()

  examples:
    - title: Read All Messages
      description: Stream all messages from the configured Kafka topic
      code: |
        SELECT * FROM kafka_string_stream;
    
    - title: Read with Filter
      description: Filter messages containing specific text
      code: |
        SELECT data 
        FROM kafka_string_stream 
        WHERE data LIKE '%error%';
    
    - title: Write Single Message
      description: Send a single message to Kafka
      code: |
        INSERT INTO kafka_string_stream(data) 
        VALUES ('Hello, Kafka!');
    
    - title: Write JSON String
      description: Send a JSON object as a string
      code: |
        INSERT INTO kafka_string_stream(data) 
        VALUES ('{"event":"click","user_id":123,"timestamp":"2025-01-17T00:00:00Z"}');
    
    - title: Stream Processing - Pass Through
      description: Read from input, write to output (different topics require separate connectors)
      code: |
        INSERT INTO kafka_string_stream(data)
        SELECT data FROM kafka_string_stream;
    
    - title: Transform and Write
      description: Transform data and write back
      code: |
        INSERT INTO kafka_string_stream(data)
        SELECT upper(data) 
        FROM kafka_string_stream 
        WHERE length(data) > 0;
    
    - title: Parse JSON and Aggregate
      description: Parse JSON strings and perform aggregation
      code: |
        SELECT 
          json_extract_string(data, '$.event') as event_type,
          count(*) as cnt
        FROM kafka_string_stream
        GROUP BY event_type;
```

---