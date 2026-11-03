"""Minimal Azure Content Understanding 2025-11-01 REST client.

No Azure credentials are committed to the repository. The caller supplies a key,
or DefaultAzureCredential uses an existing Azure login.
"""

from __future__ import annotations

import base64
import json
import time
from urllib.parse import urlparse

import requests

API_VERSION = "2025-11-01"
SCOPE = "https://cognitiveservices.azure.com/.default"
SUPPORTED_HOST_SUFFIXES = (".cognitiveservices.azure.com", ".services.ai.azure.com")
MAX_FILE_SIZE = 10 * 1024 * 1024


class CUError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class CUClient:
    def __init__(
        self,
        endpoint: str,
        api_key: str = "",
        *,
        session: requests.Session | None = None,
        credential=None,
    ) -> None:
        endpoint = endpoint.strip().rstrip("/")
        parsed = urlparse(endpoint)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith(SUPPORTED_HOST_SUFFIXES)
            or parsed.path not in ("", "/")
            or parsed.query
        ):
            raise CUError("Azure Foundry의 HTTPS 리소스 엔드포인트를 입력해 주세요.")
        self.endpoint = endpoint
        self.api_key = api_key.strip()
        self.session = session or requests.Session()
        self.credential = credential

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Ocp-Apim-Subscription-Key"] = self.api_key
        else:
            if self.credential is None:
                try:
                    from azure.identity import DefaultAzureCredential
                except ImportError as exc:
                    raise CUError("azure-identity가 없습니다. requirements.txt를 설치해 주세요.") from exc
                self.credential = DefaultAzureCredential()
            try:
                token = self.credential.get_token(SCOPE).token
            except Exception as exc:
                raise CUError(
                    "Azure 로그인에 실패했어요. az login을 하거나 AZURE_CU_KEY를 설정해 주세요."
                ) from exc
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _request(self, method: str, path: str, *, payload: dict | None = None) -> requests.Response:
        # A returned operation URL is never followed; only our fixed Azure host is used.
        url = f"{self.endpoint}/contentunderstanding/{path}"
        for attempt in range(3):
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=payload,
                    timeout=(10, 75),
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                raise CUError("CU 서버 연결에 실패했어요. 네트워크와 엔드포인트를 확인해 주세요.") from exc
            if response.status_code in (429, 502, 503, 504) and attempt < 2:
                retry_after = response.headers.get("Retry-After", "")
                delay = min(10.0, float(retry_after)) if retry_after.isdigit() else 2.0 * (attempt + 1)
                time.sleep(delay)
                continue
            if 200 <= response.status_code < 300:
                return response
            try:
                detail = response.json()
                error = detail.get("error", detail)
                message = error.get("message", json.dumps(error, ensure_ascii=False)[:300])
            except (ValueError, AttributeError):
                message = response.text[:300]
            raise CUError(f"CU API 오류 (HTTP {response.status_code}): {message}", response.status_code)
        raise CUError("CU API 요청이 반복적으로 실패했어요.")

    @staticmethod
    def _json(response: requests.Response) -> dict:
        try:
            return response.json()
        except ValueError as exc:
            raise CUError("CU API가 JSON 응답을 반환하지 않았어요.") from exc

    def get_analyzer(self, analyzer_id: str) -> dict:
        response = self._request("GET", f"analyzers/{analyzer_id}?api-version={API_VERSION}")
        return self._json(response)

    def configure_model_defaults(self, completion_deployment: str, embedding_deployment: str) -> dict:
        """Merge two model mappings; leaves other resource defaults untouched."""
        response = self._request(
            "PATCH",
            f"defaults?api-version={API_VERSION}",
            payload={
                "modelDeployments": {
                    "gpt-4.1-mini": completion_deployment,
                    "text-embedding-3-small": embedding_deployment,
                }
            },
        )
        return self._json(response)

    def ensure_analyzer(self, analyzer_id: str, definition: dict, *, wait_seconds: int = 150) -> dict:
        try:
            existing = self.get_analyzer(analyzer_id)
        except CUError as exc:
            if exc.status_code != 404:
                raise
        else:
            existing_fields = existing.get("fieldSchema", {}).get("fields", {})
            defined_fields = definition["fieldSchema"]["fields"]
            matched = set(existing_fields) == set(defined_fields) and all(
                all(existing_fields[key].get(prop) == value for prop, value in spec.items())
                for key, spec in defined_fields.items()
            )
            if not matched:
                raise CUError(
                    f"기존 분석기 {analyzer_id}의 스키마가 달라요. "
                    "다른 ID를 사용해야 합니다(기존 분석기는 덮어쓰지 않음)."
                )
            return self._wait_analyzer(analyzer_id, wait_seconds)

        # No allowReplace=true: a resource with the same ID is never overwritten.
        self._request(
            "PUT", f"analyzers/{analyzer_id}?api-version={API_VERSION}", payload=definition
        )
        return self._wait_analyzer(analyzer_id, wait_seconds)

    def _wait_analyzer(self, analyzer_id: str, wait_seconds: int) -> dict:
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            try:
                analyzer = self.get_analyzer(analyzer_id)
            except CUError as exc:
                # New analyzers may not appear in the GET endpoint immediately.
                if exc.status_code != 404:
                    raise
                time.sleep(2)
                continue
            status = str(analyzer.get("status", "")).lower()
            if status in ("ready", "succeeded", "completed", "active"):
                return analyzer
            if status in ("failed", "canceled", "cancelled"):
                raise CUError(f"분석기 생성 실패: {analyzer.get('errors', analyzer)}")
            if status not in ("creating", "updating", "pending", "running", "notstarted", ""):
                raise CUError(f"분석기가 알 수 없는 상태를 반환했어요: {status}")
            time.sleep(2)
        raise CUError(f"분석기 {analyzer_id} 준비 시간 초과. 잠시 후 다시 확인해 주세요.")

    def analyze(
        self,
        analyzer_id: str,
        contents: bytes,
        filename: str,
        mime_type: str,
        *,
        model_deployments: dict[str, str] | None = None,
        wait_seconds: int = 180,
    ) -> dict:
        if not contents:
            raise CUError("빈 파일은 분석할 수 없어요.")
        if len(contents) > MAX_FILE_SIZE:
            raise CUError("데모에서는 10MB 이하의 파일만 업로드해 주세요.")

        payload = {
            "inputs": [
                {
                    "name": filename,
                    "mimeType": mime_type,
                    "data": base64.b64encode(contents).decode("ascii"),
                }
            ]
        }
        if model_deployments:
            payload["modelDeployments"] = model_deployments

        response = self._request(
            "POST", f"analyzers/{analyzer_id}:analyze?api-version={API_VERSION}", payload=payload
        )
        operation = self._json(response)
        operation_id = operation.get("id")
        if not operation_id:
            raise CUError("CU API 응답에 분석 작업 ID가 없어요.")
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            try:
                response = self._request(
                    "GET", f"analyzerResults/{operation_id}?api-version={API_VERSION}"
                )
            except CUError as exc:
                # A newly accepted asynchronous operation can be briefly unavailable.
                if exc.status_code != 404:
                    raise
                time.sleep(2)
                continue
            result = self._json(response)
            status = str(result.get("status", "")).lower()
            if status == "succeeded":
                return result
            if status in ("failed", "canceled", "cancelled"):
                raise CUError(f"CU 분석 실패: {result.get('error', result.get('result', {}))}")
            time.sleep(2)
        raise CUError(f"분석 시간이 초과됐어요. 작업 ID: {operation_id}")
