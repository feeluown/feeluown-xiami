# -*- coding: utf-8 -*-

import json
import logging
import os

from .excs import XiamiIOError
from .provider import provider
from .models import XUserModel

from feeluown.consts import DATA_DIR

__alias__ = '虾米音乐'
__version__ = '0.1a1'
__desc__ = '虾米音乐'

logger = logging.getLogger(__name__)
USER_INFO_FILE = DATA_DIR + '/xiami_user_info.json'


def dump_user(user):
    assert user.access_token is not None
    data = {
        'id': user.identifier,
        'name': user.name,
        'access_token': user.access_token,
    }
    with open(USER_INFO_FILE, 'w') as f:
        json.dump(data, f)


def load_user():
    if not os.path.exists(USER_INFO_FILE):
        return None
    with open(USER_INFO_FILE) as f:
        user_data = json.load(f)
    user = XUserModel(source=provider.identifier,
                      identifier=user_data['id'],
                      name=user_data['name'],
                      access_token=user_data['access_token'])
    return user


class Xiami(object):
    """GUI 控制"""

    instance = None

    def __init__(self, app):
        self._app = app
        self._user = None

        self._pm = self._app.pvd_uimgr.create_item(
            name=provider.identifier,
            text='虾米音乐',
            symbol='♩ ',
            desc='')
        self._pm.clicked.connect(self.show_provider)
        self._app.pvd_uimgr.add_item(self._pm)

        Xiami.instance = self

    def show_login_dialog(self):
        from .ui import LoginDialog
        dialog = LoginDialog()
        dialog.login_success.connect(self.bind_user)
        dialog.exec()

    def bind_user(self, user, dump=True):
        if dump:
            dump_user(user)
        self._user = user
        provider.auth(user)

    def show_fav_songs(self):
        self._app.ui.songs_table_container.show_songs(songs_g=self._user.fav_songs)

    def show_fav_albums(self):
        self._app.ui.songs_table_container.show_albums_coll(self._user.fav_albums)
        
    def show_rec_songs(self):
        self._app.ui.songs_table_container.show_songs(self._user.rec_songs)

    def show_provider(self):
        """展示虾米首页

        要求用户已经登录，支持展示用户名、用户歌单列表

        TODO: 可以考虑支持展示榜单等
        """
        if self._user is None:
            user = load_user()
            if user is None:
                self.show_login_dialog()
            else:
                # FIXME: 电台、日推等与accessToken强相关，这类歌曲可能与官方客户端不一致
                self.bind_user(user, dump=False)
        if self._user is not None:
            # 显示用户名
            self._pm.text = '虾米音乐 - {}'.format(self._user.name)
            # 显示播放列表/歌单
            self._app.pl_uimgr.clear()
            self._app.pl_uimgr.add(self._user.playlists)
            self._app.pl_uimgr.add(self._user.fav_playlists, is_fav=True)
            # self._app.pl_uimgr.add(self._user.rec_playlists)
            # 显示用户收藏的歌曲
            self._app.ui.left_panel.my_music_con.show()
            self._app.ui.left_panel.playlists_con.show()
            self._app.mymusic_uimgr.clear()

            mymusic_fm_item = self._app.mymusic_uimgr.create_item('📻 私人 FM')
            mymusic_fm_item.clicked.connect(self.activate_fm)
            self._app.mymusic_uimgr.add_item(mymusic_fm_item)
            mymusic_rec_item = self._app.mymusic_uimgr.create_item('📅 每日推荐')
            mymusic_rec_item.clicked.connect(self.show_rec_songs)
            self._app.mymusic_uimgr.add_item(mymusic_rec_item)
            mymusic_fav_item = self._app.mymusic_uimgr.create_item('♥ 我的收藏')
            mymusic_fav_item.clicked.connect(self.show_fav_songs)
            self._app.mymusic_uimgr.add_item(mymusic_fav_item)
            mymusic_albums_item = self._app.mymusic_uimgr.create_item('♥ 我的专辑')
            mymusic_albums_item.clicked.connect(self.show_fav_albums)
            self._app.mymusic_uimgr.add_item(mymusic_albums_item)

    def activate_fm(self):
        self._app.fm.activate(self.fetch_fm_songs)

    def fetch_fm_songs(self, *args, **kwargs):
        songs = provider._user.get_radio()  # noqa
        if songs is None:
            raise XiamiIOError('unknown error: get no radio songs')
        return songs


def enable(app):
    app.library.register(provider)
    if app.mode & app.GuiMode:
        app.__ui_ctl = Xiami(app)


def disable(app):
    app.library.deregister(provider)
