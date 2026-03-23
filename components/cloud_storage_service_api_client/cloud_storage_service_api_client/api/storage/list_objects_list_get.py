from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.list_response import ListResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    prefix: str | Unset = "",
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["prefix"] = prefix

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/list",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ListResponse | None:
    if response.status_code == 200:
        response_200 = ListResponse.from_dict(response.json())

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
) -> Response[HTTPValidationError | ListResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    prefix: str | Unset = "",
) -> Response[HTTPValidationError | ListResponse]:
    """List Objects

     List objects in cloud storage with optional prefix filter.

    Requires authentication via Bearer token.

    Args:
        prefix: Filter objects by key prefix.
        token: Validated access token.
        client: GCP storage client.

    Returns:
        List of objects matching the prefix.

    Raises:
        HTTPException: If listing fails.

    Args:
        prefix (str | Unset): Prefix filter for object keys Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListResponse]
    """

    kwargs = _get_kwargs(
        prefix=prefix,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    prefix: str | Unset = "",
) -> HTTPValidationError | ListResponse | None:
    """List Objects

     List objects in cloud storage with optional prefix filter.

    Requires authentication via Bearer token.

    Args:
        prefix: Filter objects by key prefix.
        token: Validated access token.
        client: GCP storage client.

    Returns:
        List of objects matching the prefix.

    Raises:
        HTTPException: If listing fails.

    Args:
        prefix (str | Unset): Prefix filter for object keys Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListResponse
    """

    return sync_detailed(
        client=client,
        prefix=prefix,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    prefix: str | Unset = "",
) -> Response[HTTPValidationError | ListResponse]:
    """List Objects

     List objects in cloud storage with optional prefix filter.

    Requires authentication via Bearer token.

    Args:
        prefix: Filter objects by key prefix.
        token: Validated access token.
        client: GCP storage client.

    Returns:
        List of objects matching the prefix.

    Raises:
        HTTPException: If listing fails.

    Args:
        prefix (str | Unset): Prefix filter for object keys Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListResponse]
    """

    kwargs = _get_kwargs(
        prefix=prefix,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    prefix: str | Unset = "",
) -> HTTPValidationError | ListResponse | None:
    """List Objects

     List objects in cloud storage with optional prefix filter.

    Requires authentication via Bearer token.

    Args:
        prefix: Filter objects by key prefix.
        token: Validated access token.
        client: GCP storage client.

    Returns:
        List of objects matching the prefix.

    Raises:
        HTTPException: If listing fails.

    Args:
        prefix (str | Unset): Prefix filter for object keys Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            prefix=prefix,
        )
    ).parsed
