# feeluown 虾米音乐插件

## 安装

```sh
pip3 install fuo-xiami
```

## 开发

注意：master 分支代码需要配合 FeelUOwn master 分支代码才可以使用。

修改代码之后，在本地运行 `pytest`，确保能通过单元测试。

## changelog

### 0.1.3 (2019-10-28)(注：当前 API 已经几乎不可用了)

- 支持获取播放列表全部的歌曲 [@cyliuu] [@cosven]
- 支持 Mv [@cyliuu] [@cosven]
- 支持搜索 artists/albums/playlists [@hjlarry]
- 适配 feeluown 3.1

### 0.1.2 (2019-03-18)
- 修复获取歌手歌曲时进入死循环

### 0.1.1 (2019-03-18)
- 当请求因为 token 失效而失败时，自动重试

### 0.1 (2019-03-18)
- 用户登录，歌曲/歌手/专辑详情获取等基本功能


[@hjlarry]: https://github.com/hjlarry
[@cyliuu]: https://github.com/cyliuu
[@cosven]: https://github.com/cosven
