import unittest

from amzmail.classifier import extract_payment


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
