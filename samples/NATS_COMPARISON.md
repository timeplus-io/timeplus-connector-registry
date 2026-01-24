# NATS Core vs JetStream Comparison

This guide helps you choose between NATS Core and NATS JetStream connectors based on your use case.

## Quick Decision Matrix

| Use Case | Recommended | Why |
|----------|-------------|-----|
| Real-time pub/sub, no persistence needed | NATS Core | Simpler, faster, lower overhead |
| Need message replay/history | JetStream | Provides message persistence |
| At-least-once delivery guarantee | JetStream | Acknowledgment and redelivery |
| High-throughput, low latency | NATS Core | Minimal overhead, no disk I/O |
| Audit trail/compliance requirements | JetStream | Messages are persisted |
| Event sourcing | JetStream | Can replay events from the beginning |
| Fire-and-forget messaging | NATS Core | No acknowledgment overhead |
| Consumer may disconnect/reconnect | JetStream | Durable consumers maintain position |

## Feature Comparison

### NATS Core

**Pros:**
- ✅ Ultra-low latency (microseconds)
- ✅ Minimal resource usage
- ✅ Simple setup - no stream configuration needed
- ✅ At-most-once delivery (fast, no duplicates)
- ✅ Perfect for real-time data streaming

**Cons:**
- ❌ No message persistence
- ❌ If consumer is offline, messages are lost
- ❌ No replay capability
- ❌ No delivery guarantees

**Best For:**
- IoT sensor data streaming
- Real-time metrics/monitoring
- Live dashboards
- Temporary notifications
- High-frequency updates where missing occasional messages is acceptable

**Example:**
```sql
-- Read real-time sensor data
SELECT nats_subject, message_data, received_at
FROM nats_read_connector
WHERE nats_subject = 'sensor.temperature';
```

### NATS JetStream

**Pros:**
- ✅ Message persistence (survives restarts)
- ✅ At-least-once delivery guarantee
- ✅ Message replay from any point
- ✅ Durable consumers (maintain position)
- ✅ Sequence numbers for ordering
- ✅ Configurable retention policies
- ✅ Multiple consumers can read same messages

**Cons:**
- ❌ Higher latency (disk I/O)
- ❌ More resource intensive
- ❌ Requires stream configuration
- ❌ Possible duplicate messages (at-least-once)

**Best For:**
- Event sourcing
- Order processing
- Financial transactions
- Audit logs
- Critical events that must not be lost
- Systems requiring message replay
- Microservices with guaranteed delivery needs

**Example:**
```sql
-- Read persisted events with sequence numbers
SELECT nats_subject, message_data, sequence, received_at
FROM nats_jetstream_read_connector
ORDER BY sequence;
```

## Performance Comparison

| Metric | NATS Core | JetStream |
|--------|-----------|-----------|
| Latency | < 1ms | 1-5ms |
| Throughput | Millions/sec | Hundreds of thousands/sec |
| Memory | Very low | Moderate (buffers) |
| Disk | None | Required for persistence |
| CPU | Minimal | Moderate (encoding/acks) |

## Configuration Comparison

### NATS Core Setup

**Server Setup:**
```yaml
nats:
  image: nats:latest
  ports:
    - "4222:4222"
```

**No additional setup needed!** Just start publishing/subscribing.

### JetStream Setup

**Server Setup:**
```yaml
nats-js:
  image: nats:latest
  command: -js
  ports:
    - "4223:4222"
```

**Requires stream creation:**
```bash
make nats-js-stream-create
```

## Delivery Guarantees

### NATS Core: At-Most-Once
```
Publisher → NATS → Subscriber
            ↓
         (no ack)

Result: Fast, but message may be lost if subscriber is offline
```

### JetStream: At-Least-Once
```
Publisher → NATS → JetStream → Subscriber
            ↓        ↓           ↓
          (ack)   (persist)    (ack)

Result: Reliable, but may deliver duplicates on retry
```

## Code Examples

### Use Case: IoT Temperature Sensors (Choose NATS Core)

**Why:** High-frequency updates, occasional loss acceptable, low latency critical

```sql
-- Write connector: Publish sensor readings
INSERT INTO nats_write_connector(message_string)
SELECT to_json_string(map(
  'sensor_id', sensor_id,
  'temperature', temperature,
  'timestamp', to_string(now())
))
FROM sensor_readings;

-- Read connector: Real-time temperature monitoring
SELECT
  window_start,
  message_data:sensor_id AS sensor_id,
  avg(message_data:temperature::float64) AS avg_temp
FROM tumble(nats_read_connector, received_at, 10s)
GROUP BY window_start, sensor_id;
```

### Use Case: E-commerce Orders (Choose JetStream)

**Why:** Cannot lose orders, need audit trail, may need replay

```sql
-- Write connector: Persist orders with guaranteed delivery
INSERT INTO nats_jetstream_write_connector(message_string)
SELECT to_json_string(map(
  'order_id', order_id,
  'customer_id', customer_id,
  'total', total,
  'items', items,
  'timestamp', to_string(now())
))
FROM orders_stream;

-- Read connector: Process orders with sequence tracking
SELECT
  sequence,
  message_data:order_id AS order_id,
  message_data:customer_id AS customer_id,
  message_data:total AS total,
  received_at
FROM nats_jetstream_read_connector
WHERE message_data:total::float64 > 100;
```

## Migration Path

### From Core to JetStream

If you start with NATS Core and later need persistence:

1. Create a JetStream stream
2. Change connector from `nats_read_connector` to `nats_jetstream_read_connector`
3. Update subject names if needed (e.g., `sensor.data` → `events.sensor.data`)
4. No changes needed to application logic

### From JetStream to Core

If you want to reduce overhead for high-frequency data:

1. Change connector from `nats_jetstream_read_connector` to `nats_read_connector`
2. Remove stream configuration
3. Accept that messages won't be persisted

## Hybrid Approach

You can use both in the same system!

**Example: Smart Factory**

```sql
-- High-frequency sensor data → NATS Core
-- (Real-time monitoring, some loss acceptable)
SELECT * FROM nats_read_connector
WHERE nats_subject LIKE 'sensor.%';

-- Critical events → JetStream
-- (Maintenance alerts, must not be lost)
SELECT * FROM nats_jetstream_read_connector
WHERE nats_subject LIKE 'events.alert.%';
```

## Cost Considerations

### NATS Core
- Lower infrastructure costs (no disk storage needed)
- Minimal CPU and memory
- Can handle more messages per dollar

### JetStream
- Higher infrastructure costs (disk storage required)
- More CPU for acknowledgments and persistence
- Worth the cost when messages have business value

## Recommendation Summary

**Choose NATS Core when:**
- You need maximum throughput and minimum latency
- Message loss is acceptable (you'll get the next one soon)
- No compliance/audit requirements
- Temporary/ephemeral data

**Choose JetStream when:**
- You cannot afford to lose messages
- Need to replay historical data
- Compliance/audit requirements
- Event sourcing architecture
- Consumers may be offline temporarily

**Still not sure?** Start with JetStream. You can always optimize later by moving non-critical data to NATS Core.
