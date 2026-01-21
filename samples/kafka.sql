

CREATE EXTERNAL STREAM kafka_string_stream(data string)
AS $$
from kafka import KafkaConsumer, KafkaProducer

def kafka_string_read():
    consumer = KafkaConsumer(
        "input-topic",
        bootstrap_servers="redpanda:9092",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="timeplus-consumer-group",
        value_deserializer=lambda m: m.decode("utf-8") if m else "",
    )
    try:
        for msg in consumer:
            yield [msg.value]
    finally:
        consumer.close()

def kafka_string_write(values):
    producer = KafkaProducer(
        bootstrap_servers="redpanda:9092",
        value_serializer=lambda v: v.encode("utf-8") if v else b"",
    )
    try:
        for row in values:
            data = row if row is not None else ""
            producer.send("output-topic", data)
        producer.flush()
    finally:
        producer.close()

$$
SETTINGS type='python', mode='streaming', read_function_name='kafka_string_read', write_function_name='kafka_string_write';

CREATE RANDOM STREAM test_source(
  raw string default 'device'||to_string(rand()%4)
)
SETTINGS eps = 1;

-- adding SETTINGS min_insert_block_size_rows=1 to force Timeplus to process each row immediately
INSERT INTO kafka_string_stream(data) 
SELECT raw as data FROM test_source
SETTINGS min_insert_block_size_rows=1;

CREATE MATERIALIZED VIEW mv_kafka_string_sink
INTO kafka_string_stream
AS
SELECT raw as data FROM test_source
SETTINGS min_insert_block_size_rows=1;
