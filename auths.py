
import functools
from urllib.parse import urlencode

from tornado import escape, httpclient
from tornado.auth import OAuth2Mixin, _auth_return_future, AuthError

class BaiduOAuth2Mixin(OAuth2Mixin):
    """Baidu authentication using OAuth2."""

    _OAUTH_AUTHORIZE_URL = 'http://openapi.baidu.com/oauth/2.0/authorize'
    _OAUTH_ACCESS_TOKEN_URL = 'https://openapi.baidu.com/oauth/2.0/token'
    _BAIDU_BASE_URL = 'https://openapi.baidu.com/rest/2.0'
    _OAUTH_NO_CALLBACKS = False

    @_auth_return_future
    def get_authenticated_user(self, redirect_uri, code, client_id,
            client_secret, callback):
        http = httpclient.AsyncHTTPClient()
        body = urlencode({
            "redirect_uri": redirect_uri,
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
        })

        http.fetch(self._OAUTH_ACCESS_TOKEN_URL,
                   functools.partial(self._on_access_token, callback),
                   method="POST", body=body)

    def _on_access_token(self, future, response):
        if response.error:
            future.set_exception(AuthError('Baidu auth error: %s' % str(response)))
            return
        future.set_result(escape.json_decode(response.body))

    @_auth_return_future
    def baidu_request(self, path, callback, access_token=None,
            post_args=None, **args):
        """there is method oauth2_request in class OAuth2Mixin in dev branch of 
        Tornado (4.3). I copied the code here since dev branch not released"""
        all_args = {}
        url = self._BAIDU_BASE_URL + path
        if access_token:
            all_args['access_token'] = access_token
            all_args.update(args)
        if all_args:
            url += "?" + urlencode(all_args)
        callback = functools.partial(self._on_baidu_request, callback)
        http = httpclient.AsyncHTTPClient()
        if post_args is not None:
            http.fetch(url, method="POST", body=urlencode(post_args),
                    callback=callback)
        else:
            http.fetch(url, callback=callback)

    def _on_baidu_request(self, future, response):
        if response.error:
            future.set_exception(AuthError('Error response %s fetching %s' %
                (response.error, response.request.url)))
            return
        future.set_result(escape.json_decode(response.body))
