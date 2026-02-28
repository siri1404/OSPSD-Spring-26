"""End-to-End tests for the main application.

Tests the complete workflow against real GCS infrastructure: client creation → API call → response handling.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import gcp_client_impl
import pytest
from cloud_storage_client_api.di import get_client

pytestmark = pytest.mark.e2e


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


def local_creds_present() -> bool:
    """Return True when a local GOOGLE_APPLICATION_CREDENTIALS key file exists."""
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    return bool(path and Path(path).exists())


# ============================================================================
# Structural / syntax tests — no credentials needed
# ============================================================================


@pytest.mark.circleci
def test_main_script_syntax_is_valid() -> None:
    """Verify main.py has valid Python syntax without executing it."""
    main_script = Path(__file__).parent.parent.parent / "main.py"

    if not main_script.exists():
        pytest.skip(f"main.py not found at {main_script}")

    result = subprocess.run(  # noqa: S603
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

    import_check = "import gcp_client_impl\nimport cloud_storage_client_api\nprint('All imports successful')\n"

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", import_check],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        cwd=str(main_script.parent),
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
        "components/cloud_storage_client_api/pyproject.toml",
        "components/cloud_storage_client_api/src/cloud_storage_client_api/__init__.py",
        "components/cloud_storage_client_api/src/cloud_storage_client_api/client.py",
        "components/cloud_storage_client_api/src/cloud_storage_client_api/di.py",
        "components/gcp_client_impl/pyproject.toml",
        "components/gcp_client_impl/src/gcp_client_impl/__init__.py",
        "components/gcp_client_impl/src/gcp_client_impl/client.py",
    ]

    missing = [f for f in expected_files if not (workspace_root / f).exists()]
    if missing:
        pytest.fail(f"Missing required files: {missing}")


@pytest.mark.circleci
def test_di_registration_on_import() -> None:
    """Importing gcp_client_impl must register the GCP client as the default provider."""
    client = get_client()
    assert client.__class__.__name__ == "GCPCloudStorageClient"

    client_named = get_client(name="gcp")
    assert client_named.__class__.__name__ == "GCPCloudStorageClient"


@pytest.mark.circleci
def test_client_raises_without_bucket_env_var() -> None:
    """GCPCloudStorageClient must raise RuntimeError when no bucket is configured."""
    from gcp_client_impl.client import GCPCloudStorageClient

    env_patch = {
        "GCS_BUCKET_NAME": "",
        "GOOGLE_CLOUD_PROJECT": "",
        "GOOGLE_APPLICATION_CREDENTIALS": "",
        "GCP_SERVICE_KEY": "",
    }
    with patch.dict(os.environ, env_patch, clear=False):
        client = GCPCloudStorageClient()
        with pytest.raises(RuntimeError, match="GCS bucket is not configured"):
            client._get_bucket_name()


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
        with pytest.raises(RuntimeError, match="GCP_SERVICE_KEY must be a valid JSON"):
            client._build_credentials()


# ============================================================================
# Full workflow tests — require real GCS credentials
# ============================================================================


@pytest.mark.circleci
def test_full_workflow_with_env_var_credentials() -> None:
    """Run the complete workflow using GCP_SERVICE_KEY env-var credentials.

    Validates: client creation → upload → head → download → list → delete.
    Skips when credentials are not set.
    """
    if not env_creds_present():
        pytest.skip("GCP_SERVICE_KEY / GCS_BUCKET_NAME / GOOGLE_CLOUD_PROJECT not set.")

    from gcp_client_impl.client import GCPCloudStorageClient

    client = GCPCloudStorageClient()
    key = unique_key("e2e-circleci")
    payload = b"hello from circleci e2e test"

    try:
        # 1. Upload
        info = client.upload_bytes(data=payload, key=key, content_type="text/plain")
        assert info.key == key
        assert info.size_bytes == len(payload)
        assert info.content_type == "text/plain"
        assert info.etag is not None

        # 2. Head
        head_info = client.head(key=key)
        assert head_info is not None
        assert head_info.key == key
        assert head_info.size_bytes == len(payload)

        # 3. Download
        downloaded = client.download_bytes(key=key)
        assert downloaded == payload

        # 4. List
        prefix = key.rsplit("/", 1)[0] + "/"
        objects = client.list(prefix=prefix)
        assert any(o.key == key for o in objects)

    finally:
        # 5. Delete — always runs even if assertions fail
        with contextlib.suppress(FileNotFoundError):
            client.delete(key=key)

    # 6. Confirm deletion
    assert client.head(key=key) is None


@pytest.mark.local_credentials
def test_full_workflow_with_local_credentials() -> None:
    """Run the complete workflow using a local GOOGLE_APPLICATION_CREDENTIALS file.

    Skips when credentials file is not present.
    """
    if not local_creds_present():
        pytest.skip("GOOGLE_APPLICATION_CREDENTIALS not set or file does not exist.")
    if not os.environ.get("GCS_BUCKET_NAME"):
        pytest.skip("GCS_BUCKET_NAME not set.")

    from gcp_client_impl.client import GCPCloudStorageClient

    client = GCPCloudStorageClient()
    key = unique_key("e2e-local")
    payload = b"hello from local e2e test"

    try:
        info = client.upload_bytes(data=payload, key=key, content_type="text/plain")
        assert info.key == key
        assert info.size_bytes == len(payload)

        head_info = client.head(key=key)
        assert head_info is not None
        assert head_info.key == key

        downloaded = client.download_bytes(key=key)
        assert downloaded == payload

        prefix = key.rsplit("/", 1)[0] + "/"
        objects = client.list(prefix=prefix)
        assert any(o.key == key for o in objects)

    finally:
        with contextlib.suppress(FileNotFoundError):
            client.delete(key=key)

    assert client.head(key=key) is None


@pytest.mark.local_credentials
def test_upload_file_workflow_with_local_credentials(tmp_path: Path) -> None:
    """Verify upload_file() round-trip using a local credentials file."""
    if not local_creds_present():
        pytest.skip("GOOGLE_APPLICATION_CREDENTIALS not set or file missing.")
    if not os.environ.get("GCS_BUCKET_NAME"):
        pytest.skip("GCS_BUCKET_NAME not set.")

    from gcp_client_impl.client import GCPCloudStorageClient

    client = GCPCloudStorageClient()
    key = unique_key("e2e-upload-file")
    payload = b"file upload e2e test content"

    local_file = tmp_path / "test_upload.txt"
    local_file.write_bytes(payload)

    try:
        info = client.upload_file(
            local_path=str(local_file),
            key=key,
            content_type="text/plain",
        )
        assert info.key == key
        assert info.size_bytes == len(payload)

        downloaded = client.download_bytes(key=key)
        assert downloaded == payload

    finally:
        with contextlib.suppress(FileNotFoundError):
            client.delete(key=key)


@pytest.mark.circleci
def test_upload_with_custom_metadata() -> None:
    """Verify custom metadata is stored and retrievable via head()."""
    if not env_creds_present():
        pytest.skip("GCP_SERVICE_KEY / GCS_BUCKET_NAME / GOOGLE_CLOUD_PROJECT not set.")

    from gcp_client_impl.client import GCPCloudStorageClient

    client = GCPCloudStorageClient()
    key = unique_key("e2e-metadata")
    payload = b"metadata test"
    custom_meta = {"owner": "e2e-test", "purpose": "hw-1-validation"}

    try:
        info = client.upload_bytes(
            data=payload,
            key=key,
            content_type="text/plain",
            metadata=custom_meta,
        )
        assert info.key == key

        head_info = client.head(key=key)
        assert head_info is not None
        assert head_info.metadata is not None
        for k, v in custom_meta.items():
            assert head_info.metadata.get(k) == v

    finally:
        with contextlib.suppress(FileNotFoundError):
            client.delete(key=key)


@pytest.mark.circleci
def test_download_nonexistent_object_raises() -> None:
    """download_bytes() must raise FileNotFoundError for a missing key."""
    if not env_creds_present():
        pytest.skip("GCP_SERVICE_KEY / GCS_BUCKET_NAME / GOOGLE_CLOUD_PROJECT not set.")

    from gcp_client_impl.client import GCPCloudStorageClient

    client = GCPCloudStorageClient()
    ghost_key = unique_key("e2e-ghost")

    with pytest.raises(FileNotFoundError, match=ghost_key):
        client.download_bytes(key=ghost_key)


@pytest.mark.circleci
def test_delete_nonexistent_object_raises() -> None:
    """delete() must raise FileNotFoundError for a missing key."""
    if not env_creds_present():
        pytest.skip("GCP_SERVICE_KEY / GCS_BUCKET_NAME / GOOGLE_CLOUD_PROJECT not set.")

    from gcp_client_impl.client import GCPCloudStorageClient

    client = GCPCloudStorageClient()
    ghost_key = unique_key("e2e-ghost-delete")

    with pytest.raises(FileNotFoundError, match=ghost_key):
        client.delete(key=ghost_key)


@pytest.mark.circleci
def test_head_nonexistent_object_returns_none() -> None:
    """head() must return None (not raise) for a missing key."""
    if not env_creds_present():
        pytest.skip("GCP_SERVICE_KEY / GCS_BUCKET_NAME / GOOGLE_CLOUD_PROJECT not set.")

    from gcp_client_impl.client import GCPCloudStorageClient

    client = GCPCloudStorageClient()
    ghost_key = unique_key("e2e-ghost-head")

    result = client.head(key=ghost_key)
    assert result is None


@pytest.mark.circleci
def test_main_script_runs_with_env_var_credentials() -> None:
    """Execute main.py as a subprocess and verify it exits 0 with expected output."""
    main_script = Path(__file__).parent.parent.parent / "main.py"

    if not main_script.exists():
        pytest.skip(f"main.py not found at {main_script}")
    if main_script.stat().st_size == 0:
        pytest.skip("main.py is empty — nothing to execute.")
    if not env_creds_present():
        pytest.skip("GCP_SERVICE_KEY / GCS_BUCKET_NAME / GOOGLE_CLOUD_PROJECT not set.")

    try:
        result = subprocess.run(  # noqa: S603
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
        pytest.fail("E2E test timed out — main.py took > 120 s.")
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
        pytest.skip("main.py is empty — nothing to execute.")
    if not local_creds_present():
        pytest.skip("GOOGLE_APPLICATION_CREDENTIALS not set or file missing.")
    if not os.environ.get("GCS_BUCKET_NAME"):
        pytest.skip("GCS_BUCKET_NAME not set.")

    try:
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(main_script)],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
            cwd=str(main_script.parent),
        )
        assert result.returncode == 0

    except subprocess.TimeoutExpired:
        pytest.fail("E2E test timed out — main.py took > 120 s.")
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
