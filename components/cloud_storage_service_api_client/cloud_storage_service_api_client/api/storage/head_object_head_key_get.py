from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.object_info_response import ObjectInfoResponse
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
        "url": "/head/{key}".format(key=quote(str(key), safe=""),),
        "params": params,
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | ObjectInfoResponse | None:
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


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | ObjectInfoResponse]:
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

) -> Response[HTTPValidationError | ObjectInfoResponse]:
    """ Head Object

     Get metadata for an object without downloading its contents.

    Requires authentication via Bearer token.

    Args:
        key: Object key/path to query.
        token: Validated access token.
        client: GCP storage client.
        container: Optional storage container or bucket override.

    Returns:
        Object metadata.

    Raises:
        HTTPException: If object not found or query fails.

    Args:
        key (str):
        container (None | str | Unset): Storage container or bucket name

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ObjectInfoResponse]
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

) -> HTTPValidationError | ObjectInfoResponse | None:
    """ Head Object

     Get metadata for an object without downloading its contents.

    Requires authentication via Bearer token.

    Args:
        key: Object key/path to query.
        token: Validated access token.
        client: GCP storage client.
        container: Optional storage container or bucket override.

    Returns:
        Object metadata.

    Raises:
        HTTPException: If object not found or query fails.

    Args:
        key (str):
        container (None | str | Unset): Storage container or bucket name

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ObjectInfoResponse
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

) -> Response[HTTPValidationError | ObjectInfoResponse]:
    """ Head Object

     Get metadata for an object without downloading its contents.

    Requires authentication via Bearer token.

    Args:
        key: Object key/path to query.
        token: Validated access token.
        client: GCP storage client.
        container: Optional storage container or bucket override.

    Returns:
        Object metadata.

    Raises:
        HTTPException: If object not found or query fails.

    Args:
        key (str):
        container (None | str | Unset): Storage container or bucket name

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ObjectInfoResponse]
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

) -> HTTPValidationError | ObjectInfoResponse | None:
    """ Head Object

     Get metadata for an object without downloading its contents.

    Requires authentication via Bearer token.

    Args:
        key: Object key/path to query.
        token: Validated access token.
        client: GCP storage client.
        container: Optional storage container or bucket override.

    Returns:
        Object metadata.

    Raises:
        HTTPException: If object not found or query fails.

    Args:
        key (str):
        container (None | str | Unset): Storage container or bucket name

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ObjectInfoResponse
     """


    return (await asyncio_detailed(
        key=key,
client=client,
container=container,

    )).parsed
