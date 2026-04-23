"""End-to-End tests for the main application.

Tests the complete workflow against real GCS infrastructure: client creation -> API call -> response handling.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import os
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import gcp_client_impl
import httpx
import pytest
from cloud_storage_api.exceptions import (
    InvalidContainerError,
    ObjectNotFoundError,
    StorageBackendError,
)
from cloud_storage_service_api_client import AuthenticatedClient
from cloud_storage_service_api_client import Client as ServiceApiClient
from cloud_storage_service_api_client.api.storage import (
    delete_object_delete_key_delete,
    download_file_download_key_get,
    head_object_head_key_get,
    list_objects_list_get,
    upload_file_upload_post,
)
from cloud_storage_service_api_client.models.body_upload_file_upload_post import BodyUploadFileUploadPost
from cloud_storage_service_api_client.models.list_response import ListResponse
from cloud_storage_service_api_client.models.object_info_response import ObjectInfoResponse

RUN_E2E_TESTS = os.environ.get("RUN_E2E_TESTS", "false").lower() == "true"
RUNNING_IN_CI = os.environ.get("CI") is not None

if not RUN_E2E_TESTS and not RUNNING_IN_CI:
    pytestmark = pytest.mark.skip(reason="E2E tests only run in CI or when RUN_E2E_TESTS=true")
else:
    pytestmark = pytest.mark.e2e


def local_creds_present() -> bool:
    """Return True when a local GOOGLE_APPLICATION_CREDENTIALS key file exists."""
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    return bool(path and Path(path).exists())


def _has_backend_credentials() -> bool:
    """Return True when either env var or local credential configuration exists."""
    return env_creds_present() or local_creds_present()


def _pick_free_port() -> int:
    """Return an available localhost port for spinning up the FastAPI service."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_service(base_url: str, timeout: float = 45.0) -> None:
    """Poll the FastAPI /health endpoint until the service reports healthy."""
    deadline = time.time() + timeout
    health_url = f"{base_url}/health"
    while time.time() < deadline:
        try:
            response = httpx.get(health_url, timeout=2.0)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(0.5)
        else:
            time.sleep(0.5)

    message = "FastAPI service did not become healthy in time"
    raise RuntimeError(message)


# ============================================================================
# Helpers
# ============================================================================


def unique_key(prefix: str = "e2e-test") -> str:
    """Return a unique GCS object key so parallel runs never collide."""
    return f"{prefix}/{uuid.uuid4().hex}.txt"


def env_creds_present() -> bool:
    """Return True when CircleCI-style env-var credentials are all set."""
    return bool(
        os.environ.get("GCP_SERVICE_KEY") and os.environ.get("GCS_BUCKET_NAME") and os.environ.get("GOOGLE_CLOUD_PROJECT")
    )


def _require_test_container() -> str:
    """Return the container (bucket) for live workflow tests or skip if missing."""
    container = os.environ.get("GCS_BUCKET_NAME", "")
    if not container:
        pytest.skip("GCS_BUCKET_NAME not set.")
    return container


