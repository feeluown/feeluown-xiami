# feeluown 虾米音乐插件

[![Build Status](https://travis-ci.com/feeluown/feeluown-xiami.svg?branch=master)](https://travis-ci.com/feeluown/feeluown-xiami)
[![PyPI](https://img.shields.io/pypi/v/fuo_xiami.svg)](https://pypi.python.org/pypi/fuo-xiami)
[![Coverage Status](https://coveralls.io/repos/github/feeluown/feeluown-xiami/badge.svg?branch=master)](https://coveralls.io/github/feeluown/feeluown-xiami?branch=master)

## 安装

```sh
pip3 install fuo-xiami
```

## 开发

注意：master 分支代码需要配合 FeelUOwn master 分支代码才可以使用。

修改代码之后，在本地运行 `pytest`，确保能通过单元测试。

## changelog

### 0.2.1 (2019-12-26)(注：当前歌单列表接口不可用)

- 修复“登录”会导致程序 crash 的 bug，见 issue #5

### 0.2 (2019-11-27)(注：当前歌单列表接口不可用)

- 使用 marshmallow>=3.0
- 加入 Makefile 方便运行测试
- 接入 travis 持续集成

### 0.1.3 (2019-10-28)(注：当前歌单列表接口不可用)

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
