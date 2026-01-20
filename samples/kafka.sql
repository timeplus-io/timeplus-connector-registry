CREATE EXTERNAL STREAM kafka_string_stream(data string)
AS $$
from kafka import KafkaConsumer, KafkaProducer
import json

def kafka_string_read():
    consumer = KafkaConsumer(
        "input-topic",
        bootstrap_servers="redpanda:9092",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="timeplus-consumer-group",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )
    try:
        for msg in consumer:
            yield [msg.value]
    finally:
        consumer.close()

def kafka_string_write(values):
    producer = KafkaProducer(
        bootstrap_servers="redpanda:9092",
        value_serializer=lambda v: json.dumps({"value": v}).encode("utf-8"),
    )
    try:
        for row in values:
            data = row[0] if row[0] is not None else ""
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

INSERT INTO kafka_string_stream(data) 
SELECT raw as data FROM test_source;


create external stream py_kafka_stream
(
value int32
)
AS $$
from kafka import KafkaConsumer, KafkaProducer
import json
def py_kafka_read():
    consumer = KafkaConsumer(
        "py_read",
        bootstrap_servers="redpanda:9092",
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
        bootstrap_servers="redpanda:9092",
        value_serializer=lambda v: json.dumps({"value": v}).encode("utf-8"),
    )
    try:
        for v in values:
            producer.send("py_write", v)
        producer.flush()
    finally:
        producer.close()
$$
SETTINGS type='python', read_function_name='py_kafka_read', write_function_name='py_kafka_sink', mode='streaming';

INSERT INTO py_kafka_stream
VALUES (1), (2), (3), (4), (5);