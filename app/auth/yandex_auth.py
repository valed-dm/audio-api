from authlib.integrations.starlette_client import OAuth
from fastapi.security import OAuth2AuthorizationCodeBearer

from app.core.config import settings

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://oauth.yandex.com/authorize",
    tokenUrl="https://oauth.yandex.com/token",
)


def setup_oauth():
    oa = OAuth()

    oa.register(
        name="yandex",
        client_id=settings.YANDEX_CLIENT_ID,
        client_secret=settings.YANDEX_CLIENT_SECRET,
        access_token_url=settings.YANDEX_TOKEN_URL,
        authorize_url="https://oauth.yandex.com/authorize",
        api_base_url="https://login.yandex.com",
        userinfo_endpoint="https://login.yandex.ru/info",
        client_kwargs={
            "scope": "login:email login:info",
            "token_endpoint_auth_method": "client_secret_post",
        },
        server_metadata_url=None,
    )
    return oa


oauth = setup_oauth()
