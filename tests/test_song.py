from unittest.mock import patch

from fuo_xiami.api import API
from fuo_xiami.models import XSongModel


def test_song_not_exists():
    with patch.object(API, 'song_detail', return_value=None) as mock_song_detail:
        song = XSongModel(identifier=1)
        assert song.list_quality() == []
        for field in song.meta.fields:
            value = getattr(song, field)
            if field == 'identifier':
                assert value == 1
            elif field in ('lyric'):
                pass
            else:
                assert getattr(song, field) is None
