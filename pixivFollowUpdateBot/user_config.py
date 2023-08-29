from . import followUpdates
import json
from pbrm.spider import cookie_verify
from pbrm.error import CookieVerifyError
from typing import List
import os


class Config:
    _last_page: str
    _cookie: str
    _path: str
    _check_interval: int
    _channel: List[int]

    def __init__(self, path: str, cookie=None, last_page=None, check_interval=None, channel=None):
        if cookie is not None:
            self._last_page = last_page
            self._cookie = cookie
            self._path = path
            self._check_interval = check_interval
            self._channel = channel
            self.save()
        else:
            self.load(path)
            self.path = path

    @classmethod
    def get(cls, path: str):
        if os.path.exists(path) and not os.path.isdir(path):
            return cls(path)
        else:
            return cls(path, "", "", 600, [])

    @property
    def last_page(self) -> str:
        return self._last_page

    @property
    def cookie(self) -> str:
        return self._cookie

    @property
    def path(self) -> str:
        return self._path

    @property
    def check_interval(self) -> int:
        return self._check_interval

    @property
    def channel(self) -> List[int]:
        return self._channel

    @last_page.setter
    def last_page(self, value: str):
        self._last_page = value
        self.save()

    @cookie.setter
    def cookie(self, value: str):
        self._cookie = value
        self.save()

    @path.setter
    def path(self, value: str):
        self._path = value

    @check_interval.setter
    def check_interval(self, value: int):
        self._check_interval = value
        self.save()

    @channel.setter
    def channel(self, value: List[int]):
        self._channel = value
        self.save()

    def channel_append(self, channel_id) -> bool:
        if channel_id in self.channel:
            return False
        else:
            self._channel.append(channel_id)
            return True

    def channel_remove(self, channel_id):
        if channel_id in self.channel:
            self._channel.remove(channel_id)
            return True
        else:
            return False

    def get_update(self):
        result = followUpdates.get_follow_update(self.last_page, self.cookie)

        if len(result) == 0:
            return []

        else:
            self.last_page = result[0]
            return result[::-1]

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "last_page": self.last_page,
                "cookie": self.cookie,
                "check_interval": self.check_interval,
                "channel": self.channel
            }, ensure_ascii=False))

    def load(self, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
            self.last_page = data["last_page"]
            self.cookie = data["cookie"]
            self.check_interval = data["check_interval"]
            self.channel = data["channel"]

    def cookie_verify(self):
        try:
            return cookie_verify(self.cookie)
        except CookieVerifyError:
            return {"userId": None, "userName": None}

