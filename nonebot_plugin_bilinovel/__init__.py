from nonebot import require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_htmlrender")

from .config import Config
from . import novel

__plugin_meta__ = PluginMetadata(
    name="哔哩轻小说爬虫",
    description="搜索并下载哔哩轻小说，生成EPUB电子书",
    usage="/sear 小说名",
    type="application",
    homepage="https://github.com/AuYaMi/nonebot_plugin_bilinovel",
    supported_adapters={"~onebot.v11"},
    config=Config,
)