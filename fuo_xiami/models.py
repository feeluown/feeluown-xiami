import logging
import time

from fuocore.models import (
    BaseModel,
    SongModel,
    MvModel,
    AlbumModel,
    ArtistModel,
    PlaylistModel,
    LyricModel,
    SearchModel,
    UserModel,
)

from .provider import provider

logger = logging.getLogger(__name__)


class XBaseModel(BaseModel):
    _api = provider.api

    class Meta:
        allow_get = True
        provider = provider


def _deserialize(data, schema_cls):
    schema = schema_cls(strict=True)
    obj, _ = schema.load(data)
    return obj


class XMvModel(MvModel, XBaseModel):

    @classmethod
    def get(cls, identifier):
        data = cls._api.mv_detail(identifier)
        if data is not None:
            mv, _ = MvSchema(strict=True).load(data)
            return mv
        return None


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
        if self._mv is not None:
            return self._mv
        # 这里可能会先获取一次 mvid
        if self.mvid:
            mv = XMvModel.get(self.mvid)
            if mv is not None:
                self._mv = mv
                return self._mv
        self.mvid = None
        return None

    @mv.setter
    def mv(self, value):
        self._mv = value

    # multi quality support

    def list_quality(self):
        return list(self.q_media_mapping.keys())

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
        data = self._api.artist_songs(self.identifier, page=1)
        if data is None:
            yield from ()
        else:
            paging = data['pagingVO']
            page = int(paging['page'])
            page_size = int(paging['pageSize'])
            count = int(paging['count'])
            num = 0
            while num < count:
                data_songs = data['songs']
                for data_song in data_songs:
                    yield _deserialize(data_song, NestedSongSchema)
                    num += 1
                page += 1
                data = self._api.artist_songs(
                    self.identifier, page=page, page_size=page_size)

    @songs.setter
    def songs(self, value):
        self._songs = value


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
        data = self._api.playlist_detail_v2(self.identifier, page=1)
        if data is None:
            yield from ()
        else:
            paging = data['pagingVO']
            page = int(paging['page'])
            page_size = int(paging['pageSize'])
            pages = int(paging['pages'])
            while page <= pages:
                songs_data = data['songs']
                for song_data in songs_data:
                    yield _deserialize(song_data, NestedSongSchema)
                page += 1
                data = self._api.playlist_detail_v2(
                    self.identifier, page=page, page_size=page_size)


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
        """
        FIXME: 支持获取所有的收藏歌曲
        """
        if self._fav_songs is None:
            data = self._api.user_favorite_songs(self.identifier, page=1)
            if data is None:
                yield from ()
            else:
                paging = data['pagingVO']
                page = int(paging['page'])
                page_size = int(paging['pageSize'])
                pages = int(paging['pages'])
                while page <= pages:
                    songs_data = data['songs']
                    for song_data in songs_data:
                        yield _deserialize(song_data, NestedSongSchema)
                    page += 1
                    data = self._api.user_favorite_songs(
                        self.identifier, page=page, page_size=page_size)


    @fav_songs.setter
    def fav_songs(self, value):
        self._fav_songs = value

    def add_to_fav_songs(self, song_id):
        return self._api.update_favorite_song(song_id, 'add')

    def remove_from_fav_songs(self, song_id):
        return self._api.update_favorite_song(song_id, 'del')


def search(keyword, **kwargs):
    data = provider.api.search(keyword, **kwargs)
    schema = SongSearchSchema(strict=True)
    result, _ = schema.load(data)
    result.q = keyword
    return result


from .schemas import (
    AlbumSchema,
    ArtistSchema,
    PlaylistSchema,
    NestedSongSchema,
    MvSchema,
    SongSchema,
    SongSearchSchema,
    UserSchema,
)  # noqa
