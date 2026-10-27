"""lambda_function.py の入力検証を検証する stdlib のみのテスト。

boto3/botocore が無い環境でも動くよう、import 前にスタブを差し込む。
実行: python3 test_lambda_validation.py
"""
import json
import sys
import types
import unittest
from unittest import mock

# ---- boto3 / botocore スタブ（import 前に必ず配置）----
boto3_stub = types.ModuleType("boto3")
boto3_stub.client = lambda *args, **kwargs: mock.Mock(name="ses")
botocore_stub = types.ModuleType("botocore")
botocore_exceptions_stub = types.ModuleType("botocore.exceptions")


class ClientError(Exception):
    def __init__(self, message="simulated"):
        self.response = {"Error": {"Message": message}}
        super().__init__(message)


botocore_exceptions_stub.ClientError = ClientError
botocore_stub.exceptions = botocore_exceptions_stub
sys.modules.setdefault("boto3", boto3_stub)
sys.modules.setdefault("botocore", botocore_stub)
sys.modules.setdefault("botocore.exceptions", botocore_exceptions_stub)

import lambda_function  # noqa: E402


def make_event(body, headers=None):
    return {
        "body": json.dumps(body, ensure_ascii=False),
        "headers": headers or {},
    }


VALID_CORPORATE = {
    "formType": "corporate",
    "メール": "someone@example.com",
    "会社名": "株式会社サンプル",
    "担当者": "山田",
    "種別": "AI活用",
    "内容": "相談したいです",
    "submissionId": "0f0e6d1a-1b2c-4d3e-9f8a-7b6c5d4e3f21",
    "source": "home-hero",
    "page": "/",
}


class LambdaValidationTest(unittest.TestCase):
    def setUp(self):
        self.ses = mock.Mock()
        self.ses.send_email.side_effect = lambda **kw: {"MessageId": "stub-id"}
        lambda_function.ses = self.ses

    def test_valid_submission_sends_two_emails(self):
        result = lambda_function.lambda_handler(make_event(VALID_CORPORATE), mock.Mock())
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(self.ses.send_email.call_count, 2)
        first, second = self.ses.send_email.call_args_list
        self.assertEqual(
            first.kwargs["Destination"]["ToAddresses"], [lambda_function.RECIPIENT_EMAIL]
        )
        self.assertEqual(
            second.kwargs["Destination"]["ToAddresses"], ["someone@example.com"]
        )

    def test_honeypot_is_silently_dropped(self):
        poisoned = dict(VALID_CORPORATE, website="http://spam.example")
        result = lambda_function.lambda_handler(make_event(poisoned), mock.Mock())
        self.assertEqual(result["statusCode"], 200)
        self.ses.send_email.assert_not_called()

    def test_invalid_email_is_rejected_without_sending(self):
        bad = dict(VALID_CORPORATE, メール="victim@evil@example.com")
        result = lambda_function.lambda_handler(make_event(bad), mock.Mock())
        self.assertEqual(result["statusCode"], 400)
        self.ses.send_email.assert_not_called()

    def test_unknown_form_type_is_rejected(self):
        bad = dict(VALID_CORPORATE, formType="mass-mail")
        result = lambda_function.lambda_handler(make_event(bad), mock.Mock())
        self.assertEqual(result["statusCode"], 400)
        self.ses.send_email.assert_not_called()

    def test_cross_site_origin_is_rejected(self):
        result = lambda_function.lambda_handler(
            make_event(VALID_CORPORATE, {"Origin": "https://evil.example"}), mock.Mock()
        )
        self.assertEqual(result["statusCode"], 400)
        self.ses.send_email.assert_not_called()

    def test_own_origin_is_allowed(self):
        result = lambda_function.lambda_handler(
            make_event(VALID_CORPORATE, {"Origin": "https://www.onewonder.co.jp"}),
            mock.Mock(),
        )
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(self.ses.send_email.call_count, 2)

    def test_unknown_fields_are_stripped_not_forwarded(self):
        payload = dict(VALID_CORPORATE, injection="<script>alert(1)</script>")
        lambda_function.lambda_handler(make_event(payload), mock.Mock())
        sent_body = self.ses.send_email.call_args_list[0].kwargs["Message"]["Body"]["Text"]["Data"]
        self.assertNotIn("injection", sent_body)
        self.assertNotIn("<script>", sent_body)

    def test_oversized_body_is_rejected(self):
        payload = dict(VALID_CORPORATE, 内容="あ" * 9000)
        result = lambda_function.lambda_handler(make_event(payload), mock.Mock())
        self.assertEqual(result["statusCode"], 400)
        self.ses.send_email.assert_not_called()

    def test_error_response_hides_internal_details(self):
        self.ses.send_email.side_effect = ClientError("Secret SES detail")
        result = lambda_function.lambda_handler(make_event(VALID_CORPORATE), mock.Mock())
        self.assertEqual(result["statusCode"], 500)
        self.assertNotIn("Secret SES detail", result["body"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
