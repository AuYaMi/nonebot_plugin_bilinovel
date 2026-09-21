from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, Message, GroupMessageEvent, PrivateMessageEvent
import asyncio
from pathlib import Path
from .download import download_volume
from .search import search_book
from .config import plugin_config

# 全局信号量：同一时刻只允许1个下载任务
GLOBAL_SEM = asyncio.Semaphore(1)


async def send_notice(bot: Bot, target_id: int, is_group: bool, text: str):
    """统一发送群聊/私聊消息工具函数"""
    if is_group:
        await bot.send_group_msg(group_id=target_id, message=text)
    else:
        await bot.send_private_msg(user_id=target_id, message=text)


down = on_command("down", priority=plugin_config.bilinovel_down_priority, block=True)


@down.handle()
async def down_handler(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    raw_text = arg.extract_plain_text().strip()
    if not raw_text:
        await down.finish("用法：\n/down 书籍ID 卷号\n例：/down 123 1\n/down 123 1 epub")

    parts = raw_text.split()
    if len(parts) < 2:
        await down.finish("参数不足！格式：/down 书籍ID 卷号")

    try:
        book_id = int(parts[0])
        vol = int(parts[1])
        run_mode = parts[2] if len(parts) >= 3 else "txt"
    except ValueError:
        await down.finish("❌书籍ID、卷号必须为数字")

    await down.send(f"📥开始下载 {book_id} 第{vol}卷，后台执行...")

    # 提前提取信息，后台任务不再依赖event对象
    if isinstance(event, GroupMessageEvent):
        is_group = True
        target_id = event.group_id
    elif isinstance(event, PrivateMessageEvent):
        is_group = False
        target_id = event.user_id
    else:
        await down.finish("不支持该场景")
        return

    async def background_task(bot: Bot, tid: int, is_grp: bool, bid: int, v: int, mode: str):
        # 检测锁是否被占用，发送排队提示
        if GLOBAL_SEM.locked():
            await send_notice(bot, tid, is_grp, "⏳当前已有下载任务正在运行，你的任务进入排队队列，请耐心等待...")

        async with GLOBAL_SEM:
            try:
                file_list = await download_volume(
                    book_id=bid,
                    vol_number=v,
                    mode=mode
                )
                for file_path in file_list:
                    filename = Path(file_path).name
                    if is_grp:
                        await bot.call_api(
                            "upload_group_file",
                            group_id=tid,
                            file=file_path,
                            name=filename
                        )
                    else:
                        await bot.call_api(
                            "upload_private_file",
                            user_id=tid,
                            file=file_path,
                            name=filename
                        )
                await send_notice(bot, tid, is_grp, "✅下载任务执行完成，文件已上传至文件面板")

            except Exception as e:
                import traceback
                traceback.print_exc()
                await send_notice(bot, tid, is_grp, f"❌下载失败：{str(e)}")

    asyncio.create_task(background_task(bot, target_id, is_group, book_id, vol, run_mode))


sear = on_command("sear", priority=plugin_config.bilinovel_sear_priority, block=True)


@sear.handle()
async def sear_handler(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    keyword = arg.extract_plain_text().strip()
    if not keyword:
        await sear.finish("🔍搜索用法：\n/sear 小说名字\n示例：/sear 刀剑神域")
    try:
        result = await search_book(keyword)
        reply_lines = ["————搜索结果————"]
        if isinstance(result, str):
            reply_lines.append(result)
        elif len(result) == 2:
            name, bid = result
            reply_lines.append(f"1. {name}｜ID:{bid}")
        elif len(result) == 3:
            names, urls, ids = result
            for idx, (name, bid) in enumerate(zip(names, ids), start=1):
                reply_lines.append(f"{idx}. {name}｜ID:{bid}")
        reply_msg = "\n".join(reply_lines)
        await sear.send(reply_msg)
        return
    except Exception as e:
        import traceback
        traceback.print_exc()
        await sear.send(f"❌搜索出错：{str(e)}")
