import logging
import time

from fuocore.models import (
    BaseModel,
    SongModel,
    AlbumModel,
    ArtistModel,
    MvModel,
    PlaylistModel,
    LyricModel,
    SearchModel,
    UserModel,
    GeneratorProxy,
    SearchType,
)

from .provider import provider

logger = logging.getLogger(__name__)


class XBaseModel(BaseModel):
    _api = provider.api

    class Meta:
        allow_get = True
        provider = provider


def _deserialize(data, schema_cls):
    schema = schema_cls()
    obj = schema.load(data)
    return obj


def create_g(func, identifier, field='songs', schema=None):
    if schema is None:
        schema = NestedSongSchema
    data = func(identifier, page=1)
    # user_favorite_songs 接口返回的数据有 total 字段，
    # 但 playlist_detail_v2 接口返回的数据没有 total 字段，
    # 这里取 pagingVO 结构体中的 count 字段值作为 total
    total = int(data['pagingVO']['count'])

    def g():
        nonlocal data
        if data is None:
            yield from ()
        else:
            paging = data['pagingVO']
            # pagingVO 结构体中字段是 string 类型
            page = int(paging['page'])
            page_size = int(paging['pageSize'])
            pages = int(paging['pages'])
            while page <= pages:
                obj_data_list = data[field]
                for obj_data in obj_data_list:
                    yield _deserialize(obj_data, schema)
                page += 1
                data = func(identifier, page, page_size)
    return GeneratorProxy(g(), total)


class XMvModel(MvModel, XBaseModel):
    @classmethod
    def get(cls, identifier):
        data = cls._api.mv_detail(identifier)
        if data is not None:
            return _deserialize(data, MvSchema)


class XSongModel(SongModel, XBaseModel):

    class Meta:
        fields = ['mvid', 'q_media_mapping', 'expired_at']
        fields_no_get = ['expired_at']
        support_multi_quality = True

    @classmethod
    def get(cls, identifier):
        data = cls._api.song_detail(identifier)
        if data is None:
            return None
        return _deserialize(data, SongSchema)

    def refresh_url(self):
        song = self.get(self.identifier)
        self.url = song.url
        self.q_media_mapping = song.q_media_mapping
        self.expired_at = song.expired_at

    @property
    def is_expired(self):
        return self.expired_at is not None and time.time() >= self.expired_at

    @property
    def url(self):
        if time.time() > self._expired_at:
            logger.debug('song({}) url is expired, refresh...'.format(self))
            self.refresh_url()
        return self._url

    @url.setter
    def url(self, value):
        self._expired_at = time.time() + 60 * 60 * 1  # one hour
        self._url = value

    @property
    def lyric(self):
        if self._lyric is not None:
            return self._lyric
        content = self._api.song_lyric(self.identifier)
        self.lyric = LyricModel(
            identifier=self.identifier,
            content=content
        )
        return self._lyric

    @lyric.setter
    def lyric(self, value):
        self._lyric = value

    @property
    def mv(self):
        # FIXME: currently, api.mv_detail may raise error
        return None

        if self._mv is not None:
            return self._mv
        # 这里可能会先获取一次 mvid
        if self.mvid:
            mv = XMvModel.get(self.mvid)
            if mv is not None:
                self._mv = mv
                return self._mv
        return None

    @mv.setter
    def mv(self, value):
        self._mv = value

    # multi quality support

    def list_quality(self):
        return list((self.q_media_mapping or {}).keys())

    def get_media(self, quality):
        if self.is_expired:
            self.refresh_url()
        return self.q_media_mapping.get(quality)


class XAlbumModel(AlbumModel, XBaseModel):

    @classmethod
    def get(cls, identifier):
        data = cls._api.album_detail(identifier)
        if data is None:
            return None
        return _deserialize(data, AlbumSchema)