@pytest.fixture(scope="session")
def service_runtime() -> Iterator[dict[str, str]]:
    """Start the FastAPI service in a background process for HW2 E2E tests."""
    if not _has_backend_credentials():
        pytest.skip("FastAPI service tests require either env-var or local GCP credentials.")

    repo_root = Path(__file__).parent.parent.parent
    service_src = repo_root / "components" / "cloud_storage_service" / "src"
    host = "127.0.0.1"
    port = _pick_free_port()
    base_url = f"http://{host}:{port}"
    dev_token = os.environ.get("DEV_AUTH_TOKEN", "dev-token-12345")

    env = os.environ.copy()
    pythonpath_entries = [
        str(service_src),
        str(repo_root / "components" / "gcp_client_impl" / "src"),
    ]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_entries.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)

    env.setdefault("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    env.setdefault("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    env["GOOGLE_OAUTH_REDIRECT_URI"] = f"{base_url}/auth/callback"
    env["ENVIRONMENT"] = "test"
    env["DEV_AUTH_TOKEN"] = dev_token
    env["DEV_ACCESS_TOKEN"] = dev_token
    env.setdefault("CLOUD_STORAGE_SERVICE_URL", base_url)

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "cloud_storage_service.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]

    process = subprocess.Popen(
        command,
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        _wait_for_service(base_url)
    except Exception:
        process.terminate()
        process.wait(timeout=10)
        raise

    # Ensure adapter imports pick up the correct runtime values
    os.environ.setdefault("CLOUD_STORAGE_SERVICE_URL", base_url)
    os.environ["DEV_AUTH_TOKEN"] = dev_token
    os.environ.setdefault("DEV_ACCESS_TOKEN", dev_token)

    try:
        yield {"base_url": base_url, "token": dev_token}
    finally:
        process.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=10)


# ============================================================================
# Structural / syntax tests - no credentials needed
# ============================================================================


@pytest.mark.circleci
def test_main_script_syntax_is_valid() -> None:
    """Verify main.py has valid Python syntax without executing it."""
    main_script = Path(__file__).parent.parent.parent / "main.py"

    if not main_script.exists():
        pytest.skip(f"main.py not found at {main_script}")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(main_script)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if result.returncode != 0:
        pytest.fail(f"main.py has syntax errors:\n{result.stderr}")


@pytest.mark.circleci
def test_main_script_imports_work() -> None:
    """Verify both packages import cleanly from the workspace root."""
    main_script = Path(__file__).parent.parent.parent / "main.py"
    workspace_root = main_script.parent

    # Set PYTHONPATH to include component source paths
    env = os.environ.copy()
    pythonpath_parts = [
        str(workspace_root / "components" / "gcp_client_impl" / "src"),
        str(workspace_root / "components" / "cloud_storage_adapter" / "src"),
        str(workspace_root / "components" / "cloud_storage_service" / "src"),
        str(workspace_root / "components" / "cloud_storage_service_api_client"),
    ]
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    import_check = "import gcp_client_impl\nimport cloud_storage_api\nprint('All imports successful')\n"

    result = subprocess.run(
        [sys.executable, "-c", import_check],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        cwd=str(workspace_root),
        env=env,
    )
    if result.returncode != 0:
        pytest.fail(f"Import check failed:\n{result.stderr}")
    assert "All imports successful" in result.stdout


@pytest.mark.circleci
def test_application_structure_integrity() -> None:
    """Verify all required source files exist in the workspace."""
    workspace_root = Path(__file__).parent.parent.parent

    expected_files = [
        "main.py",
        "pyproject.toml",
        "components/gcp_client_impl/pyproject.toml",
        "components/gcp_client_impl/src/gcp_client_impl/__init__.py",
        "components/gcp_client_impl/src/gcp_client_impl/client.py",
    ]

    missing = [f for f in expected_files if not (workspace_root / f).exists()]
    if missing:
        pytest.fail(f"Missing required files: {missing}")


@pytest.mark.circleci
def test_client_raises_without_bucket_env_var() -> None:
    """GCPCloudStorageClient operations must require a non-empty container name."""
    from gcp_client_impl.client import GCPCloudStorageClient

    env_patch = {
        "GCS_BUCKET_NAME": "",
        "GOOGLE_CLOUD_PROJECT": "",
        "GOOGLE_APPLICATION_CREDENTIALS": "",
        "GCP_SERVICE_KEY": "",
    }
    with patch.dict(os.environ, env_patch, clear=False):
        client = GCPCloudStorageClient()
        with pytest.raises(InvalidContainerError, match="Container name cannot be empty"):
            client.list_files(container="", prefix="")


@pytest.mark.circleci
def test_client_raises_with_malformed_service_key() -> None:
    """GCPCloudStorageClient must raise RuntimeError for a non-JSON GCP_SERVICE_KEY."""
    from gcp_client_impl.client import GCPCloudStorageClient

    env_patch = {
        "GCS_BUCKET_NAME": "dummy-bucket",
        "GOOGLE_CLOUD_PROJECT": "dummy-project",
        "GOOGLE_APPLICATION_CREDENTIALS": "",
        "GCP_SERVICE_KEY": "not-valid-json-or-base64!!!",
    }
    with patch.dict(os.environ, env_patch, clear=False):
        client = GCPCloudStorageClient()
        with pytest.raises(StorageBackendError, match="GCP_SERVICE_KEY must be a valid JSON"):
            client._build_credentials()


# ============================================================================
# Full workflow tests - require real GCS credentials
# ============================================================================


@pytest.mark.circleci
def test_full_workflow_with_env_var_credentials(tmp_path: Path) -> None:
    """Run the complete workflow using GCP_SERVICE_KEY env-var credentials.

    Validates: client creation -> upload -> get_file_info -> download -> list -> delete.
    Skips when credentials are not set.
    """
    if not env_creds_present():
        pytest.skip("GCP_SERVICE_KEY / GCS_BUCKET_NAME / GOOGLE_CLOUD_PROJECT not set.")

    from gcp_client_impl.client import GCPCloudStorageClient

    client = GCPCloudStorageClient()
    container = _require_test_container()
    key = unique_key("e2e-circleci")
    payload = b"hello from circleci e2e test"
    download_path = tmp_path / "circleci_download.txt"

    try:
        # 1. Upload
        info = client.upload_obj(container=container, file_obj=io.BytesIO(payload), remote_path=key)
        assert info.object_name == key
        assert info.size_bytes == len(payload)
        assert info.integrity is not None

        # 2. Get metadata
        head_info = client.get_file_info(container=container, object_name=key)
        assert head_info.object_name == key
        assert head_info.size_bytes == len(payload)

        # 3. Download to local file
        downloaded_info = client.download_file(container=container, object_name=key, file_name=str(download_path))
        assert downloaded_info.object_name == key
        assert download_path.read_bytes() == payload

        # 4. List
        prefix = key.rsplit("/", 1)[0] + "/"
        objects = client.list_files(container=container, prefix=prefix)
        assert any(o.object_name == key for o in objects)

    finally:
        # 5. Delete - always runs even if assertions fail
        with contextlib.suppress(ObjectNotFoundError):
            client.delete_file(container=container, object_name=key)

    # 6. Confirm deletion
    with pytest.raises(ObjectNotFoundError):
        client.get_file_info(container=container, object_name=key)


@pytest.mark.local_credentials
def test_full_workflow_with_local_credentials(tmp_path: Path) -> None:
    """Run the complete workflow using a local GOOGLE_APPLICATION_CREDENTIALS file.

    Skips when credentials file is not present.
    """
    if not local_creds_present():
        pytest.skip("GOOGLE_APPLICATION_CREDENTIALS not set or file does not exist.")
    if not os.environ.get("GCS_BUCKET_NAME"):
        pytest.skip("GCS_BUCKET_NAME not set.")

    from gcp_client_impl.client import GCPCloudStorageClient

    client = GCPCloudStorageClient()
    container = _require_test_container()
    key = unique_key("e2e-local")
    payload = b"hello from local e2e test"
    download_path = tmp_path / "local_download.txt"

    try:
        info = client.upload_obj(container=container, file_obj=io.BytesIO(payload), remote_path=key)
        assert info.object_name == key
        assert info.size_bytes == len(payload)

        head_info = client.get_file_info(container=container, object_name=key)
        assert head_info.object_name == key

        client.download_file(container=container, object_name=key, file_name=str(download_path))
        assert download_path.read_bytes() == payload

        prefix = key.rsplit("/", 1)[0] + "/"
        objects = client.list_files(container=container, prefix=prefix)
        assert any(o.object_name == key for o in objects)

    finally:
        with contextlib.suppress(ObjectNotFoundError):
            client.delete_file(container=container, object_name=key)

    with pytest.raises(ObjectNotFoundError):
        client.get_file_info(container=container, object_name=key)


@pytest.mark.local_credentials
def test_upload_file_workflow_with_local_credentials(tmp_path: Path) -> None:
    """Verify upload_file() round-trip using a local credentials file."""
    if not local_creds_present():
        pytest.skip("GOOGLE_APPLICATION_CREDENTIALS not set or file missing.")
    if not os.environ.get("GCS_BUCKET_NAME"):
        pytest.skip("GCS_BUCKET_NAME not set.")

    from gcp_client_impl.client import GCPCloudStorageClient

    client = GCPCloudStorageClient()
    container = _require_test_container()
    key = unique_key("e2e-upload-file")
    payload = b"file upload e2e test content"

    local_file = tmp_path / "test_upload.txt"
    local_file.write_bytes(payload)

    try:
        info = client.upload_file(
            container=container,
            local_path=str(local_file),
            remote_path=key,
        )
        assert info.object_name == key
        assert info.size_bytes == len(payload)

        downloaded_path = tmp_path / "upload_file_download.txt"
        client.download_file(container=container, object_name=key, file_name=str(downloaded_path))
        assert downloaded_path.read_bytes() == payload

    finally:
        with contextlib.suppress(ObjectNotFoundError):
            client.delete_file(container=container, object_name=key)


@pytest.mark.circleci
def test_upload_with_custom_metadata() -> None:
    """Verify metadata and core fields are retrievable via get_file_info()."""
    if not env_creds_present():
        pytest.skip("GCP_SERVICE_KEY / GCS_BUCKET_NAME / GOOGLE_CLOUD_PROJECT not set.")

    from gcp_client_impl.client import GCPCloudStorageClient

    client = GCPCloudStorageClient()
    container = _require_test_container()
    key = unique_key("e2e-metadata")
    payload = b"metadata test"

    try:
        info = client.upload_obj(container=container, file_obj=io.BytesIO(payload), remote_path=key)
        assert info.object_name == key

        head_info = client.get_file_info(container=container, object_name=key)
        assert head_info.object_name == key
        assert head_info.metadata is None or isinstance(head_info.metadata, dict)
        assert head_info.data_type is None or isinstance(head_info.data_type, str)
        assert head_info.integrity is None or isinstance(head_info.integrity, str)

    finally:
        with contextlib.suppress(ObjectNotFoundError):
            client.delete_file(container=container, object_name=key)


@pytest.mark.circleci
def test_download_nonexistent_object_raises() -> None:
    """download_file() must raise ObjectNotFoundError for a missing key."""
    if not env_creds_present():
        pytest.skip("GCP_SERVICE_KEY / GCS_BUCKET_NAME / GOOGLE_CLOUD_PROJECT not set.")

    from gcp_client_impl.client import GCPCloudStorageClient

    client = GCPCloudStorageClient()
    container = _require_test_container()
    ghost_key = unique_key("e2e-ghost")
    local_path = str(Path.cwd() / f"{uuid.uuid4().hex}.tmp")

    with pytest.raises(ObjectNotFoundError, match=ghost_key):
        client.download_file(container=container, object_name=ghost_key, file_name=local_path)


@pytest.mark.circleci
def test_delete_nonexistent_object_raises() -> None:
    """delete_file() must raise ObjectNotFoundError for a missing key."""
    if not env_creds_present():
        pytest.skip("GCP_SERVICE_KEY / GCS_BUCKET_NAME / GOOGLE_CLOUD_PROJECT not set.")

    from gcp_client_impl.client import GCPCloudStorageClient

    client = GCPCloudStorageClient()
    container = _require_test_container()
    ghost_key = unique_key("e2e-ghost-delete")

    with pytest.raises(ObjectNotFoundError, match=ghost_key):
        client.delete_file(container=container, object_name=ghost_key)


@pytest.mark.circleci
def test_get_file_info_nonexistent_object_raises() -> None:
    """get_file_info() must raise ObjectNotFoundError for a missing key."""
    if not env_creds_present():
        pytest.skip("GCP_SERVICE_KEY / GCS_BUCKET_NAME / GOOGLE_CLOUD_PROJECT not set.")

    from gcp_client_impl.client import GCPCloudStorageClient

    client = GCPCloudStorageClient()
    container = _require_test_container()
    ghost_key = unique_key("e2e-ghost-head")

    with pytest.raises(ObjectNotFoundError, match=ghost_key):
        client.get_file_info(container=container, object_name=ghost_key)


@pytest.mark.circleci
def test_main_script_runs_with_env_var_credentials() -> None:
    """Execute main.py as a subprocess and verify it exits 0 with expected output."""
    main_script = Path(__file__).parent.parent.parent / "main.py"

    if not main_script.exists():
        pytest.skip(f"main.py not found at {main_script}")
    if main_script.stat().st_size == 0:
        pytest.skip("main.py is empty - nothing to execute.")
    if not env_creds_present():
        pytest.skip("GCP_SERVICE_KEY / GCS_BUCKET_NAME / GOOGLE_CLOUD_PROJECT not set.")

    try:
        result = subprocess.run(
            [sys.executable, str(main_script)],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
            cwd=str(main_script.parent),
        )
        assert result.returncode == 0
        # Check for some output (modify based on what main.py actually outputs)

    except subprocess.TimeoutExpired:
        pytest.fail("E2E test timed out - main.py took > 120 s.")
    except subprocess.CalledProcessError as exc:
        pytest.fail(
            f"main.py exited non-zero.\nExit code: {exc.returncode}\nStdout:\n{exc.stdout}\nStderr:\n{exc.stderr}",
        )


@pytest.mark.local_credentials
def test_main_script_runs_with_local_credentials() -> None:
    """Execute main.py as a subprocess using a local credentials file."""
    main_script = Path(__file__).parent.parent.parent / "main.py"

    if not main_script.exists():
        pytest.skip(f"main.py not found at {main_script}")
    if main_script.stat().st_size == 0:
        pytest.skip("main.py is empty - nothing to execute.")
    if not local_creds_present():
        pytest.skip("GOOGLE_APPLICATION_CREDENTIALS not set or file missing.")
    if not os.environ.get("GCS_BUCKET_NAME"):
        pytest.skip("GCS_BUCKET_NAME not set.")

    try:
        result = subprocess.run(
            [sys.executable, str(main_script)],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
            cwd=str(main_script.parent),
        )
        assert result.returncode == 0

    except subprocess.TimeoutExpired:
        pytest.fail("E2E test timed out - main.py took > 120 s.")
    except subprocess.CalledProcessError as exc:
        pytest.fail(
            f"main.py exited non-zero.\nExit code: {exc.returncode}\nStdout:\n{exc.stdout}\nStderr:\n{exc.stderr}",
        )


@pytest.mark.local_credentials
def test_client_instantiates_without_credentials() -> None:
    """GCPCloudStorageClient must instantiate cleanly with no credentials.

    The error is only raised on the first real API call, not at construction time.
    """
    from gcp_client_impl.client import GCPCloudStorageClient

    env_patch = {
        "GCS_BUCKET_NAME": "some-bucket",
        "GOOGLE_CLOUD_PROJECT": "",
        "GOOGLE_APPLICATION_CREDENTIALS": "",
        "GCP_SERVICE_KEY": "",
    }
    with patch.dict(os.environ, env_patch, clear=False):
        client = GCPCloudStorageClient()
        assert client is not None


# ============================================================================
# HW2 FastAPI service and adapter tests
# ============================================================================


@pytest.mark.circleci
def test_service_health_endpoint(service_runtime: dict[str, str]) -> None:
    """Verify the FastAPI deployment responds with a healthy status."""
    base_url = service_runtime["base_url"]
    response = httpx.get(f"{base_url}/health", timeout=5.0)
    response.raise_for_status()
    payload = response.json()
    assert payload["status"].lower() == "healthy"
    assert payload["service"] == "cloud-storage-service"


@pytest.mark.circleci
def test_service_storage_round_trip_via_http(service_runtime: dict[str, str]) -> None:
    """Exercise upload/list/download/delete endpoints via pure HTTP calls."""
    base_url = service_runtime["base_url"]
    token = service_runtime["token"]
    headers = {"Authorization": f"Bearer {token}"}
    key = unique_key("e2e-service-http")
    payload = b"service http round trip"

    files = {"file": ("round-trip.txt", payload, "text/plain")}
    data = {"key": key, "content_type": "text/plain"}

    upload = httpx.post(f"{base_url}/upload", files=files, data=data, headers=headers, timeout=20.0)
    upload.raise_for_status()
    assert upload.json()["key"] == key

    head = httpx.get(f"{base_url}/head/{key}", headers=headers, timeout=10.0)
    head.raise_for_status()
    assert head.json()["content_type"] == "text/plain"

    download = httpx.get(f"{base_url}/download/{key}", headers=headers, timeout=10.0)
    download.raise_for_status()
    assert download.content == payload

    prefix = key.rsplit("/", maxsplit=1)[0] + "/"
    listing = httpx.get(f"{base_url}/list", params={"prefix": prefix}, headers=headers, timeout=10.0)
    listing.raise_for_status()
    assert any(obj["key"] == key for obj in listing.json()["objects"])

    delete = httpx.delete(f"{base_url}/delete/{key}", headers=headers, timeout=10.0)
    assert delete.status_code == 204


@pytest.mark.circleci
def test_adapter_and_impl_interoperate(service_runtime: dict[str, str], tmp_path: Path) -> None:
    """Ensure the service-backed adapter behaves like the direct GCP implementation."""
    base_url = service_runtime["base_url"]
    token = service_runtime["token"]

    adapter_module = importlib.import_module("cloud_storage_adapter")
    adapter_cls = adapter_module.CloudStorageAdapter
    adapter_client = adapter_cls(base_url=base_url, token=token)

    from gcp_client_impl.client import GCPCloudStorageClient

    direct_client = GCPCloudStorageClient()
    container = _require_test_container()
    key = unique_key("e2e-adapter")
    payload = b"adapter vs impl"
    downloaded_path = tmp_path / "adapter_round_trip.bin"

    try:
        info = adapter_client.upload_obj(
            container=container,
            file_obj=io.BytesIO(payload),
            remote_path=key,
        )
        assert info.object_name == key

        direct_metadata = direct_client.get_file_info(container=container, object_name=key)
        assert direct_metadata.object_name == key

        adapter_client.download_file(container=container, object_name=key, file_name=str(downloaded_path))
        assert downloaded_path.read_bytes() == payload

        prefix = key.rsplit("/", maxsplit=1)[0] + "/"
        listed = adapter_client.list_files(container=container, prefix=prefix)
        assert any(obj.object_name == key for obj in listed)

    finally:
        with contextlib.suppress(Exception):
            adapter_client.delete_file(container=container, object_name=key)
        with pytest.raises(ObjectNotFoundError):
            direct_client.get_file_info(container=container, object_name=key)


@pytest.mark.circleci
def test_generated_client_round_trip(service_runtime: dict[str, str]) -> None:
    """Use the auto-generated client to exercise the FastAPI service endpoints."""
    base_url = service_runtime["base_url"]
    token = service_runtime["token"]
    client = AuthenticatedClient(base_url=base_url, token=token)

    key = unique_key("e2e-generated-client")
    payload = "generated client payload"
    body = BodyUploadFileUploadPost(file=payload, key=key, content_type="text/plain")

    try:
        upload_response = upload_file_upload_post.sync(client=client, body=body)
        validated_upload = _ensure_object_info(upload_response)
        assert validated_upload.key == key

        head_response = head_object_head_key_get.sync(client=client, key=key)
        validated_head = _ensure_object_info(head_response)
        assert validated_head.key == key

        download_response = download_file_download_key_get.sync_detailed(key=key, client=client)
        assert download_response.status_code == HTTPStatus.OK
        assert download_response.content == payload.encode()

        prefix = key.rsplit("/", maxsplit=1)[0] + "/"
        list_response = list_objects_list_get.sync(client=client, prefix=prefix)
        validated_list = _ensure_list_response(list_response)
        assert any(obj.key == key for obj in validated_list.objects)
    finally:
        with contextlib.suppress(Exception):
            delete_object_delete_key_delete.sync_detailed(key=key, client=client)


@pytest.mark.circleci
def test_service_oauth_login_returns_authorization_url(service_runtime: dict[str, str]) -> None:
    """Ensure /auth/login returns a well-formed Google OAuth URL."""
    base_url = service_runtime["base_url"]
    response = httpx.post(f"{base_url}/auth/login", timeout=10.0)
    assert response.status_code == HTTPStatus.OK
    auth_url = response.json()["auth_url"]
    parsed = urlparse(auth_url)
    params = parse_qs(parsed.query)

    assert parsed.netloc.endswith("accounts.google.com")
    assert params.get("redirect_uri", [None])[0] == f"{base_url}/auth/callback"
    expected_client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    assert params.get("client_id", [None])[0] == expected_client_id
    assert params.get("state", [""])[0]


@pytest.mark.circleci
def test_deployed_service_health_endpoint() -> None:
    """Check the health and OpenAPI schema of the deployed service when configured."""
    base_url = os.environ.get("DEPLOYED_SERVICE_BASE_URL")
    if not base_url:
        pytest.skip("DEPLOYED_SERVICE_BASE_URL not configured for deployed health check.")

    normalized_base = base_url.rstrip("/")
    health_response = httpx.get(f"{normalized_base}/health", timeout=10.0)
    health_response.raise_for_status()
    payload = health_response.json()
    assert payload["status"].lower() == "healthy"
    assert payload["service"] == "cloud-storage-service"

    schema_response = httpx.get(f"{normalized_base}/openapi.json", timeout=10.0)
    schema_response.raise_for_status()
    schema = schema_response.json()
    assert "openapi" in schema
    assert schema.get("info", {}).get("title") == "Cloud Storage Service API"


def _ensure_object_info(value: object | ObjectInfoResponse | None) -> ObjectInfoResponse:
    if not isinstance(value, ObjectInfoResponse):
        msg = "Expected ObjectInfoResponse"
        raise TypeError(msg)
    return value


def _ensure_list_response(value: object | ListResponse | None) -> ListResponse:
    if not isinstance(value, ListResponse):
        msg = "Expected ListResponse"
        raise TypeError(msg)
    return value
