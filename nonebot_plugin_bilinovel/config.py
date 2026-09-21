import asyncio
import random
from pathlib import Path

from nonebot import get_driver, get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    """哔哩轻小说插件配置项"""

    bilinovel_worker_count: int = 2
    bilinovel_sear_priority: int = 4
    bilinovel_down_priority: int = 5


plugin_config = get_plugin_config(Config)


driver = get_driver()

ROOT = Path(__file__).parent.parent
OUTPUT_FOLDER = ROOT / "shared_output"
OUTPUT_FOLDER.mkdir(exist_ok=True)
BASE_URL = "https://w.linovelib.com"

task_queue: asyncio.Queue = asyncio.Queue(maxsize=30)
END_SENTINEL = None


def get_worker_count() -> int:
    return plugin_config.bilinovel_worker_count


def get_temp_json_path() -> Path:
    return OUTPUT_FOLDER / "chap_temp.json"


@driver.on_startup
def print_config_info():
    w = get_worker_count()
    t = get_temp_json_path()
    print("✅ 插件配置加载完成")
    print(f"  BILINOVEL_WORKER_COUNT = {w}")
    print(f"  TEMP_JSON_PATH         = {t}")


USER_AGENTS = [
    "Mozilla/5.0 (Linux; U; Android 4.0.2; en-us; Galaxy Nexus Build/ICL53F) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30",
    "Mozilla/5.0 (Linux; U; Android 2.3.6; en-us; Nexus S Build/GRK39F) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1",
    "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Pixel 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 4.3; Nexus 7 Build/JSS15Q) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/91.0.4472.124 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 13_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/91.0.4472.124 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Android 4.4; Mobile; rv:70.0) Gecko/70.0 Firefox/70.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 8_3 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) FxiOS/1.0 Mobile/12F69 Safari/600.1.4",
    "Mozilla/5.0 (iPad; CPU iPhone OS 8_3 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) FxiOS/1.0 Mobile/12F69 Safari/600.1.4",
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 12_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.1.1 EdgiOS/44.5.0.10 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 12_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 EdgiOS/44.5.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 8.1.0; Pixel Build/OPM4.171019.021.D1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.109 Mobile Safari/537.36 EdgA/42.0.0.2057",
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 7 Build/MOB30X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.109 Safari/537.36 EdgA/42.0.0.2057",
    "Opera/12.02 (Android 4.1; Linux; Opera Mobi/ADR-1111101157; U; en-US) Presto/2.9.201 Version/12.02",
    "Opera/9.80 (iPhone; Opera Mini/8.0.0/34.2336; U; en) Presto/2.8.119 Version/11.10",
    "Mozilla/5.0 (iPad; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; U; Android 8.1.0; en-US; Nexus 6P Build/OPM7.181205.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/57.0.2987.108 UCBrowser/12.11.1.1197 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 12_1 like Mac OS X; zh-CN) AppleWebKit/537.51.1 (KHTML, like Gecko) Mobile/16B92 UCBrowser/12.1.7.1109 Mobile AliApp(TUnionSDK/0.1.20.3)",
]

COOKIE_STR = "_ga=GA1.2.373713668.1646927652; _gid=GA1.2.1447053390.1651231171; Hm_lpvt_d29ecd95ff28d58324c09b9dc0bee919=1651231349; Hm_lvt_d29ecd95ff28d58324c09b9dc0bee919=1649823562,1651231165; jieqiUserInfo=jieqiUserId%3D627182%2CjieqiUserUname%3Dfangxx3863%2CjieqiUserName%3Dfangxx3863%2CjieqiUserGroup%3D3%2CjieqiUserGroupName%3D%E6%99%AE%E9%80%9A%E4%BC%9A%E5%91%98%2CjieqiUserVip%3D0%2CjieqiUserHonorId%3D1%2CjieqiUserHonor%3D%E5%A4%A9%E7%84%B6%2CjieqiUserToken%3D8ea5ef793d94938673124b15cb3a7102%2CjieqiCodeLogin%3D0%2CjieqiCodePost%3D0%2CjieqiUserPassword%3D5c82b131f01843ca05e751717d74a992%2CjieqiUserLogin%3D1651231169; jieqiVisitId=article_articleviews%3D2939; jieqiVisitInfo=jieqiUserLogin%3D1651231169%2CjieqiUserId%3D627182; night=0; PHPSESSID=bsdrsrdj916v5etol006ji2odl"


def get_random_headers() -> dict:
    """每次调用生成一份全新随机UA的请求头"""
    random_ua = random.choice(USER_AGENTS)
    headers = {
        "Cookie": COOKIE_STR,
        "Referer": BASE_URL + "/",
        "User-Agent": random_ua,
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    return headers