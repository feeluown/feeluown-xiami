import time
import hashlib
import json
import logging

import requests

from .excs import XiamiIOError

logger = logging.getLogger(__name__)

site_url = 'http://www.xiami.com'
api_base_url = 'http://h5api.m.xiami.com'


def _gen_url(action):
    return api_base_url + '/h5/{}/1.0/'.format(action)


class API(object):
    def __init__(self):
        self._headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip,deflate,sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,gl;q=0.6,zh-TW;q=0.4',
            'Connection': 'keep-alive',
            # 'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'http://h.xiami.com',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6)' \
                          ' AppleWebKit/537.36 (KHTML, like Gecko) '\
                          'Chrome/77.0.3865.120 Safari/537.36'
        }
        self._cookies = {}
        self._app_key = '23649156'  # NOTE: appId 和 app_key 是配对使用
        self._req_header = {'appId': 200, 'platformId': 'h5'}
        self._req_token = None
        self._http = None

    def set_access_token(self, access_token):
        self._req_header['accessToken'] = access_token

    def set_http(self, http):
        self._http = http
        self._http.headers.update(self._headers)

    @property
    def http(self):
        # TODO: 将来可能会使用是一个全局唯一的 Request 对象
        # 目前开发时，我们默认未来的 Request 对象接口兼容官方 requests
        if self._http is None:
            self.set_http(requests.Session())
        return self._http

    def _sign_payload(self, payload):
        """使用 appkey 对 payload 进行签名，返回新的请求参数
        """
        app_key = self._app_key
        t = int(time.time() * 1000)
        request_str = {
            'header': self._req_header,
            'model': payload
        }
        data = json.dumps({'requestStr': json.dumps(request_str)})
        data_str = '{}&{}&{}&{}'.format(self._req_token, t, app_key, data)
        sign = hashlib.md5(data_str.encode('utf-8')).hexdigest()
        params = {
            't': t,
            'appKey': app_key,
            'sign': sign,
            'data': data,
        }
        return params

    def _fetch_token(self):
        action = 'mtop.alimusic.music.songservice.getsongdetail'
        token = self.request(action, {'songId': '1'}, need_token=False)
        self._req_token = token
        return token

    def request(self, action, payload, timeout=3, need_token=True,
                retry_on_tokenexpired=True):
        """
        虾米 API 请求流程：

        1. 获取一个 token：这里 need_token 为 False 时，意为获取 token，
           根据观察，这个 token 一般是 7 天过期
        2. 对请求签名：见 _sign_payload 方法
        3. 发送请求
        """
        if need_token is True and self._req_token is None:  # 获取 token
            self._fetch_token()

        url = _gen_url(action)
        params = self._sign_payload(payload)
        response = self.http.get(url, params=params,
                                 timeout=timeout)
        # if need_token is False, this request must be used for fetching token
        if need_token is False:
            resp_cookies = response.cookies.get_dict()
            m_h5_tk = resp_cookies['_m_h5_tk']
            return m_h5_tk.split('_')[0]

        rv = response.json()
        code, msg = rv['ret'][0].split('::')
        # app id 和 key 不匹配，一般应该不会出现这种情况
        if code == 'FAIL_SYS_PARAMINVALID_ERROR':
            raise XiamiIOError('unexpected error, app id or app key mismatch')
        elif code == 'FAIL_SYS_TOKEN_EXOIRED':  # 刷新 token
            self._fetch_token()
            if retry_on_tokenexpired:
                return self.request(action, payload, timeout=timeout,
                                    retry_on_tokenexpired=False)
        elif code == 'FAIL_BIZ_GLOBAL_NEED_LOGIN':
            # TODO: 单独定义一个 Exception
            raise XiamiIOError('you need login first')
        elif code == 'FAIL_SYS_WJAS_DENIED':
            # FAIL_SYS_WJAS_DENIED::请下载升级最新版本APP
            raise XiamiIOError('this API is unavailable anymore')
        else:
            if code != 'SUCCESS':
                logger.warning('Xiami request failed:: '
                               'req_action: {}, req_payload: {}\n'
                               'response: {}'
                               .format(action, payload, rv))
            return code, msg, rv

    # 用户登陆
    def login(self, email, password):
        """
        :password: user password md5 digest
        """
        payload = {
            'account': email,
            'password': password
        }
        code, msg, rv = self.request(
            'mtop.alimusic.xuser.facade.xiamiuserservice.login',
            payload
        )
        if code == 'SUCCESS':
            # TODO: 保存 refreshToken 和过期时间等更多信息
            # 根据目前观察，token 过期时间有三年
            accessToken = rv['data']['data']['accessToken']
            self.set_access_token(accessToken)
        return rv  # rv -> return value

    def search(self, keywords, type_=1, page=1, limit=30):
        if type_ == 1:
            action = 'mtop.alimusic.search.searchservice.searchsongs'
        elif type_ == 10:
            action = 'mtop.alimusic.search.searchservice.searchalbums'
        elif type_ == 100:
            action = 'mtop.alimusic.search.searchservice.searchartists'
        elif type_ == 1000:
            action = 'mtop.alimusic.search.searchservice.searchcollects'
        else:
            raise ValueError('invalid type_:%d', type_)

        payload = {
            'key': keywords,
            'pagingVO': {
                'page': page,
                'pageSize': limit
            }
        }
        _, _, rv = self.request(action, payload)
        return rv['data']['data']

    def song_detail(self, song_id):
        action = 'mtop.alimusic.music.songservice.getsongdetail'
        payload = {'songId': song_id}
        code, msg, rv = self.request(action, payload)
        if code == 'SUCCESS':
            return rv['data']['data']['songDetail']
        return None

    def songs_detail(self, song_ids):
        action = 'mtop.alimusic.music.songservice.getsongs'
        songs = []
        # FIXME: 这里写个 for 循环可能会有点问题
        for start in range(0, len(song_ids), 200):
            payload = {'songIds': song_ids[start:min(start + 200, len(song_ids))]}
            code, msg, rv = self.request(action, payload)
            songs.extend(rv['data']['data']['songs'])
        return songs

    def song_lyric(self, song_id):
        action = 'mtop.alimusic.music.lyricservice.getsonglyrics'
        payload = {'songId': song_id}
        code, msg, rv = self.request(action, payload)
        for lyric in rv['data']['data']['lyrics']:
            if int(lyric['type']) == 2:
                return lyric['content']
        return ''

    def mv_detail(self, mv_id):
        action = 'mtop.alimusic.music.mvservice.getmvdetail'
        payload = {'mvId': mv_id}
        _, _, rv = self.request(action, payload)
        # 当 id 不存在时，rv['data']['data'] 为空字典
        return rv['data']['data'].get('mvDetailVO')

    # 专辑详情 专辑评论
    def album_detail(self, album_id):
        action = 'mtop.alimusic.music.albumservice.getalbumdetail'
        payload = {'albumId': album_id}
        code, msg, rv = self.request(action, payload)
        return rv['data']['data']['albumDetail']

    # 歌手详情 歌手专辑 歌手歌曲 歌手评论
    def artist_detail(self, artist_id):
        action = 'mtop.alimusic.music.artistservice.getartistdetail'
        payload = {'artistId': artist_id}
        code, msg, rv = self.request(action, payload)
        return rv['data']['data']['artistDetailVO']

    def artist_songs(self, artist_id, page=1, page_size=50):
        action = 'mtop.alimusic.music.songservice.getartistsongs'
        payload = {
            'artistId': artist_id,
            'pagingVO': {
                'page': page,
                'pageSize': page_size
            }
        }
        code, msg, rv = self.request(action, payload)
        return rv['data']['data']

    def artist_albums(self, artist_id, page=1, page_size=20):
        action = 'mtop.alimusic.music.albumservice.getartistalbums'
        payload = {
            'artistId': artist_id,
            'pagingVO': {
                'page': page,
                'pageSize': page_size
            }
        }
        code, msg, rv = self.request(action, payload)
        return rv['data']['data']

    def playlist_detail(self, playlist_id):
        """获取歌单详情

        如果歌单歌曲数超过 100 时，该接口的 songs 字段不会包含所有歌曲，
        但是它有个 allSongs 字段，会包含所有歌曲的 ID。
        """
        action = 'mtop.alimusic.music.list.collectservice.getcollectdetail'
        payload = {'listId': playlist_id}
        code, msg, rv = self.request(action, payload)
        return rv['data']['data']['collectDetail']

    def playlist_detail_v2(self, playlist_id, page=1, page_size=200):
        """获取歌单详情

        NOTE: 当设置 limit 大于 200 时，虾米服务端好像会忽略这个设置，将 limit 设为 200
        """
        action = 'mtop.alimusic.music.list.collectservice.getcollectsongs'
        payload = {
            'listId': playlist_id,
            'pagingVO': {
                'page': page,
                'pageSize': page_size
            }
        }
        code, msg, rv = self.request(action, payload)
        return rv['data']['data']

    # 用户详情 用户歌单 用户收藏(歌曲 专辑 歌手 歌单)
    def user_detail(self, user_id):
        action = 'mtop.alimusic.xuser.facade.xiamiuserservice.getuserinfobyuserid'
        payload = {'userId': user_id}
        code, msg, rv = self.request(action, payload)
        return rv['data']['data']

    def user_playlists(self, user_id, page=1, limit=30):
        """
        NOTE: 用户歌单有可能是仅自己可见
        """
        action = 'mtop.alimusic.music.list.collectservice.getcollectbyuser'
        payload = {
            'userId': user_id,
            'pagingVO': {
                'page': page,
                'pageSize': limit
            }
        }
        code, msg, rv = self.request(action, payload)
        # TODO: 支持获取更多
        return rv['data']['data']['collects']

    def user_favorite_playlists(self, user_id, page=1, limit=30):
        action = 'mtop.alimusic.fav.collectfavoriteservice.getfavoritecollects'
        payload = {
            'userId': user_id,
            'pagingVO': {
                'page': page,
                'pageSize': limit
            }
        }
        code, msg, rv = self.request(action, payload)
        return rv['data']['data']['collects']

    def user_favorite_songs(self, user_id, page=1, page_size=50):
        """获取用户收藏的歌曲

        NOTE: 当设置 limit 大于 200 时，虾米服务端好像会忽略这个设置，将 limit 设为 20
        """
        action = 'mtop.alimusic.fav.songfavoriteservice.getfavoritesongs'
        payload = {
            'userId': user_id,
            'pagingVO': {
                'page': page,
                'pageSize': page_size
            }
        }
        code, msg, rv = self.request(action, payload)
        # TODO: 支持获取更多
        return rv['data']['data']

    def update_favorite_song(self, song_id, op):
        """
        :param str op: `add` or `del`
        """
        op = 'un' if op == 'del' else ''
        action = 'mtop.alimusic.fav.songfavoriteservice.{}favoritesong'.format(op)
        payload = {
            'songId': song_id
        }
        code, msg, rv = self.request(action, payload)
        return rv['data']['data']['status'] == 'true'

    def update_playlist_song(self, playlist_id, song_id, op):
        """从播放列表删除或者增加一首歌曲

        如果歌曲不存在与歌单中，删除时返回 True；如果歌曲已经存在于
        歌单，添加时也返回 True。
        """
        action = 'mtop.alimusic.music.list.collectservice.{}songs'.format(
            'delete' if op == 'del' else 'add')
        payload = {
            'listId': playlist_id,
            'songIds': [song_id]
        }
        code, msg, rv = self.request(action, payload)
        return rv['data']['data']['success'] == 'true'

    def user_favorite_artists(self, user_id, page=1, page_size=50):
        """获取用户收藏的歌手

        NOTE: 当设置 limit 大于 200 时，虾米服务端好像会忽略这个设置，将 limit 设为 20
        """
        action = 'mtop.alimusic.fav.artistfavoriteservice.getfavoriteartists'
        payload = {
            'userId': user_id,
            'pagingVO': {
                'page': page,
                'pageSize': page_size
            }
        }
        code, msg, rv = self.request(action, payload)
        # TODO: 支持获取更多
        return rv['data']['data']

    def user_favorite_albums(self, user_id, page=1, page_size=50):
        """获取用户收藏的专辑

        NOTE: 当设置 limit 大于 200 时，虾米服务端好像会忽略这个设置，将 limit 设为 20
        """
        action = 'mtop.alimusic.fav.albumfavoriteservice.getfavoritealbums'
        payload = {
            'userId': user_id,
            'pagingVO': {
                'page': page,
                'pageSize': page_size
            }
        }
        code, msg, rv = self.request(action, payload)
        # TODO: 支持获取更多
        return rv['data']['data']

    # 私人FM 每日推荐歌曲 每日推荐歌单
    def personal_fm(self):
        action = 'mtop.alimusic.music.radio.getradiosongs'
        payload = {
            'radioType': 1
        }
        code, msg, rv = self.request(action, payload)
        return rv['data']['data']['list']

    def recommend_songs(self):
        action = 'mtop.alimusic.recommend.songservice.getdailysongs'
        code, msg, rv = self.request(action, dict())
        return rv['data']['data']['songs']

    def recommend_playlists(self):
        action = 'mtop.alimusic.music.list.collectservice.getcollects'
        code, msg, rv = self.request(action, dict())
        return rv['data']['data']['collects']


api = API()