class XArtistModel(ArtistModel, XBaseModel):
    class Meta:
        allow_create_songs_g = True
        allow_create_albums_g = True

    @classmethod
    def get(cls, identifier):
        data = cls._api.artist_detail(identifier)
        if data is None:
            return None
        return _deserialize(data, ArtistSchema)

    @property
    def songs(self):
        if self._songs is None:
            self._songs = []
            data_songs = self._api.artist_songs(self.identifier)['songs'] or []
            if data_songs:
                for data_song in data_songs:
                    song = _deserialize(data_song, NestedSongSchema)
                    self._songs.append(song)
        return self._songs

    def create_songs_g(self):
        return create_g(self._api.artist_songs, self.identifier)

    @songs.setter
    def songs(self, value):
        self._songs = value

    def create_albums_g(self):
        return create_g(self._api.artist_albums, self.identifier, 'albums', AlbumSchema)


class XPlaylistModel(PlaylistModel, XBaseModel):

    class Meta:
        fields = ('uid', )
        allow_create_songs_g = True

    @classmethod
    def get(cls, identifier):
        # FIXME: 获取所有歌曲，而不仅仅是前 100 首
        data = cls._api.playlist_detail(identifier)
        if data is None:
            return None
        return _deserialize(data, PlaylistSchema)

    def add(self, song_id, **kwargs):
        rv = self._api.update_playlist_song(self.identifier, song_id, 'add')
        if rv:
            song = XSongModel.get(song_id)
            self.songs.append(song)
            return True
        return rv

    def remove(self, song_id, allow_not_exist=True):
        rv = self._api.update_playlist_song(self.identifier, song_id, 'del')
        for song in self.songs:
            if song.identifier == song_id:
                self.songs.remove(song)
        return rv

    def create_songs_g(self):
        return create_g(self._api.playlist_detail_v2, self.identifier)


class XSearchModel(SearchModel, XBaseModel):
    pass


class XUserModel(UserModel, XBaseModel):
    class Meta:
        allow_fav_songs_add = True
        allow_fav_songs_remove = True
        fields = ('access_token', )

    @classmethod
    def get(cls, identifier):
        user_data = cls._api.user_detail(identifier)
        if user_data is None:
            return None
        return _deserialize(user_data, UserSchema)

    @property
    def playlists(self):
        """获取用户创建的歌单

        如果不是用户本人，则不能获取用户默认精选集
        """
        if self._playlists is None:
            playlists_data = self._api.user_playlists(self.identifier)
            playlists = []
            for playlist_data in playlists_data:
                playlist = _deserialize(playlist_data, PlaylistSchema)
                playlists.append(playlist)
            self._playlists = playlists
        return self._playlists

    @playlists.setter
    def playlists(self, value):
        self._playlists = value  # pylint: disable=all

    @property
    def fav_playlists(self):
        if self._fav_playlists is None:
            playlists_data = self._api.user_favorite_playlists(self.identifier)
            fav_playlists = []
            for playlist_data in playlists_data:
                playlist = _deserialize(playlist_data, PlaylistSchema)
                fav_playlists.append(playlist)
            self._fav_playlists = fav_playlists
        return self._fav_playlists

    @fav_playlists.setter
    def fav_playlists(self, value):
        self._fav_playlists = value

    @property
    def fav_songs(self):
        return create_g(self._api.user_favorite_songs, self.identifier)

    @fav_songs.setter
    def fav_songs(self, value):
        pass

    def add_to_fav_songs(self, song_id):
        return self._api.update_favorite_song(song_id, 'add')

    def remove_from_fav_songs(self, song_id):
        return self._api.update_favorite_song(song_id, 'del')


def search(keyword, **kwargs):
    type_ = SearchType.parse(kwargs['type_'])
    type_type_map = {
        SearchType.so: 1,
        SearchType.al: 10,
        SearchType.ar: 100,
        SearchType.pl: 1000,
    }
    data = provider.api.search(keyword, type_=type_type_map[type_])
    result = _deserialize(data, SearchSchema)
    result.q = keyword
    return result


from .schemas import (
    AlbumSchema,
    ArtistSchema,
    MvSchema,
    PlaylistSchema,
    NestedSongSchema,
    SongSchema,
    SearchSchema,
    UserSchema,
)  # noqa
