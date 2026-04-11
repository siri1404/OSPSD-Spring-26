## Team 6 - Adaptation Plan

Our HW-2 codebase had its own interface package (cloud_storage_client_api) with a DI registry, custom exceptions, and method names that did not match the other teams. Here is what we changed to align with the shared contract.

- Dependency swap: Removed our local cloud_storage_client_api package entirely. Added the shared cloud_storage_api as a pinned git dependency (v1.0.0) in every pyproject.toml.

- Method renames across all components:
	- upload_bytes -> upload_obj (now takes BinaryIO instead of raw bytes)
	- download_bytes -> download_file (now writes to a local file path instead of returning bytes)
	- list -> list_files
	- delete -> delete_file (now returns DeleteResult instead of None)
	- head -> get_file_info (now raises ObjectNotFoundError instead of returning None)

- Container parameter: Every method now takes container as the first argument. Before, we configured the bucket once in the constructor. This was the biggest structural change and touched every method in gcp_client_impl, every endpoint in the service, every proxy call in the adapter, and every test.

- Field name mapping: key -> object_name, etag -> integrity, content_type -> data_type. Added new fields our old ObjectInfo did not have: version_id, encryption, storage_tier.

- Exceptions: Replaced our 4 custom exceptions with the shared set of 8. Our service now maps all 8 exception types to appropriate HTTP status codes.

- DI removal: The shared API has no DI module, so we removed all get_client() / register_get_client() usage.

- Python version: Bumped from 3.11 to 3.12 everywhere (shared API requires it).
