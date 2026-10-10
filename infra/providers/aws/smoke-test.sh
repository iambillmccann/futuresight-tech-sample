#!/usr/bin/env bash
set -euo pipefail

frontend_url="${1:?Usage: smoke-test.sh FRONTEND_URL BACKEND_URL}"
backend_url="${2:?Usage: smoke-test.sh FRONTEND_URL BACKEND_URL}"

curl --fail --silent --show-error "$frontend_url/" >/dev/null
for endpoint in health ready version; do
  curl --fail --silent --show-error "$backend_url/$endpoint" >/dev/null
done

printf 'Frontend and backend health endpoints are reachable.\n'
