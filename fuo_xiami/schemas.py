import logging
import time
from urllib.parse import urlparse

from marshmallow import Schema, fields, post_load, EXCLUDE

from fuocore.media import Media


logger = logging.getLogger(__name__)


class ArtistSchema(Schema):
    """歌手详情 Schema、歌曲歌手简要信息 Schema
    """

    class Meta:
        unknown = EXCLUDE

    identifier = fields.Int(data_key='artistId', required=True)
    name = fields.Str(data_key='artistName', required=True)
    cover = fields.Str(data_key='artistLogo', missing=None)
    desc = fields.Str(data_key='description', missing=None)

    @post_load
    def create_model(self, data, **kwargs):
        return XArtistModel(**data)


class ListenFileSchema(Schema):
    """Song listenfile"""

    class Meta:
        unknown = EXCLUDE

    quality = fields.Str(required=True)
    # song_detail and artist_songs api return different listenFile struct,
    # the struct song_detail api return only contains url field, while
    # the struct artist_songs api return only contains listenFile field.
    url = fields.Str(missing=None)
    url_bak = fields.Str(data_key='listenFile', missing=None)
    format = fields.Str(required=True)
    # expire = fields.Str(required=True)

    @post_load
    def process_url(self, data, **kwargs):
        url = data['url'] or data['url_bak']
        data['url'] = url
        return data

    @classmethod
    def to_q_media_mapping(cls, lfiles):
        q_media_mapping = {}
        if lfiles:
            q_q_mapping = {'m': 'shq',  # for example: flac
                           's': 'shq',
                           'h': 'hq',
                           'l': 'sq',
                           'f': 'lq',
                           'e': 'lq'}
            for lfile in filter(lambda lfile: lfile['url'], lfiles):
                url = lfile['url']
                quality = lfile['quality']
                format = lfile['format']
                # url example: http://m720.xiami.net/...
                try:
                    bitrate = int(urlparse(url).netloc.split('.')[0][1:])
                except:  # noqa
                    bitrate = None
                if quality not in q_q_mapping:
                    field = 'lq'
                    logger.warning('unknown quality {}, url {}'.format(quality, url))
                else:
                    field = q_q_mapping[quality]
                q_media_mapping[field] = Media(url, format=format, bitrate=bitrate)
        return q_media_mapping


class AlbumSchema(Schema):
    """专辑详情 Schema

    >>> import json
    >>> with open('data/fixtures/xiami/album.json') as f:
    ...     data = json.load(f)
    ...     schema = AlbumSchema(strict=True)
    ...     album, _ = schema.load(data)
    >>> album.identifier
    2100387382
    """
    class Meta:
        unknown = EXCLUDE

    identifier = fields.Int(data_key='albumId', required=True)
    name = fields.Str(data_key='albumName', required=True)
    cover = fields.Str(data_key='albumLogo', required=True)

    songs = fields.List(fields.Nested('NestedSongSchema'))
    artists = fields.List(fields.Nested(ArtistSchema), data_key='artists')
    desc = fields.Str(data_key='description')

    @post_load
    def create_model(self, data, **kwargs):
        return XAlbumModel(**data)


class MvSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    identifier = fields.Str(requried=True, data_key='mvId')
    name = fields.Str(requried=True, data_key='title')
    cover = fields.Str(requried=True, data_key='mvCover')
    media = fields.Str(requried=True, data_key='mp4Url')

    @post_load
    def create_model(self, data, **kwargs):
        return XMvModel(**data)


