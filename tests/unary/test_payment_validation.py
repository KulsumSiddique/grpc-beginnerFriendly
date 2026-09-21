"""
Direct validation tests against PaymentService.Charge — isolated from the
full CheckoutService chain so failures here are unambiguous (i.e. a failure
proves PaymentService's own validation is wrong, not some upstream service
sending it bad data).
"""

import grpc
import pytest


def _charge_request(demo_pb2, units=100, nanos=0, currency="USD",
                     card_number="4432801561520454", cvv=672,
                     exp_year=2030, exp_month=1):
    return demo_pb2.ChargeRequest(
        amount=demo_pb2.Money(currency_code=currency, units=units, nanos=nanos),
        credit_card=demo_pb2.CreditCardInfo(
            credit_card_number=card_number,
            credit_card_cvv=cvv,
            credit_card_expiration_year=exp_year,
            credit_card_expiration_month=exp_month,
        ),
    )


class TestPaymentValidation:
    def test_charge_invalid_card_number_format_rejected(self, payment_channel):
        from generated import demo_pb2, demo_pb2_grpc

        stub = demo_pb2_grpc.PaymentServiceStub(payment_channel)
        request = _charge_request(demo_pb2, card_number="not-a-card-number")

        with pytest.raises(grpc.RpcError) as exc_info:
            stub.Charge(request)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT

    def test_charge_expired_card_rejected(self, payment_channel):
        from generated import demo_pb2, demo_pb2_grpc

        stub = demo_pb2_grpc.PaymentServiceStub(payment_channel)
        request = _charge_request(demo_pb2, exp_year=2020, exp_month=1)

        with pytest.raises(grpc.RpcError) as exc_info:
            stub.Charge(request)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT

    def test_charge_invalid_cvv_length_rejected(self, payment_channel):
        """
        CVV is typically 3-4 digits. A single-digit or absurdly long CVV
        should be rejected at the validation layer, not passed through.
        """
        from generated import demo_pb2, demo_pb2_grpc

        stub = demo_pb2_grpc.PaymentServiceStub(payment_channel)
        request = _charge_request(demo_pb2, cvv=7)

        with pytest.raises(grpc.RpcError) as exc_info:
            stub.Charge(request)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT

    def test_charge_negative_amount_rejected(self, payment_channel):
        """
        A negative charge amount should never be accepted — this is the
        kind of input validation gap that matters most in a payments
        context specifically, since a bug here has real financial impact
        rather than just a broken UI.
        """
        from generated import demo_pb2, demo_pb2_grpc

        stub = demo_pb2_grpc.PaymentServiceStub(payment_channel)
        request = _charge_request(demo_pb2, units=-50)

        with pytest.raises(grpc.RpcError) as exc_info:
            stub.Charge(request)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT

    def test_charge_unsupported_card_brand_rejected(self, payment_channel):
        """
        Online Boutique's mock PaymentService only supports Visa/Mastercard
        prefixes. A card number with a valid Luhn checksum but an
        unsupported brand prefix should be rejected with a clear code, not
        silently charged or crash with UNKNOWN.
        """
        from generated import demo_pb2, demo_pb2_grpc

        stub = demo_pb2_grpc.PaymentServiceStub(payment_channel)
        # Example Diners Club-prefixed number, unsupported by the mock service.
        request = _charge_request(demo_pb2, card_number="30569309025904")

        with pytest.raises(grpc.RpcError) as exc_info:
            stub.Charge(request)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT