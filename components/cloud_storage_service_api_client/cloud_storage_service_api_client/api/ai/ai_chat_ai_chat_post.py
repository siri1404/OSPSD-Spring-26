from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.ai_chat_ai_chat_post_response_ai_chat_ai_chat_post import AiChatAiChatPostResponseAiChatAiChatPost
from ...models.body_ai_chat_ai_chat_post import BodyAiChatAiChatPost
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: BodyAiChatAiChatPost,
    x_container: None | str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(x_container, Unset):
        headers["X-Container"] = x_container

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/ai/chat",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AiChatAiChatPostResponseAiChatAiChatPost | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = AiChatAiChatPostResponseAiChatAiChatPost.from_dict(response.json())

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
) -> Response[AiChatAiChatPostResponseAiChatAiChatPost | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: BodyAiChatAiChatPost,
    x_container: None | str | Unset = UNSET,
) -> Response[AiChatAiChatPostResponseAiChatAiChatPost | HTTPValidationError]:
    """Ai Chat

     Natural-language interface to cloud storage operations.

    Accepts a plain-English prompt and returns a human-readable response.
    The AI may call appropriate storage tools to fulfill the request.
    A default container can be supplied via the X-Container header.

    Args:
        x_container (None | str | Unset):
        body (BodyAiChatAiChatPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AiChatAiChatPostResponseAiChatAiChatPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
        x_container=x_container,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    body: BodyAiChatAiChatPost,
    x_container: None | str | Unset = UNSET,
) -> AiChatAiChatPostResponseAiChatAiChatPost | HTTPValidationError | None:
    """Ai Chat

     Natural-language interface to cloud storage operations.

    Accepts a plain-English prompt and returns a human-readable response.
    The AI may call appropriate storage tools to fulfill the request.
    A default container can be supplied via the X-Container header.

    Args:
        x_container (None | str | Unset):
        body (BodyAiChatAiChatPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AiChatAiChatPostResponseAiChatAiChatPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
        x_container=x_container,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: BodyAiChatAiChatPost,
    x_container: None | str | Unset = UNSET,
) -> Response[AiChatAiChatPostResponseAiChatAiChatPost | HTTPValidationError]:
    """Ai Chat

     Natural-language interface to cloud storage operations.

    Accepts a plain-English prompt and returns a human-readable response.
    The AI may call appropriate storage tools to fulfill the request.
    A default container can be supplied via the X-Container header.

    Args:
        x_container (None | str | Unset):
        body (BodyAiChatAiChatPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AiChatAiChatPostResponseAiChatAiChatPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
        x_container=x_container,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: BodyAiChatAiChatPost,
    x_container: None | str | Unset = UNSET,
) -> AiChatAiChatPostResponseAiChatAiChatPost | HTTPValidationError | None:
    """Ai Chat

     Natural-language interface to cloud storage operations.

    Accepts a plain-English prompt and returns a human-readable response.
    The AI may call appropriate storage tools to fulfill the request.
    A default container can be supplied via the X-Container header.

    Args:
        x_container (None | str | Unset):
        body (BodyAiChatAiChatPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AiChatAiChatPostResponseAiChatAiChatPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            x_container=x_container,
        )
    ).parsed
