#!/usr/bin/env bash
#
# checkout_load_test.sh
#
# Runs ghz load tests against checkout and payment RPCs at increasing
# concurrency levels, saving an HTML report per scenario to perf/reports/.
#
# Usage:
#   chmod +x perf/checkout_load_test.sh
#   ./perf/checkout_load_test.sh
#
# Requires: ghz (https://ghz.sh) and a running local Online Boutique stack.
# Also requires: grpcurl (https://github.com/fullstorydev/grpcurl)

set -euo pipefail

PROTO_PATH="protos/demo.proto"
REQUESTS_PER_RUN=2000
CONCURRENCY_LEVELS=(10 25 50 100)
OUTPUT_DIR="perf/reports"

mkdir -p "$OUTPUT_DIR"

PAYMENT_PAYLOAD='{"amount":{"currency_code":"USD","units":100,"nanos":0},"credit_card":{"credit_card_number":"4432801561520454","credit_card_cvv":672,"credit_card_expiration_year":2030,"credit_card_expiration_month":1}}'
INVALID_PAYMENT_PAYLOAD='{"amount":{"currency_code":"USD","units":-50,"nanos":0},"credit_card":{"credit_card_number":"not-a-card-number","credit_card_cvv":7,"credit_card_expiration_year":2020,"credit_card_expiration_month":1}}'
CHECKOUT_PAYLOAD='{"user_id":"test-user-001","user_currency":"USD","address":{"street_address":"1600 Amphitheatre Parkway","city":"Mountain View","state":"CA","country":"USA","zip_code":94043},"email":"perf.test@example.com","credit_card":{"credit_card_number":"4432801561520454","credit_card_cvv":672,"credit_card_expiration_year":2030,"credit_card_expiration_month":1}}'

seed_cart() {
  echo "Seeding cart for test-user-001"
  grpcurl -plaintext -import-path protos -proto demo.proto \
    -d '{"user_id":"test-user-001","item":{"product_id":"OLJCESPC7Z","quantity":1}}' \
    localhost:7070 hipstershop.CartService/AddItem >/dev/null
}

run_checkout_case() {
  echo ""
  echo "============================================================"
  echo "SCENARIO: checkout_valid"
  echo "TARGET:   localhost:5050"
  echo "RPC:      hipstershop.CheckoutService.PlaceOrder"
  echo "============================================================"
  local index=0 total_levels=${#CONCURRENCY_LEVELS[@]}
  for c in "${CONCURRENCY_LEVELS[@]}"; do
    index=$((index + 1))
    seed_cart
    echo "[$index/$total_levels] Running concurrency=$c requests=$REQUESTS_PER_RUN"
    ghz --insecure --proto "$PROTO_PATH" \
      --call "hipstershop.CheckoutService.PlaceOrder" \
      -d "$CHECKOUT_PAYLOAD" -n "$REQUESTS_PER_RUN" -c "$c" -t 20s \
      -o "${OUTPUT_DIR}/checkout_valid_c${c}.html" -O html localhost:5050
    echo "[$index/$total_levels] COMPLETE report=${OUTPUT_DIR}/checkout_valid_c${c}.html"
  done
}

run_case() {
  local name="$1" call="$2" target="$3" payload="$4" timeout="$5" extra_args="${6:-}"
  echo ""
  echo "============================================================"
  echo "SCENARIO: $name"
  echo "TARGET:   $target"
  echo "RPC:      $call"
  echo "============================================================"
  local index=0 total_levels=${#CONCURRENCY_LEVELS[@]}
  for c in "${CONCURRENCY_LEVELS[@]}"; do
    index=$((index + 1))
    echo "[$index/$total_levels] Running concurrency=$c requests=$REQUESTS_PER_RUN"
    # shellcheck disable=SC2086
    ghz --insecure \
        --proto "$PROTO_PATH" \
        --call "$call" \
        -d "$payload" \
        -n "$REQUESTS_PER_RUN" \
        -c "$c" \
        -t "$timeout" \
        $extra_args \
        -o "${OUTPUT_DIR}/${name}_c${c}.html" \
        -O html \
        "$target"
    echo "[$index/$total_levels] COMPLETE report=${OUTPUT_DIR}/${name}_c${c}.html"
  done
}

echo "Requests per run: $REQUESTS_PER_RUN"
echo "Concurrency levels: ${CONCURRENCY_LEVELS[*]}"
echo ""

run_case "payment_valid" "hipstershop.PaymentService.Charge" "localhost:50051" "$PAYMENT_PAYLOAD" "20s"
run_case "payment_invalid" "hipstershop.PaymentService.Charge" "localhost:50051" "$INVALID_PAYMENT_PAYLOAD" "20s" "--count-errors"
run_checkout_case
run_case "checkout_deadline" "hipstershop.CheckoutService.PlaceOrder" "localhost:5050" "$CHECKOUT_PAYLOAD" "5ms" "--count-errors"

echo "All runs complete. Compare p50/p95/p99 latency and error counts across"
echo "the generated reports in ${OUTPUT_DIR}/."
