#!/bin/bash
# Register all sample connectors to the registry
# Usage: ./scripts/register_samples.sh [API_URL]

set -e

# Configuration
API_URL="${1:-http://localhost:8000/api/v1}"
NAMESPACE="timeplus"
DISPLAY_NAME="Timeplus"
EMAIL="support@timeplus.com"
PASSWORD="Password!"
SAMPLES_DIR="$(dirname "$0")/../samples"

echo "==================================="
echo "Timeplus Connector Registry - Sample Registration"
echo "==================================="
echo "API URL: $API_URL"
echo "Namespace: $NAMESPACE"
echo ""

# Try to register publisher (ignore error if already exists)
echo "Registering publisher '$NAMESPACE'..."
REGISTER_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/register" \
    -H "Content-Type: application/json" \
    -d "{\"namespace\": \"$NAMESPACE\", \"display_name\": \"$DISPLAY_NAME\", \"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}")

HTTP_CODE=$(echo "$REGISTER_RESPONSE" | tail -n1)
BODY=$(echo "$REGISTER_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "201" ]; then
    echo "Publisher registered successfully."
    TOKEN=$(echo "$BODY" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
elif [ "$HTTP_CODE" = "409" ]; then
    echo "Publisher already exists. Logging in..."
    LOGIN_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/login" \
        -H "Content-Type: application/json" \
        -d "{\"namespace\": \"$NAMESPACE\", \"password\": \"$PASSWORD\"}")

    HTTP_CODE=$(echo "$LOGIN_RESPONSE" | tail -n1)
    BODY=$(echo "$LOGIN_RESPONSE" | sed '$d')

    if [ "$HTTP_CODE" != "200" ]; then
        echo "Error: Failed to login. HTTP $HTTP_CODE"
        echo "$BODY"
        exit 1
    fi
    TOKEN=$(echo "$BODY" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    echo "Login successful."
else
    echo "Error: Failed to register. HTTP $HTTP_CODE"
    echo "$BODY"
    exit 1
fi

if [ -z "$TOKEN" ]; then
    echo "Error: Failed to get access token"
    exit 1
fi

echo ""
echo "Publishing sample connectors..."
echo "-----------------------------------"

# Count for summary
SUCCESS=0
FAILED=0
SKIPPED=0

# Find and publish all YAML connector files
for yaml_file in "$SAMPLES_DIR"/*.yaml; do
    if [ ! -f "$yaml_file" ]; then
        continue
    fi

    filename=$(basename "$yaml_file")
    echo -n "Publishing $filename... "

    PUBLISH_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/connectors" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/x-yaml" \
        --data-binary "@$yaml_file")

    HTTP_CODE=$(echo "$PUBLISH_RESPONSE" | tail -n1)
    BODY=$(echo "$PUBLISH_RESPONSE" | sed '$d')

    if [ "$HTTP_CODE" = "201" ]; then
        echo "OK"
        SUCCESS=$((SUCCESS + 1))
    elif [ "$HTTP_CODE" = "409" ]; then
        echo "SKIPPED (already exists)"
        SKIPPED=$((SKIPPED + 1))
    else
        echo "FAILED (HTTP $HTTP_CODE)"
        echo "  Error: $BODY"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "==================================="
echo "Summary"
echo "==================================="
echo "Success: $SUCCESS"
echo "Skipped: $SKIPPED"
echo "Failed:  $FAILED"
echo ""

if [ "$FAILED" -gt 0 ]; then
    exit 1
fi

echo "Done!"
