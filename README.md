# Timeplus Connector Registry

Central registry for Timeplus Custom Table Function (CTF) connectors. Think npm/PyPI for Timeplus data connectors.

## Features

- 📦 **Package Management** - Publish, version, and distribute connectors
- 🔍 **Discovery** - Search and browse connectors by category, tags, and keywords
- 📥 **Easy Installation** - Generate ready-to-run SQL for any connector
- 🏷️ **Categorization** - Source, Sink, and Bidirectional connectors
- ✅ **Verification** - Verified publisher badges for trusted connectors

## Quick Start

### Option 1: Docker Compose (Recommended)

The easiest way to run the registry locally:

```bash
# Start the registry API (UI is integrated)
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down

# Stop and remove data
docker-compose down -v
```

Once running:
- **UI**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### Option 2: Local Development

If you prefer to run without Docker:

```bash
# 1. Install Python dependencies
pip install -e .

# 2. Set up environment variables (copy and edit .env.example)
cp .env.example .env
# By default, it uses an embedded SQLite database (registry.db)

# 3. Start the server
uvicorn registry.main:app --reload
```



## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

## Using the API

### Register a Publisher

```bash
curl -X POST "http://localhost:8000/api/v1/register" \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": "timeplus",
    "display_name": "Timeplus",
    "email": "gang@timeplus.com",
    "password": "Password!"
  }'
```

Response:
```json
{
  "access_token":"eyJhbGciOiJIUzI1Ni......",
  "token_type":"bearer"}
```

### Login

```bash
curl -X POST "http://localhost:8000/api/v1/login" \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": "timeplus",
    "password": "Password!"
  }'
```

### Publish a Connector

```bash
# Using the sample connector
curl -X POST "http://localhost:8000/api/v1/connectors" \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/x-yaml" \
  --data-binary @samples/kafka-json-reader.yaml
```

### Search Connectors

```bash
# Search by keyword
curl "http://localhost:8000/api/v1/connectors?q=kafka"

# Filter by category
curl "http://localhost:8000/api/v1/connectors?category=source"

# Filter by tags
curl "http://localhost:8000/api/v1/connectors?tags=kafka,streaming"

# Combine filters
curl "http://localhost:8000/api/v1/connectors?q=json&category=source&tags=kafka"
```

### Get Connector Details

```bash
curl "http://localhost:8000/api/v1/connectors/mycompany/kafka-json-reader"
```

### Get Installation SQL

```bash
# Get SQL for latest version
curl "http://localhost:8000/api/v1/connectors/mycompany/kafka-json-reader/sql"

# Get SQL for specific version
curl "http://localhost:8000/api/v1/connectors/mycompany/kafka-json-reader/sql?version=1.0.0"

# Get SQL with custom stream name
curl "http://localhost:8000/api/v1/connectors/mycompany/kafka-json-reader/sql?name=my_kafka_stream"
```

### List Tags and Categories

```bash
# List all tags
curl "http://localhost:8000/api/v1/tags"

# Get category statistics
curl "http://localhost:8000/api/v1/categories"
```

## Project Structure

```
registry/
├── main.py              # FastAPI application entry point
├── config.py            # Configuration settings
├── database.py          # Database connection and session
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic schemas
├── routers/             # API route handlers
├── services/            # Business logic
└── utils/               # Utility functions
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./registry.db` | Database connection string |
| `SECRET_KEY` | (required) | JWT signing key - use a long random string |
| `DEBUG` | `false` | Enable debug mode |
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `8000` | Server bind port |

## License

Apache 2.0
