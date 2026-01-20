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
                yield [col1_value, col2_value, ...]
        finally:
            client.close()
    
    # For SINK - receive iterator of row lists:
    def write_func(values):
        client = setup_client()
        try:
            for row in values:
                client.send(row[0], row[1], ...)
            client.flush()
        finally:
            client.close()

  examples:
    - title: <Example Name>
      code: |
        <SQL example>
```

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

---

## MY REQUIREMENTS:

[Describe what you want here. Examples:]

**Example 1 - Source:**
```
Read JSON messages from MQTT broker at mqtt.example.com:1883
Topic: sensors/temperature
Fields: sensor_id (string), temperature (float), timestamp (datetime)
```

**Example 2 - Sink:**
```
Send notifications to a webhook at https://api.example.com/notify
Fields: title (string), body (string), priority (int)
```

**Example 3 - Bidirectional:**
```
Read from and write to MongoDB collection "events" 
Database: mydb at mongodb://localhost:27017
Fields: _id (string), type (string), payload (string), created_at (datetime)
```

---

**YOUR TURN - Enter your requirements below:**

