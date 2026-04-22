"""Apply hand-edits to generated client code.

This script re-applies critical hand-edits to the cloud_storage_service_api_client
that the openapi-python-client generator overwrites. Each patch is idempotent,
so it can be safely run multiple times or in CI after every generation.

Hand-edits preserved:
1. body_upload_file_upload_post.py::to_multipart() - Handle bytes payloads
2. download_file_download_key_get.py::_parse_response() - Return raw bytes
3. ai_chat_ai_chat_post.py::_get_kwargs() - Guard header None serialization

Usage:
    uv run python scripts/apply_generator_patches.py

Exit codes:
    0 - All patches applied successfully or already in place
    1 - At least one patch failed to apply
"""

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


def check_and_patch(
    file_path: Path,
    old_marker: str,
    new_fragment: str,
    patch_name: str,
    check_already_patched: str | None = None,
) -> bool:
    """Apply a patch idempotently. Return True if successful, False otherwise.

    Args:
        file_path: Path to file to patch.
        old_marker: Exact string to find and replace (include context).
        new_fragment: Replacement text.
        patch_name: Human-readable name for logging.
        check_already_patched: Marker string to detect if patch already applied.
                              If None, uses new_fragment (file should contain it).

    Returns:
        True if patch applied or already in place, False if patch failed.
    """
    if not file_path.exists():
        logger.warning("❌ %s: File not found: %s", patch_name, file_path)
        return False

    content = file_path.read_text()

    # Determine what "already patched" looks like
    already_patched = (
        new_fragment in content
        if check_already_patched is None
        else check_already_patched in content
    )

    if already_patched:
        logger.info("✅ %s: Already patched", patch_name)
        return True

    if old_marker not in content:
        logger.warning("❌ %s: Could not find marker in file", patch_name)
        logger.warning(
            "   Expected substring not found. Generator output may have changed."
        )
        return False

    new_content = content.replace(old_marker, new_fragment)
    file_path.write_text(new_content)
    logger.info("✅ %s: Patch applied successfully", patch_name)
    return True


def patch_body_upload_file_upload_post() -> bool:
    """Patch to_multipart() to handle bytes payloads and extract filename from key."""
    file_path = (
        Path(__file__).parent.parent
        / "components/cloud_storage_service_api_client"
        / "cloud_storage_service_api_client/models/body_upload_file_upload_post.py"
    )

    old_method = """    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("file", (None, str(self.file).encode(), "text/plain")))



        files.append(("key", (None, str(self.key).encode(), "text/plain")))



        if not isinstance(self.content_type, Unset):
            if isinstance(self.content_type, str):

                files.append(("content_type", (None, str(self.content_type).encode(), "text/plain")))
            else:
                files.append(("content_type", (None, str(self.content_type).encode(), "text/plain")))



        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))



        return files"""

    new_method = """    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        # FastAPI's UploadFile dependency requires an explicit filename for proper parsing
        effective_filename = "upload.bin"
        if isinstance(self.key, str) and self.key:
            effective_filename = (
                self.key.rsplit("/", maxsplit=1)[-1] or effective_filename
            )

        effective_content_type = "application/octet-stream"
        if isinstance(self.content_type, str) and self.content_type:
            effective_content_type = self.content_type

        file_payload = (
            self.file if isinstance(self.file, bytes) else str(self.file).encode()
        )

        files.append(
            ("file", (effective_filename, file_payload, effective_content_type))
        )

        files.append(("key", (None, str(self.key).encode(), "text/plain")))

        if not isinstance(self.content_type, Unset):
            files.append(
                ("content_type", (None, str(self.content_type).encode(), "text/plain"))
            )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files"""

    return check_and_patch(
        file_path,
        old_method,
        new_method,
        "body_upload_file_upload_post.py::to_multipart()",
        check_already_patched="effective_filename",
    )


def patch_download_file_download_key_get() -> bool:
    """Patch _parse_response() to return raw bytes instead of parsed JSON."""
    file_path = (
        Path(__file__).parent.parent
        / "components/cloud_storage_service_api_client"
        / "cloud_storage_service_api_client/api/storage"
        / "download_file_download_key_get.py"
    )

    old_parse = (
        "def _parse_response("
        "*, client: AuthenticatedClient | Client, "
        "response: httpx.Response"
        ") -> Any | HTTPValidationError | None:\n"
        "    if response.status_code == 200:\n"
        "        response_200 = response.json()\n"
        "        return response_200"
    )

    new_parse = (
        "def _parse_response("
        "*, client: AuthenticatedClient | Client, "
        "response: httpx.Response"
        ") -> Any | HTTPValidationError | None:\n"
        "    if response.status_code == 200:\n"
        "        # Download endpoint returns bytes, surface raw payload.\n"
        "        return response.content"
    )

    return check_and_patch(
        file_path,
        old_parse,
        new_parse,
        "download_file_download_key_get.py::_parse_response()",
        check_already_patched="return response.content",
    )


def patch_ai_chat_ai_chat_post() -> bool:
    """Patch _get_kwargs() to guard against None in x_container header."""
    file_path = (
        Path(__file__).parent.parent
        / "components/cloud_storage_service_api_client"
        / "cloud_storage_service_api_client/api/ai"
        / "ai_chat_ai_chat_post.py"
    )

    old_guard = (
        "    headers: dict[str, Any] = {}\n"
        "    if not isinstance(x_container, Unset):\n"
        '        headers["X-Container"] = x_container'
    )

    new_guard = (
        "    headers: dict[str, Any] = {}\n"
        "    if not isinstance(x_container, Unset) and x_container is not None:\n"
        '        headers["X-Container"] = x_container'
    )

    return check_and_patch(
        file_path,
        old_guard,
        new_guard,
        "ai_chat_ai_chat_post.py::_get_kwargs()",
        check_already_patched="and x_container is not None",
    )


def main() -> int:
    """Apply all patches. Return 0 on success, 1 on failure."""
    logger.info("🔧 Applying generator patches to cloud_storage_service_api_client...\n")

    results = [
        patch_body_upload_file_upload_post(),
        patch_download_file_download_key_get(),
        patch_ai_chat_ai_chat_post(),
    ]

    logger.info("")
    if all(results):
        logger.info("✅ All generator patches applied successfully")
        return 0
    logger.warning("❌ One or more patches failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
