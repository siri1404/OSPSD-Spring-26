from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.body_upload_file_upload_post import BodyUploadFileUploadPost
from ...models.http_validation_error import HTTPValidationError
from ...models.object_info_response import ObjectInfoResponse
from ...types import Response


def _get_kwargs(
    *,
    body: BodyUploadFileUploadPost,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/upload",
    }

    _kwargs["files"] = body.to_multipart()

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ObjectInfoResponse | None:
    if response.status_code == 200:
        response_200 = ObjectInfoResponse.from_dict(response.json())

        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[HTTPValidationError | ObjectInfoResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: BodyUploadFileUploadPost,
) -> Response[HTTPValidationError | ObjectInfoResponse]:
    """Upload File

     Upload a file to cloud storage.

    Requires authentication via Bearer token.

    Args:
        file: File to upload (multipart/form-data).
        key: Destination key/path in cloud storage.
        content_type: Optional MIME type.
        token: Validated access token.
        client: GCP storage client.

    Returns:
        Object metadata after successful upload.

    Raises:
        HTTPException: If upload fails.

    Args:
        body (BodyUploadFileUploadPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ObjectInfoResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    body: BodyUploadFileUploadPost,
) -> HTTPValidationError | ObjectInfoResponse | None:
    """Upload File

     Upload a file to cloud storage.

    Requires authentication via Bearer token.

    Args:
        file: File to upload (multipart/form-data).
        key: Destination key/path in cloud storage.
        content_type: Optional MIME type.
        token: Validated access token.
        client: GCP storage client.

    Returns:
        Object metadata after successful upload.

    Raises:
        HTTPException: If upload fails.

    Args:
        body (BodyUploadFileUploadPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ObjectInfoResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: BodyUploadFileUploadPost,
) -> Response[HTTPValidationError | ObjectInfoResponse]:
    """Upload File

     Upload a file to cloud storage.

    Requires authentication via Bearer token.

    Args:
        file: File to upload (multipart/form-data).
        key: Destination key/path in cloud storage.
        content_type: Optional MIME type.
        token: Validated access token.
        client: GCP storage client.

    Returns:
        Object metadata after successful upload.

    Raises:
        HTTPException: If upload fails.

    Args:
        body (BodyUploadFileUploadPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ObjectInfoResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: BodyUploadFileUploadPost,
) -> HTTPValidationError | ObjectInfoResponse | None:
    """Upload File

     Upload a file to cloud storage.

    Requires authentication via Bearer token.

    Args:
        file: File to upload (multipart/form-data).
        key: Destination key/path in cloud storage.
        content_type: Optional MIME type.
        token: Validated access token.
        client: GCP storage client.

    Returns:
        Object metadata after successful upload.

    Raises:
        HTTPException: If upload fails.

    Args:
        body (BodyUploadFileUploadPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ObjectInfoResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
