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
# Start PostgreSQL, API server, and UI
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down

# Stop and remove data
docker-compose down -v
```

Once running:
- **UI**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### Option 2: Local Development

If you prefer to run without Docker:

```bash
# 1. Install PostgreSQL and create database
createdb registry

# 2. Install Python dependencies
pip install -e .

# 3. Set up environment variables (copy and edit .env.example)
cp .env.example .env
# Edit .env with your database credentials

# 4. Run database migrations
alembic upgrade head

# 5. Start the server
uvicorn registry.main:app --reload
```

### Option 3: Docker Compose for Database Only

Run PostgreSQL in Docker but the API locally (useful for development):

```bash
# Start only PostgreSQL
docker-compose up -d postgres

# Install dependencies and run locally
pip install -e .
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/registry"
export SECRET_KEY="dev-secret-key"
alembic upgrade head
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
    "namespace": "mycompany",
    "display_name": "My Company",
    "email": "dev@example.com",
    "password": "securepassword123"
  }'
```

Response:
```json
{
  "access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0aW1lcGx1cyIsImV4cCI6MTc2OTIxNjg3Nn0.AM9duB3EW03lOkYMF5qZnoux5Kf15NL7iIBTP-eq0D4",
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
  -d @samples/kafka-json-reader.yaml
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
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/registry` | PostgreSQL connection string |
| `SECRET_KEY` | (required) | JWT signing key - use a long random string |
| `DEBUG` | `false` | Enable debug mode |
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `8000` | Server bind port |

## License

Apache 2.0
