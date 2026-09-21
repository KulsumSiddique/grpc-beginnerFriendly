# Architecture Notes — Checkout & Payment Flow

## Call chain under test

```text
Client
  └─→ CheckoutService.PlaceOrder
        ├─→ CartService.GetCart
        ├─→ ProductCatalogService.GetProduct
        ├─→ ShippingService.GetQuote
        ├─→ CurrencyService.Convert
        ├─→ PaymentService.Charge
        ├─→ ShippingService.ShipOrder
        ├─→ CartService.EmptyCart
        └─→ EmailService.SendOrderConfirmation
```

Checkout is a synchronous orchestrator, so the tests focus on deadline
propagation, validation, downstream failures, and payment safety.

## Local Kubernetes ports

| Service | Local port | Protocol |
|---|---:|---|
| CheckoutService | 5050 | gRPC |
| PaymentService | 50051 | gRPC |
| CartService | 7070 | gRPC |
| Frontend | 8080 | HTTP |

Checkout, payment, and cart are Kubernetes `ClusterIP` services. The Python
tests reach them through `kubectl port-forward`; they are not directly
reachable from the host.

On Apple Silicon, Skaffold builds for `linux/arm64`. The cartservice Dockerfile
uses Docker BuildKit's target architecture instead of forcing an amd64 binary.

## Test scope

- Checkout happy paths and invalid-request handling.
- Payment card, expiry, CVV, brand, and amount validation.
- Deadline behavior across the checkout chain.
- Plaintext gRPC locally, matching the demo's default configuration.

Streaming RPCs and production TLS/mTLS are outside this local test scope.
