"""
Shared pytest fixtures for the Online Boutique gRPC test suite.

Assumes the microservices-demo stack is deployed to a local Kubernetes
cluster (e.g. Docker Desktop's built-in cluster) via:

    kubectl apply -f ./release/kubernetes-manifests.yaml

and that the following services are reachable via kubectl port-forward
(run each in a background terminal):

    kubectl port-forward svc/checkoutservice 5050:5050 &
    kubectl port-forward svc/paymentservice 50051:50051 &
    kubectl port-forward svc/cartservice 7070:7070 &

Generated stub modules (checkout_pb2, checkout_pb2_grpc, etc.) must be built
from the .proto files under protos/ first, e.g.:

    python -m grpc_tools.protoc -I protos \
        --python_out=tests/generated \
        --grpc_python_out=tests/generated \
        protos/demo.proto

The Online Boutique repo defines all services in a single demo.proto under
package `hipstershop`, so in practice you'll typically import one generated
module pair (demo_pb2, demo_pb2_grpc) rather than separate files per service.
"""

import sys
from pathlib import Path

# The generated gRPC modules import demo_pb2 as a top-level module. Add both
# the tests package and generated-stub directory so `pytest tests/ -v` works
# without requiring a manual PYTHONPATH export.
TESTS_DIR = Path(__file__).parent
for import_path in (TESTS_DIR, TESTS_DIR / "generated"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import grpc
import pytest

CHECKOUT_ADDR = "localhost:5050"
PAYMENT_ADDR = "localhost:50051"
CART_ADDR = "localhost:7070"


@pytest.fixture(scope="session")
def checkout_channel():
    channel = grpc.insecure_channel(CHECKOUT_ADDR)
    yield channel
    channel.close()


@pytest.fixture(scope="session")
def payment_channel():
    channel = grpc.insecure_channel(PAYMENT_ADDR)
    yield channel
    channel.close()


@pytest.fixture(scope="session")
def cart_channel():
    channel = grpc.insecure_channel(CART_ADDR)
    yield channel
    channel.close()


@pytest.fixture(autouse=True)
def seed_test_cart(cart_channel):
    """Give the shared happy-path user one item before each test.

    Checkout empties the cart after a successful order, so this must run per
    test rather than once per session. The empty-cart test uses a different
    user ID and remains unaffected.
    """
    from generated import demo_pb2, demo_pb2_grpc

    stub = demo_pb2_grpc.CartServiceStub(cart_channel)
    stub.AddItem(demo_pb2.AddItemRequest(
        user_id="test-user-001",
        item=demo_pb2.CartItem(product_id="OLJCESPC7Z", quantity=1),
    ), timeout=5.0)


@pytest.fixture
def sample_order_request():
    """
    A minimal, valid PlaceOrder request. Field names/shape match the
    hipstershop.PlaceOrderRequest message in demo.proto — adjust field
    values (user_id, address, card details, currency) to match whatever
    test data your local instance's Cart/ProductCatalog services expect.
    """
    from generated import demo_pb2  # generated stub, see module docstring

    return demo_pb2.PlaceOrderRequest(
        user_id="test-user-001",
        user_currency="USD",
        address=demo_pb2.Address(
            street_address="1600 Amphitheatre Parkway",
            city="Mountain View",
            state="CA",
            country="USA",
            zip_code=94043,
        ),
        email="kulsum.test@example.com",
        credit_card=demo_pb2.CreditCardInfo(
            credit_card_number="4432801561520454",  # Online Boutique's known-valid test card
            credit_card_cvv=672,
            credit_card_expiration_year=2030,
            credit_card_expiration_month=1,
        ),
    )
