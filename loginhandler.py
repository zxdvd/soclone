
import json
from urllib.parse import quote

from tornado import gen

from auths import BaiduOAuth2Mixin, GithubOAuth2Mixin, WeiboOAuth2Mixin
from settings import AUTH, HOST, REDIRECT_HOST

from base import BaseHandler, dbUsers

class CheckAdminHandler(BaseHandler):
    """Check if a user is admin; used in ningx aut_request module"""
    @gen.coroutine
    def get(self):
        _user = self.current_user
        if _user and len(_user) > 1:
            domain, uid = _user[0], _user[1]
            user = dbUsers.users.find_one({'authdomain': domain, 'uid': uid})
            if user and user.get('group') == 'admin':
                self.set_status(200)
                self.finish()
                return
        self.set_status(403)
        self.finish()

class GithubOauthHandler(BaseHandler, GithubOAuth2Mixin):
    """TODO XXX could get token from cookie in the future"""
    @gen.coroutine
    def get(self):
        _client_id = AUTH['github']['client_id']
        _secret = AUTH['github']['secret']
        if self.get_argument('code', False):
            auth_info = yield self.get_authenticated_user(
                redirect_uri='http://%s/auth/github' % REDIRECT_HOST,
                code = self.get_argument('code'),
                client_id=_client_id,
                client_secret=_secret)
            token = auth_info.get('access_token', None)
            if token:
                user_info = yield self.github_request('/user',
                        access_token=token)
                user_info['uid'] = user_info.get('id')
                user_info['uname'] = user_info.get('name', '')
                self.add_user(dbUsers.users, domain='github', token=token, **user_info)
                self.redirect('/')
        else:
            yield self.authorize_redirect(
                redirect_uri='http://%s/auth/github' % REDIRECT_HOST,
                client_id=_client_id)

class BaiduOauthHandler(BaseHandler, BaiduOAuth2Mixin):
    @gen.coroutine
    def get(self):
        _client_id = AUTH['baidu']['client_id']
        _secret = AUTH['baidu']['secret']
        if self.get_argument('code', False):
            auth_info = yield self.get_authenticated_user(
                redirect_uri='http://%s/auth/baidu' % REDIRECT_HOST,
                code = self.get_argument('code'),
                client_id=_client_id,
                client_secret=_secret)
            token = auth_info.get('access_token', None)
            if token:
                user_info = yield self.baidu_request('/passport/users/getLoggedInUser',
                        post_args={}, access_token=token)
                self.add_user(dbUsers.users, domain='baidu', token=token, **user_info)
                self.redirect('/')
        else:
            yield self.authorize_redirect(
                redirect_uri='http://%s/auth/baidu' % REDIRECT_HOST,
                client_id=_client_id,
                response_type='code')

class WeiboOauthHandler(BaseHandler, WeiboOAuth2Mixin):

    _OAUTH_GET_UID_URL = 'https://api.weibo.com/oauth2/get_token_info'

    @gen.coroutine
    def get(self):
        _client_id = AUTH['weibo']['client_id']
        _secret = AUTH['weibo']['secret']
        if self.get_argument('code', False):
            print(self.get_argument('code'))
            auth_info = yield self.get_authenticated_user(
                redirect_uri='http://%s/auth/weibo' % REDIRECT_HOST,
                code = self.get_argument('code'),
                client_id=_client_id,
                client_secret=_secret)
            token = auth_info.get('access_token', None)
            if token:
                get_uid = yield self.weibo_request(self._OAUTH_GET_UID_URL,
                        post_args={}, access_token=token)
                #get_uid has uid but no username which is I needed, then get it
                if get_uid.get('uid', None):
                    user_info = yield self.weibo_request(
                            'https://api.weibo.com/2/users/show.json',
                            access_token=token, uid=get_uid['uid'])
                    if user_info.get('id', None):
                        user_info['uid'] = user_info.pop('id')      #id to uid
                        user_info['uname'] = user_info['screen_name']
                        user_info.pop('domain')
                        self.add_user(dbUsers.users, domain='weibo',
                            token=token, **user_info)
                        self.redirect('/')
                    else:
                        print('TODO XXX: failed to get user_info')
                else:
                    print('TODO XXX: failed to get UID')
        else:
            yield self.authorize_redirect(
                redirect_uri='http://%s/auth/weibo' % REDIRECT_HOST,
                client_id=_client_id)
