from clerk_backend_api.security import authenticate_request
from clerk_backend_api.security.types import AuthenticateRequestOptions
from fastapi import HTTPException, Request


class ClerkLogin:
    """Checks the Clerk session token a request carries in its Authorization header, with the
    instance's public key: no call to Clerk, so the check works offline (#343)."""

    def __init__(self, jwt_key: str, authorized_parties: list[str]) -> None:
        # The frontend's origin is the token's `azp`. Without this check a token minted by
        # another site under the same root domain would pass. Only session tokens: the SDK
        # checks a machine token or API key by calling Clerk, so it would go out per request.
        self._options = AuthenticateRequestOptions(
            jwt_key=jwt_key,
            authorized_parties=authorized_parties,
            accepts_token=["session_token"],
        )

    def user_id(self, request: Request) -> str:
        """The signed-in user's Clerk id; 401 when the token is missing, expired, signed by
        another key or issued for another site."""
        state = authenticate_request(request, self._options)
        if not state.is_signed_in or state.payload is None:
            raise HTTPException(status_code=401, detail="Sign in to use Molecula.")
        return str(state.payload["sub"])
