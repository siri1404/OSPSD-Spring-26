from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.o_auth_callback_response import OAuthCallbackResponse
from typing import cast



def _get_kwargs(
    *,
    code: str,
    state: str,

) -> dict[str, Any]:
    

    

    params: dict[str, Any] = {}

    params["code"] = code

    params["state"] = state


    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}


    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/auth/callback",
        "params": params,
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | OAuthCallbackResponse | None:
    if response.status_code == 200:
        response_200 = OAuthCallbackResponse.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | OAuthCallbackResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    code: str,
    state: str,

) -> Response[HTTPValidationError | OAuthCallbackResponse]:
    """ Oauth Callback

     Handle OAuth 2.0 callback from Google.

    Exchanges authorization code for provider access token and creates a service-owned session.

    Args:
        code: Authorization code from Google OAuth.
        state: State parameter for CSRF validation.
        config: OAuth configuration.

    Returns:
        Service-owned session token (opaque, not the provider token).

    Raises:
        HTTPException: If state is invalid or token exchange fails.

    Args:
        code (str): Authorization code from Google
        state (str): State parameter for CSRF protection

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | OAuthCallbackResponse]
     """


    kwargs = _get_kwargs(
        code=code,
state=state,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    *,
    client: AuthenticatedClient | Client,
    code: str,
    state: str,

) -> HTTPValidationError | OAuthCallbackResponse | None:
    """ Oauth Callback

     Handle OAuth 2.0 callback from Google.

    Exchanges authorization code for provider access token and creates a service-owned session.

    Args:
        code: Authorization code from Google OAuth.
        state: State parameter for CSRF validation.
        config: OAuth configuration.

    Returns:
        Service-owned session token (opaque, not the provider token).

    Raises:
        HTTPException: If state is invalid or token exchange fails.

    Args:
        code (str): Authorization code from Google
        state (str): State parameter for CSRF protection

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | OAuthCallbackResponse
     """


    return sync_detailed(
        client=client,
code=code,
state=state,

    ).parsed

async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    code: str,
    state: str,

) -> Response[HTTPValidationError | OAuthCallbackResponse]:
    """ Oauth Callback

     Handle OAuth 2.0 callback from Google.

    Exchanges authorization code for provider access token and creates a service-owned session.

    Args:
        code: Authorization code from Google OAuth.
        state: State parameter for CSRF validation.
        config: OAuth configuration.

    Returns:
        Service-owned session token (opaque, not the provider token).

    Raises:
        HTTPException: If state is invalid or token exchange fails.

    Args:
        code (str): Authorization code from Google
        state (str): State parameter for CSRF protection

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | OAuthCallbackResponse]
     """


    kwargs = _get_kwargs(
        code=code,
state=state,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    code: str,
    state: str,

) -> HTTPValidationError | OAuthCallbackResponse | None:
    """ Oauth Callback

     Handle OAuth 2.0 callback from Google.

    Exchanges authorization code for provider access token and creates a service-owned session.

    Args:
        code: Authorization code from Google OAuth.
        state: State parameter for CSRF validation.
        config: OAuth configuration.

    Returns:
        Service-owned session token (opaque, not the provider token).

    Raises:
        HTTPException: If state is invalid or token exchange fails.

    Args:
        code (str): Authorization code from Google
        state (str): State parameter for CSRF protection

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | OAuthCallbackResponse
     """


    return (await asyncio_detailed(
        client=client,
code=code,
state=state,

    )).parsed
