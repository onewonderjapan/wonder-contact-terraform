"""Offline contact-contract tests: every SES call is captured in memory."""
import importlib.util
import json
import logging
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


class FakeSes:
    def __init__(self):
        self.messages = []

    def send_email(self, **kwargs):
        self.messages.append(kwargs)
        return {"MessageId": f"fixture-{len(self.messages)}"}


class ContractTest(unittest.TestCase):
    def setUp(self):
        self.ses = FakeSes()
        modules = {
            "boto3": types.SimpleNamespace(client=lambda *args, **kwargs: self.ses),
            "botocore": types.ModuleType("botocore"),
            "botocore.exceptions": types.SimpleNamespace(ClientError=type("ClientError", (Exception,), {})),
        }
        self.module_patch = patch.dict(sys.modules, modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.environment_patch = patch.dict(os.environ, {
            "SENDER_EMAIL": "sender@example.invalid",
            "RECIPIENT_EMAIL": "owner@example.invalid",
            "EMAIL_CONFIG": "{}",
        }, clear=True)
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)
        spec = importlib.util.spec_from_file_location("offline_contact", Path(__file__).parents[1] / "lambda_function.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def submit(self, body):
        return self.module.lambda_handler({"body": json.dumps(body, ensure_ascii=False)}, None)

    def test_corporate_optional_fields_remain_in_content_without_new_keys(self):
        body = {"formType": "corporate", "会社名": "Synthetic Company", "担当者": "Fixture", "メール": "fixture@example.invalid", "内容": "質問\n検討段階: 情報収集\nNDA希望: はい"}
        response = self.submit(body)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(len(self.ses.messages), 2)
        self.assertIn(body["内容"], self.ses.messages[0]["Message"]["Body"]["Text"]["Data"])
        self.assertEqual(self.ses.messages[1]["Source"], "sender@example.invalid")

    def test_english_payload_preserves_legacy_contract(self):
        response = self.submit({"formType": "corporate", "会社名": "Fixture", "担当者": "Person", "メール": "fixture@example.invalid", "内容": "[Language: English]\nPlease discuss this synthetic requirement."})
        self.assertEqual(response["statusCode"], 200)
        self.assertIn("Language: English", self.ses.messages[0]["Message"]["Body"]["Text"]["Data"])
        # The legacy auto-reply is Japanese. Do not claim a live English back end.

    def test_request_logging_does_not_include_personal_content(self):
        with self.assertLogs(level=logging.INFO) as logs:
            self.submit({"formType": "individual", "氏名": "PRIVATE_FIXTURE_NAME", "メール": "private@example.invalid", "内容": "PRIVATE_FIXTURE_CONTENT"})
        self.assertNotIn("PRIVATE_FIXTURE", "\n".join(logs.output))
        self.assertNotIn("private@example.invalid", "\n".join(logs.output))

    def test_unknown_form_type_is_never_logged_as_user_input(self):
        with self.assertLogs(level=logging.INFO) as logs:
            self.submit({"formType": "PRIVATE_TYPE\nprivate@example.invalid", "内容": "Synthetic"})
        output = "\n".join(logs.output)
        self.assertNotIn("PRIVATE_TYPE", output)
        self.assertNotIn("private@example.invalid", output)
        self.assertIn("formType=unknown", output)

    def test_email_failure_logging_omits_provider_message_with_personal_data(self):
        failure = self.module.ClientError("SES rejected private@example.invalid")
        failure.response = {"Error": {"Message": "SES rejected private@example.invalid"}}
        with patch.object(self.ses, "send_email", side_effect=failure):
            with self.assertLogs(level=logging.INFO) as logs:
                response = self.submit({"formType": "individual", "メール": "private@example.invalid"})
        self.assertEqual(response["statusCode"], 500)
        self.assertNotIn("private@example.invalid", "\n".join(logs.output))
        self.assertEqual(self.ses.messages, [])

    def test_unexpected_failure_logging_omits_personal_exception_text(self):
        with patch.object(self.ses, "send_email", side_effect=RuntimeError("PRIVATE_FIXTURE_CONTENT")):
            with self.assertLogs(level=logging.INFO) as logs:
                response = self.submit({"formType": "individual"})
        self.assertEqual(response["statusCode"], 500)
        self.assertNotIn("PRIVATE_FIXTURE_CONTENT", "\n".join(logs.output))
        self.assertEqual(self.ses.messages, [])

    def test_invalid_json_does_not_send_any_email(self):
        response = self.module.lambda_handler({"body": "{"}, None)
        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(self.ses.messages, [])


if __name__ == "__main__":
    unittest.main()