class SongSchema(Schema):
    """歌曲详情 Schema

    >>> import json
    >>> with open('data/fixtures/xiami/song.json') as f:
    ...     data = json.load(f)
    ...     schema = SongSchema(strict=True)
    ...     song, _ = schema.load(data)
    >>> song.url
    ''
    """
    class Meta:
        unknown = EXCLUDE

    identifier = fields.Int(data_key='songId', required=True)
    mvid = fields.Str(requried=True, data_key='mvId')
    title = fields.Str(data_key='songName', required=True)
    # FIXME: 有的歌曲没有 length 字段
    duration = fields.Str(data_key='length', missing='0')

    url = fields.Str(data_key='listenFile', missing='')
    files = fields.List(
        fields.Nested(ListenFileSchema), data_key='listenFiles', missing=[])

    # XXX: 这里暂时用 singerVOs 来表示歌曲的 artist，即使虾米接口中
    # 也会包含歌曲 artistVOs 信息
    artists = fields.List(
            fields.Nested(ArtistSchema), data_key='singerVOs', required=True)

    album_id = fields.Int(data_key='albumId', required=True)
    album_name = fields.Str(data_key='albumName', required=True)
    album_cover = fields.Str(data_key='albumLogo', required=True)

    @post_load
    def create_model(self, data, **kwargs):
        album = XAlbumModel(identifier=data['album_id'],
                            name=data['album_name'],
                            cover=data['album_cover'])
        files = data['files']
        if files:
            url = files[0]['url']
        else:
            url = ''
        q_media_mapping = ListenFileSchema.to_q_media_mapping(files)
        expire = int(time.time()) + 60 * 60
        song = XSongModel(identifier=data['identifier'],
                          mvid=data['mvid'],
                          title=data['title'],
                          url=url,
                          duration=int(data['duration']),
                          album=album,
                          artists=data['artists'],
                          q_media_mapping=q_media_mapping,
                          expired_at=expire,)
        return song


class NestedSongSchema(SongSchema):
    """搜索结果中歌曲 Schema、专辑/歌手详情中歌曲 Schema

    通过 search 得到的 Song 的结构和通过 song_detail 获取的 Song 的结构不一样

    search 接口得到的 Song 没有 listenFile 字段，但是可能会有 listenFiles 字段，
    有的话，取 listenFiles 中最高质量的播放链接作为音乐的 url。
    """
    class Meta:
        unknown = EXCLUDE

    @post_load
    def create_model(self, data, **kwargs):
        song = super().create_model(data)
        files = data['files']
        if files:
            song.url = files[0]['url']
        return song


class PlaylistSchema(Schema):
    """歌单 Schema

    >>> import json
    >>> with open('data/fixtures/xiami/playlist.json') as f:
    ...     data = json.load(f)
    ...     schema = PlaylistSchema(strict=True)
    ...     playlist, _ = schema.load(data)
    >>> len(playlist.songs)
    100
    """
    class Meta:
        unknown = EXCLUDE

    identifier = fields.Str(data_key='listId', required=True)
    uid = fields.Int(data_key='userId', required=True)
    name = fields.Str(data_key='collectName', required=True)
    cover = fields.Str(data_key='collectLogo', required=True)
    songs = fields.List(fields.Nested(NestedSongSchema), missing=None)
    desc = fields.Str(data_key='description', missing=None)

    @post_load
    def create_model(self, data, **kwargs):
        return XPlaylistModel(**data)


class SearchSchema(Schema):
    """搜索结果 Schema"""
    class Meta:
        unknown = EXCLUDE

    songs = fields.List(fields.Nested(NestedSongSchema))
    albums = fields.List(fields.Nested(AlbumSchema))
    artists = fields.List(fields.Nested(ArtistSchema))
    playlists = fields.List(fields.Nested(PlaylistSchema), data_key='collects')
    @post_load
    def create_model(self, data, **kwargs):
        return XSearchModel(**data)


class UserSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    identifier = fields.Int(data_key='userId')
    name = fields.Str(data_key='nickName')
    access_token = fields.Str(data_key='accessToken')

    @post_load
    def create_model(self, data, **kwargs):
        return XUserModel(**data)


from .models import (
    XAlbumModel,
    XArtistModel,
    XMvModel,
    XPlaylistModel,
    XSongModel,
    XSearchModel,
    XUserModel,
)  # noqa
