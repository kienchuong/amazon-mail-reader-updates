import unittest

from amzmail.classifier import classify, extract_payment


AMAZON_PAYABLE = "Amazon Accounts Payable <noreply@accounts-payable.amazon.com>"


class PaymentClassificationTests(unittest.TestCase):
    def assert_payment(self, subject: str) -> None:
        self.assertEqual(classify(AMAZON_PAYABLE, subject).category, "Payment")

    def assert_not_payment(self, subject: str) -> None:
        self.assertNotEqual(classify(AMAZON_PAYABLE, subject).category, "Payment")

    def test_remittance_advice_is_payment(self):
        self.assert_payment("Remittance Advice")

    def test_amazon_remittance_advice_is_payment(self):
        self.assert_payment("Amazon Remittance Advice")

    def test_forwarded_remittance_advice_is_payment(self):
        self.assert_payment("FW: RE: Your Remittance Advice")

    def test_remittance_subject_wins_over_unrelated_body_keywords(self):
        result = classify(
            AMAZON_PAYABLE,
            "Remittance Advice - Example Payment# 100001234567890",
            "Security alert and account locked wording from the quoted thread",
        )
        self.assertEqual(result.category, "Payment")

    def test_payment_declined_is_not_payment(self):
        result = classify(
            AMAZON_PAYABLE,
            "Action required: payment declined",
            "Quoted text: Remittance Advice and Payment amount: 280.35",
        )
        self.assertNotEqual(result.category, "Payment")

    def test_case_without_space_is_not_payment(self):
        self.assert_not_payment("RE:[CASE 21556110581] Payment issue")

    def test_case_with_remittance_advice_is_not_payment(self):
        result = classify(
            AMAZON_PAYABLE,
            "RE: [CASE 21556110581] Remittance Advice issue",
            "Payment amount: 280.35",
        )
        self.assertNotEqual(result.category, "Payment")

    def test_bare_case_is_not_payment(self):
        self.assert_not_payment("[CASE 21556110581] Payment")

    def test_repeated_reply_case_is_not_payment(self):
        self.assert_not_payment("RE: RE: [CASE 21556110581] Payment")

    def test_forwarded_reply_case_is_not_payment(self):
        self.assert_not_payment("FW: RE: [CASE 21556110581] Remittance Advice")

    def test_royalty_terms_update_is_not_payment(self):
        self.assert_not_payment("Merch on Demand Update to Royalty Terms")


class ExtractPaymentTests(unittest.TestCase):
    def test_amazon_accounts_payable_fields(self):
        text = """
        Our Supplier No.: 109702513
        Supplier site name: 5013561274_USD
        Payment number: 100001334607520
        Payment date: 29-Jul-2026
        Payment currency: USD
        Payment amount: 280.35
        """
        self.assertEqual(extract_payment(text), ("USD", 280.35, "100001334607520"))

    def test_dollar_amount_and_payment_id(self):
        text = "We've sent your payment of $1,234.56. Payment ID: ABC-12345"
        self.assertEqual(extract_payment(text), ("USD", 1234.56, "ABC-12345"))

    def test_european_euro_amount(self):
        text = "Payment reference: EU-98765\nPayment amount: €1.234,56"
        self.assertEqual(extract_payment(text), ("EUR", 1234.56, "EU-98765"))

    def test_currency_after_amount(self):
        text = "Payment ref: UK-12345\nAmount paid: 2,140.17 GBP"
        self.assertEqual(extract_payment(text), ("GBP", 2140.17, "UK-12345"))


if __name__ == "__main__":
    unittest.main()
