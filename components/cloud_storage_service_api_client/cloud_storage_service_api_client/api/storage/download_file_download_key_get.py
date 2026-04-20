from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Unset
from typing import cast



def _get_kwargs(
    key: str,
    *,
    container: None | str | Unset = UNSET,

) -> dict[str, Any]:
    

    

    params: dict[str, Any] = {}

    json_container: None | str | Unset
    if isinstance(container, Unset):
        json_container = UNSET
    else:
        json_container = container
    params["container"] = json_container


    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}


    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/download/{key}".format(key=quote(str(key), safe=""),),
        "params": params,
    }


    return _kwargs



def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | HTTPValidationError | None:
    if response.status_code == 200:
        # Download endpoint returns bytes, so surface the raw payload.
        return response.content

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[Any | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    key: str,
    *,
    client: AuthenticatedClient,
    container: None | str | Unset = UNSET,

) -> Response[Any | HTTPValidationError]:
    """ Download File

     Download a file from cloud storage.

    Requires authentication via Bearer token.

    Args:
        key: Object key/path to download.
        token: Validated access token.
        client: GCP storage client.
        container: Optional storage container or bucket override.

    Returns:
        File contents as streaming response.

    Raises:
        HTTPException: If file not found or download fails.

    Args:
        key (str):
        container (None | str | Unset): Storage container or bucket name

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        key=key,
container=container,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    key: str,
    *,
    client: AuthenticatedClient,
    container: None | str | Unset = UNSET,

) -> Any | HTTPValidationError | None:
    """ Download File

     Download a file from cloud storage.

    Requires authentication via Bearer token.

    Args:
        key: Object key/path to download.
        token: Validated access token.
        client: GCP storage client.
        container: Optional storage container or bucket override.

    Returns:
        File contents as streaming response.

    Raises:
        HTTPException: If file not found or download fails.

    Args:
        key (str):
        container (None | str | Unset): Storage container or bucket name

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
     """


    return sync_detailed(
        key=key,
client=client,
container=container,

    ).parsed

async def asyncio_detailed(
    key: str,
    *,
    client: AuthenticatedClient,
    container: None | str | Unset = UNSET,

) -> Response[Any | HTTPValidationError]:
    """ Download File

     Download a file from cloud storage.

    Requires authentication via Bearer token.

    Args:
        key: Object key/path to download.
        token: Validated access token.
        client: GCP storage client.
        container: Optional storage container or bucket override.

    Returns:
        File contents as streaming response.

    Raises:
        HTTPException: If file not found or download fails.

    Args:
        key (str):
        container (None | str | Unset): Storage container or bucket name

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        key=key,
container=container,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    key: str,
    *,
    client: AuthenticatedClient,
    container: None | str | Unset = UNSET,

) -> Any | HTTPValidationError | None:
    """ Download File

     Download a file from cloud storage.

    Requires authentication via Bearer token.

    Args:
        key: Object key/path to download.
        token: Validated access token.
        client: GCP storage client.
        container: Optional storage container or bucket override.

    Returns:
        File contents as streaming response.

    Raises:
        HTTPException: If file not found or download fails.

    Args:
        key (str):
        container (None | str | Unset): Storage container or bucket name

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
     """


    return (await asyncio_detailed(
        key=key,
client=client,
container=container,

    )).parsed
