#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TIMEPLUS_HTTP_URL="${TIMEPLUS_HTTP_URL:-http://localhost:8123}"
STREAM_NAME="${STREAM_NAME:-ci_smoke_stream}"
SQL_FILE="${SQL_FILE:-/tmp/proton_smoke_install.sql}"

wait_for_proton() {
  local max_retry=30
  local i
  for i in $(seq 1 "${max_retry}"); do
    if curl -fsS "${TIMEPLUS_HTTP_URL}/?query=SELECT%201" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  echo "Proton HTTP endpoint not ready after $((max_retry * 2))s: ${TIMEPLUS_HTTP_URL}" >&2
  return 1
}

generate_sql() {
  ROOT_DIR_ENV="${ROOT_DIR}" SQL_FILE_ENV="${SQL_FILE}" STREAM_NAME_ENV="${STREAM_NAME}" python3 - <<'PY'
import importlib.util
import os
import pathlib

root = pathlib.Path(os.environ["ROOT_DIR_ENV"])
module_path = root / "registry" / "utils" / "sql_generator.py"
spec = importlib.util.spec_from_file_location("sql_generator", module_path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

manifest = {
    "metadata": {
        "name": "ci-smoke-connector",
        "namespace": "ci",
        "version": "0.0.1",
    },
    "spec": {
        "category": "source",
        "mode": "streaming",
        "schema": {
            "columns": [
                {"name": "value", "type": "int32"},
            ],
        },
        "functions": {
            "read": {"name": "smoke_read", "description": "Emit one row for CI smoke"},
        },
        "pythonCode": "def smoke_read():\n    return iter([(1,)])\n",
    },
}

sql = module.generate_install_sql(manifest, stream_name=os.environ["STREAM_NAME_ENV"])
pathlib.Path(os.environ["SQL_FILE_ENV"]).write_text(sql + "\n", encoding="utf-8")
PY
}

run_query() {
  local query="$1"
  curl -fsS "${TIMEPLUS_HTTP_URL}/" --data-binary "${query}" >/dev/null
}

run_sql_file() {
  local file="$1"
  curl -fsS "${TIMEPLUS_HTTP_URL}/" --data-binary @"${file}" >/dev/null
}

query_text() {
  local encoded_query="$1"
  curl -fsS "${TIMEPLUS_HTTP_URL}/?query=${encoded_query}"
}

main() {
  wait_for_proton
  generate_sql

  run_query "DROP STREAM IF EXISTS ${STREAM_NAME};"
  run_sql_file "${SQL_FILE}"

  local result
  result="$(query_text "SELECT%20*%20FROM%20${STREAM_NAME}%20LIMIT%201%20FORMAT%20CSV" | tr -d '\r\n')"
  if [[ "${result}" != "1" ]]; then
    echo "Unexpected smoke query result: '${result}'" >&2
    return 1
  fi

  run_query "DROP STREAM IF EXISTS ${STREAM_NAME};"
  echo "Proton smoke test passed."
}

main "$@"
