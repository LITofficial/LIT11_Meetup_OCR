import base64
import json
import unittest
from unittest.mock import patch

import requests

from cu_client import CUClient, CUError


def mock_response(code: int, body: dict) -> requests.Response:
    response = requests.Response()
    response.status_code = code
    response._content = json.dumps(body).encode("utf-8")
    response.headers["Content-Type"] = "application/json"
    return response


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


class CUClientTests(unittest.TestCase):
    ENDPOINT = "https://plant88588672-6475-resource.cognitiveservices.azure.com"

    def test_rejects_non_azure_endpoint_to_protect_secret(self):
        with self.assertRaises(CUError):
            CUClient("https://untrusted.example.com", api_key="not-a-real-key")
        with self.assertRaises(CUError):
            CUClient("http://plant88588672-6475-resource.cognitiveservices.azure.com")

    def test_configure_defaults_only_touches_our_models(self):
        fake = FakeSession([mock_response(200, {"modelDeployments": {}})])
        client = CUClient(self.ENDPOINT, api_key="fake-key", session=fake)
        client.configure_model_defaults("my-mini", "my-small")
        method, url, kwargs = fake.calls[0]
        self.assertEqual(method, "PATCH")
        self.assertEqual(kwargs["json"], {
            "modelDeployments": {
                "gpt-4.1-mini": "my-mini",
                "text-embedding-3-small": "my-small",
            }
        })
        self.assertTrue(kwargs["allow_redirects"] is False)
        self.assertEqual(kwargs["headers"]["Ocp-Apim-Subscription-Key"], "fake-key")

    def test_analyze_passes_base64_and_polls_until_succeeded(self):
        fake = FakeSession([
            mock_response(202, {"id": "op-123", "status": "Running"}),
            mock_response(200, {"id": "op-123", "status": "Succeeded", "result": {"contents": [{"markdown": "OK"}]}}),
        ])
        client = CUClient(self.ENDPOINT, api_key="fake-key", session=fake)
        result = client.analyze(
            "prebuilt-read", b"%PDF-1.7", "poster.pdf", "application/pdf",
        )
        self.assertEqual(result["status"], "Succeeded")
        post = fake.calls[0]
        self.assertIn(":analyze", post[1])
        self.assertEqual(
            base64.b64decode(post[2]["json"]["inputs"][0]["data"]), b"%PDF-1.7"
        )
        self.assertEqual(fake.calls[1][0], "GET")

    def test_result_is_retried_if_not_visible_immediately(self):
        fake = FakeSession([
            mock_response(202, {"id": "op-123", "status": "Running"}),
            mock_response(404, {"error": {"message": "not yet available"}}),
            mock_response(200, {"id": "op-123", "status": "Succeeded", "result": {"contents": []}}),
        ])
        client = CUClient(self.ENDPOINT, api_key="fake-key", session=fake)
        with patch("cu_client.time.sleep"):
            result = client.analyze("prebuilt-read", b"test", "poster.pdf", "application/pdf")
        self.assertEqual(result["status"], "Succeeded")
        self.assertEqual(len(fake.calls), 3)

    def test_get_existing_analyzer_does_not_overwrite(self):
        definition = {"fieldSchema": {"fields": {"Event": {"type": "string"}}}}
        fake = FakeSession([mock_response(200, {"status": "ready", "fieldSchema": definition["fieldSchema"]}),
                            mock_response(200, {"status": "ready", "fieldSchema": definition["fieldSchema"]})])
        client = CUClient(self.ENDPOINT, api_key="fake-key", session=fake)
        client.ensure_analyzer("lit-event-id", definition)
        self.assertTrue(all(method == "GET" for method, _, _ in fake.calls))


if __name__ == "__main__":
    unittest.main()
