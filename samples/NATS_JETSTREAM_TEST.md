# NATS JetStream Connector Test Guide

This guide helps you test the NATS JetStream connectors after fixing the TimeoutError issue.

## Test Status

✅ **Stream Created**: EVENTS stream is running
✅ **Test Messages**: 7 messages published to events.data
✅ **Bug Fixed**: Replaced `nats.js.errors.TimeoutError` with `asyncio.TimeoutError`

## Quick Test

### 1. Test Reading Messages

Run this SQL in Timeplus:

```sql
-- Read all messages from JetStream
SELECT * FROM nats_jetstream_read_connector;
```

**Expected Result:**
You should see 7 rows with test messages, including:
- `nats_subject`: "events.data"
- `message_data`: JSON strings like `{"test_id": 1, "message": "Test message 1"}`
- `sequence`: Numbers 1-7
- `received_at`: Timestamps

### 2. Test Writing Messages

```sql
-- Write a simple message
INSERT INTO nats_jetstream_write_connector(message_string)
VALUES ('{"event": "test", "timestamp": "2024-01-01"}');

-- Verify it was written by reading again
SELECT * FROM nats_jetstream_read_connector
WHERE message_data LIKE '%test%';
```

### 3. Test Stream Processing

```sql
-- Read, transform, and write back
INSERT INTO nats_jetstream_write_connector(message_string)
SELECT
  to_json_string(map(
    'original_subject', nats_subject,
    'original_sequence', sequence,
    'processed_at', to_string(now()),
    'data', message_data
  )) AS message_string
FROM nats_jetstream_read_connector
WHERE sequence <= 3
LIMIT 3;
```

## Manual CLI Tests

### Publish More Messages

```bash
# Publish a single message
make nats-js-stream-pub

# Publish multiple messages with custom data
docker run --rm natsio/nats-box nats pub events.orders \
  '{"order_id": "123", "total": 99.99}' \
  --server nats://host.docker.internal:4223

docker run --rm natsio/nats-box nats pub events.users \
  '{"user_id": "456", "action": "login"}' \
  --server nats://host.docker.internal:4223
```

### Monitor Stream

```bash
# Check stream info
make nats-js-stream-info

# List all streams
make nats-js-stream-list
```

### Subscribe to Messages (Real-time)

Open a separate terminal and run:

```bash
make nats-js-stream-sub
```

Then publish messages from another terminal and watch them appear.

## Troubleshooting

### Issue: "stream not found"

**Solution:**
```bash
make nats-js-stream-create
```

### Issue: No messages appearing in Timeplus

**Check:**

1. Verify stream has messages:
   ```bash
   make nats-js-stream-info | grep "Messages:"
   ```

2. Check connector is using correct URL (`nats://nats-js:4222`)

3. Verify container can reach NATS:
   ```bash
   docker exec -it <timeplus-container> ping nats-js
   ```

### Issue: Consumer not advancing

The consumer maintains its position. To reset and read from the beginning:

1. Delete and recreate the stream:
   ```bash
   make nats-js-stream-delete
   make nats-js-stream-create
   ```

2. Or change the consumer name in the connector YAML

## Advanced Testing

### Test with Different Subjects

```sql
-- Publish to different subjects
INSERT INTO nats_jetstream_write_connector(message_string)
VALUES ('Message for events.orders');

-- All subjects matching events.> will be stored in the EVENTS stream
```

### Test Message Replay

```sql
-- Read messages ordered by sequence
SELECT sequence, message_data, received_at
FROM nats_jetstream_read_connector
ORDER BY sequence;
```

### Test Error Handling

```sql
-- Try to read from a non-existent stream
-- (Should fail gracefully with a clear error message)
```

### Test High Volume

```bash
# Publish 100 messages quickly
for i in {1..100}; do
  docker run --rm natsio/nats-box nats pub events.load_test \
    "{\"id\": $i}" \
    --server nats://host.docker.internal:4223 &
done
wait

# Then read them in Timeplus
```

```sql
SELECT count() FROM nats_jetstream_read_connector;
```

## Performance Testing

### Measure Read Throughput

```sql
SELECT
  count() AS total_messages,
  min(received_at) AS first_message,
  max(received_at) AS last_message,
  date_diff('second', min(received_at), max(received_at)) AS duration_seconds
FROM nats_jetstream_read_connector;
```

### Measure Write Throughput

```sql
-- Write 1000 messages
INSERT INTO nats_jetstream_write_connector(message_string)
SELECT to_string(number)
FROM numbers(1000);
```

## Verification Checklist

- [ ] Stream created successfully
- [ ] Can publish messages via CLI
- [ ] Can read messages in Timeplus
- [ ] Can write messages from Timeplus
- [ ] Sequence numbers are incrementing
- [ ] Timestamps are correct
- [ ] Consumer maintains position across queries
- [ ] No timeout errors in logs
- [ ] Messages persist across connector restarts

## Bug Fix Details

**Issue:** `module 'nats.js.errors' has no attribute 'TimeoutError'`

**Root Cause:** The nats-py library doesn't expose TimeoutError in `nats.js.errors`

**Fix Applied:**
- Changed from `nats.js.errors.TimeoutError` to `asyncio.TimeoutError`
- Added fallback exception handling for other timeout-like errors
- Version bumped from 1.0.2 to 1.0.3

**Lines Changed:** Line 156 in nats-jetstream-read-connector.yaml

## Next Steps

After verifying the connectors work:

1. ✅ Test basic read/write operations
2. ✅ Test with realistic data volumes
3. ✅ Monitor performance metrics
4. Consider creating production streams with appropriate retention policies
5. Document your specific use cases
6. Set up monitoring and alerting

## Support

If you encounter issues:

1. Check container logs:
   ```bash
   docker logs <timeplus-container-name>
   ```

2. Verify NATS JetStream is running:
   ```bash
   docker ps | grep nats-server-js
   ```

3. Check stream status:
   ```bash
   make nats-js-stream-info
   ```
