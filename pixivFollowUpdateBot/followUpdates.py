import requests
import json


def get_update_page(page: int, cookie: str) -> list:
    url = "https://www.pixiv.net/ajax/follow_latest/illust?p={}&mode=all&lang=zh".format(page)

    header = {
        "cookie": cookie,
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
        "referer": "https://www.pixiv.net/bookmark_new_illust.php"
    }

    response = requests.get(url, headers=header)

    page_json = json.loads(response.content.decode("utf-8"))

    r = page_json["body"]["page"]["ids"]
    r = [str(i) for i in r]

    return r


def get_follow_update(last_pid: str, cookie: str) -> list:
    first = 1
    max_page = 34

    all_illusts = []

    while True:
        illusts = get_update_page(first, cookie)

        if last_pid in illusts:
            index = illusts.index(last_pid)
            all_illusts += illusts[:index]
            break
        else:
            all_illusts += illusts

        first += 1
        if first > max_page:
            break

    return all_illusts

