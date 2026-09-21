import aiohttp
import asyncio
import random
import json
import base64
import re
from lxml import etree
from .search import getbook_html
from . import config
from nonebot.log import logger
from nonebot_plugin_htmlrender import get_default_application
from urllib.parse import urljoin
from ebooklib import epub


async def get_url(session, url):
    async with session.get(url) as resp:
        return await resp.text(encoding='utf-8')


# 移除广告弹窗，避免遮挡插图截图
async def remove_ad_popup(page):
    """移除所有可能的广告弹窗和覆盖层"""
    await page.evaluate("""() => {
        // 移除 fc-monetization 弹窗（哔哩轻小说的广告解锁弹窗）
        document.querySelectorAll('div.fc-monetization-dialog, div.fc-monetization-dialog.fc-dialog').forEach(e => e.remove());
        // 移除 Cloudflare 相关 iframe
        document.querySelectorAll('iframe[src*="challenges"], iframe[src*="turnstile"], iframe[src*="cloudflare"]').forEach(e => e.remove());
        // 移除其他常见的弹窗/覆盖层
        document.querySelectorAll('[class*="modal"], [class*="overlay"], [class*="popup"], [id*="challenge"], [id*="turnstile"]').forEach(e => e.remove());
        // 移除可能的背景遮罩
        document.querySelectorAll('div[style*="position: fixed"], div[style*="position:fixed"]').forEach(e => {
            if (e.style.zIndex > 1000) e.remove();
        });
    }""")


async def get_filtered_text(page, url, load_image: bool = False):
    await page.goto(
        url,
        timeout=30000,
        wait_until="domcontentloaded"
    )
    await page.wait_for_timeout(3000)
    page_html = await page.content()
    if "Sorry, you have been blocked" in page_html:
        logger.error(" 当前IP触发Cloudflare封禁！任务终止")
        raise Exception("CLOUDFLARE_BLOCKED")
    if "内容加载失败" in page_html or "请刷新或更换浏览器" in page_html:
        logger.warning(" 页面触发反爬检测，内容被替换为假文本")
        raise Exception("ANTI_BOT_DETECTED")
    await page.wait_for_selector('//div[@class="TextContent"]', timeout=25000, state="visible")
    await remove_ad_popup(page)
    # 只有EPUB插图模式才执行滚动+延时
    if load_image:
        await page.evaluate("window.scrollTo({top: document.body.scrollHeight, behavior:'instant'})")
        await page.wait_for_timeout(1000)
    # ========== 正文提取，共用同一段JS，无重复 ==========
    res = await page.locator('div[class="TextContent"]').evaluate(r"""
    root => {
        const raw = root.innerText.trim();
        const hasText = raw !== "";
        if(hasText === false){
            return {hasText:false, content:"", img_list:[]};
        }
        const children = Array.from(root.querySelectorAll(':scope > *'));
        const visibleNodes = children.filter(el=>{
            const rect = el.getBoundingClientRect();
            if(rect.width <= 0 || rect.height <= 0) return false;
            const style = window.getComputedStyle(el);
            if(style.display === 'none') return false;
            return true;
        })
        let textBuilder = [];
        let imgSrcList = [];
        for(const elem of visibleNodes){
            if(elem.tagName === 'P'){
                const paraText = elem.innerText.trim();
                if(paraText) textBuilder.push(paraText);
            }
            else if(elem.tagName === 'IMG'){
                if(elem.closest('center ruby')) continue;
                const realSrc = elem.dataset.src || elem.src;
                if(realSrc){
                    textBuilder.push(`[插图:${imgSrcList.length}]`);
                    imgSrcList.push(realSrc);
                }
            }
        }
        const cleanText = textBuilder.join("\n\n");
        return {
            hasText:true,
            content:cleanText,
            img_list: imgSrcList
        };
    }
    """)
    logger.info(f"页面正文检测结果 hasText: {res['hasText']}, 插图数量:{len(res['img_list'])}")
    return {
        "hasText": res["hasText"],
        "content": res["content"],
        "img_url_list": res["img_list"]
    }


# ---------------- TXT抓取分支 ----------------
async def crawl_chapter_txt(page, first_page_url):
    base_url, ext = first_page_url.rsplit(".", 1)
    full_text = ""
    page_index = 2
    MAX_SAFE_PAGE = 25
    IMG_NOTICE_MAX_LEN = 60
    ban_keywords = ["插图"]
    res = await get_filtered_text(page, first_page_url, load_image=False)
    if res["hasText"]:
        full_text += res["content"] + "\n\n\n"
    while page_index <= MAX_SAFE_PAGE:
        current_url = f"{base_url}_{page_index}.{ext}"
        try:
            res = await get_filtered_text(page, current_url, load_image=False)
        except Exception:
            break
        if not res["hasText"]:
            break
        h1_loc = page.locator('//div[@id="mlfy_main_text"]/h1')
        if await h1_loc.count() > 0:
            h1_text = await h1_loc.inner_text()
            if "插图(3/1)" in h1_text or "插图（3/1）" in h1_text:
                logger.info("✅txt模式命中插图分页h1标题，结束翻页")
                break
        page_content = res["content"].strip()
        has_img_tag = any(word in page_content for word in ban_keywords)
        is_short_text = len(page_content) < IMG_NOTICE_MAX_LEN
        if has_img_tag and is_short_text:
            logger.info("✅txt模式命中短插图提示文本，结束翻页")
            break
        full_text += page_content + "\n\n\n"
        page_index += 1
    return full_text


# ---------------- EPUB抓取分支----------------
async def crawl_chapter_epub(page, first_page_url, load_image=True):
    base_url, ext = first_page_url.rsplit(".", 1)
    full_text = ""
    all_img_base64 = []
    page_index = 2
    MAX_SAFE_PAGE = 25
    res = await get_filtered_text(page, first_page_url, load_image=True)
    if res["hasText"]:
        full_text += res["content"] + "\n\n\n"
        img_locators = page.locator('//div[@class="TextContent"]/img[not(ancestor::center/ruby)]')
        img_count = await img_locators.count()
        for i in range(img_count):
            loc = img_locators.nth(i)
            try:
                await loc.scroll_into_view_if_needed(timeout=8000)
                await page.wait_for_timeout(2000)
                # 截图前移除广告弹窗（可能在滚动后才出现）
                await remove_ad_popup(page)
                pic_bytes = await loc.screenshot()
                b64_str = base64.b64encode(pic_bytes).decode("utf‑8")
                all_img_base64.append(b64_str)
            except Exception as e:
                logger.warning(f"截图插图{i}失败:{e}")
                all_img_base64.append(None)
    while page_index <= MAX_SAFE_PAGE:
        current_url = f"{base_url}_{page_index}.{ext}"
        try:
            res = await get_filtered_text(page, current_url)
        except Exception:
            break
        if not res["hasText"]:
            break
        h1_loc = page.locator('//div[@id="mlfy_main_text"]/h1')
        if await h1_loc.count() > 0:
            h1_text = await h1_loc.inner_text()
            if "插图(3/1)" in h1_text or "插图（3/1）" in h1_text:
                logger.info("✅h1标题命中插图分页，结束翻页")
                break
        full_text += res["content"] + "\n\n\n"
        img_locators = page.locator('//div[@class="TextContent"]/img[not(ancestor::center/ruby)]')
        img_count = await img_locators.count()
        for i in range(img_count):
            loc = img_locators.nth(i)
            try:
                await loc.scroll_into_view_if_needed(timeout=8000)
                await page.wait_for_timeout(600)
                # 截图前移除广告弹窗
                await remove_ad_popup(page)
                pic_bytes = await loc.screenshot()
                b64_str = base64.b64encode(pic_bytes).decode("utf‑8")
                all_img_base64.append(b64_str)
            except Exception as e:
                logger.warning(f"分页截图插图{i}失败:{e}")
                all_img_base64.append(None)
        page_index += 1
    return {"content": full_text, "img_base64_list": all_img_base64}


async def download_one_chapter_txt(page, chap_url, retry_times=3):
    for attempt in range(retry_times):
        try:
            return await crawl_chapter_txt(page, chap_url)
        except Exception as e:
            logger.warning(f"章节尝试 {attempt+1}/{retry_times} 失败: {e}")
            await asyncio.sleep(2)
    raise Exception("多次重试下载失败")


async def download_one_chapter_epub(page, chap_url, retry_times=3):
    for attempt in range(retry_times):
        try:
            return await crawl_chapter_epub(page, chap_url)
        except Exception as e:
            logger.warning(f"章节尝试 {attempt+1}/{retry_times} 失败: {e}")
            await asyncio.sleep(2)
    raise Exception("多次重试下载失败")


async def volume_get(session, url):
    response = await get_url(session, url)
    e = etree.HTML(response)
    vol_name = e.xpath('//div/ul[@class="module-content"]/li/a/span/text()')
    vol_url = e.xpath('//div/ul[@class="module-content"]/li/a/@href')
    return vol_name, vol_url


# ---------------- Producer（两个模式共用） ----------------
async def producer(book_id: int, vol_number: int, session: aiohttp.ClientSession):
    base_domain = "https://www.bilinovel.com"
    vol_name_list, book_htmls = await getbook_html(book_id, session)
    if not vol_name_list or not book_htmls:
        logger.error("未获取到任何分卷列表")
        await config.task_queue.put(config.END_SENTINEL)
        return
    vol_index = vol_number - 1
    if vol_index < 0 or vol_index >= len(book_htmls):
        logger.error(f"卷号 {vol_number} 越界")
        await config.task_queue.put(config.END_SENTINEL)
        return
    target_volume_rel_url = book_htmls[vol_index]
    target_volume_full_url = urljoin(base_domain, target_volume_rel_url)
    chap_name_list, chap_rel_list = await volume_get(session, target_volume_full_url)
    if not chap_name_list or not chap_rel_list:
        logger.error("未解析出章节")
        await config.task_queue.put(config.END_SENTINEL)
        return
    for idx, (chap_title, chap_href) in enumerate(zip(chap_name_list, chap_rel_list)):
        full_url = urljoin(base_domain, chap_href)
        await config.task_queue.put((idx, chap_title, full_url))
        logger.info(f"加入队列: {chap_title}")
    # 发送哨兵
    worker_num = config.get_worker_count()
    for _ in range(worker_num):
        await config.task_queue.put(config.END_SENTINEL)
    logger.info("✅全部章节任务获取完成")


# ---------------- Worker‑TXT版：直接写入txt ----------------
async def worker_txt(worker_id: int, save_path: str, file_lock: asyncio.Lock):
    init_delay = worker_id * 5.0
    logger.info(f"工人{worker_id}，等待 {init_delay}s 后开始工作")
    await asyncio.sleep(init_delay)
    playwright = get_default_application().extensions.playwright
    async with playwright.browser() as browser:
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        while True:
            job = await config.task_queue.get()
            if job is config.END_SENTINEL:
                break
            _, chap_title, chap_full_url = job
            logger.info(f"[工人{worker_id}]开始下载：{chap_title}")
            page = await context.new_page()
            await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico}", lambda r: r.abort())
            await page.route("**/*.css", lambda r: r.abort())
            try:
                chapter_text = await download_one_chapter_txt(page, chap_full_url)
                if chapter_text.strip():
                    async with file_lock:
                        with open(save_path, "a", encoding="utf-8") as f:
                            f.write(f"\n---------- {chap_title} ----------\n{chapter_text}")
                            f.flush()
                    logger.info(f"{chap_title} → 完成")
                else:
                    logger.info(f"{chap_title} → 插图占位，跳过写入")
            except Exception as err:
                logger.error(f"章节 {chap_title} 下载失败跳过：{err}")
            finally:
                await page.close()
            await asyncio.sleep(random.uniform(2.0, 3.0))
        await context.close()
    logger.info(f"✅工人{worker_id}退出")


# ---------------- Worker‑EPUB版：写入临时json ----------------
async def worker_epub(worker_id: int, file_lock: asyncio.Lock):
    init_delay = worker_id * 4.0
    logger.info(f"工人{worker_id}，等待 {init_delay}s 后启动")
    await asyncio.sleep(init_delay)
    playwright = get_default_application().extensions.playwright
    async with playwright.browser() as browser:
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        temp_json_path = config.get_temp_json_path()
        while True:
            job = await config.task_queue.get()
            if job is config.END_SENTINEL:
                break
            chap_idx, chap_title, chap_full_url = job
            logger.info(f"[工人{worker_id}]开始下载：{chap_title}")
            page = await context.new_page()
            await page.route("**/*.css", lambda r: r.abort())
            try:
                chapter_result = await download_one_chapter_epub(page, chap_full_url)
                async with file_lock:
                    line = json.dumps({
                        "idx": chap_idx,
                        "title": chap_title,
                        "text": chapter_result["content"],
                        "img_base64_list": chapter_result["img_base64_list"]
                    }, ensure_ascii=False)
                    with open(temp_json_path, "a", encoding="utf‑8") as f:
                        f.write(line + "\n")
                logger.info(f"{chap_title} → 完成")
            except Exception as err:
                logger.error(f"章节 {chap_title} 下载失败跳过：{err}")
            finally:
                await page.close()
            await asyncio.sleep(random.uniform(2, 3))
        await context.close()
    logger.info(f"✅工人{worker_id}浏览器退出")


# ---------------- 导出工具函数 ----------------
def export_sorted_txt(json_path: str, out_path: str, volume_name: str):
    chapters = []
    with open(json_path, "r", encoding="utf‑8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chapters.append(json.loads(line))
    chapters.sort(key=lambda x: x["idx"])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"==================== {volume_name} ====================\n")
        for ch in chapters:
            f.write(f"\n---------- {ch['title']} ----------\n{ch['text']}")
    logger.info(f"✅排序导出完成，输出文件：{out_path}")


def build_epub_from_json(json_path: str, epub_output: str, book_title: str):
    chapters = []
    img_assets = dict()
    with open(json_path, "r", encoding="utf‑8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            chapters.append(data)
    chapters.sort(key=lambda x: x["idx"])
    # 插图错位校验
    for chap in chapters:
        text = chap["text"]
        img_arr = chap["img_base64_list"]
        mark_list = re.findall(r'\[插图:(\d+)\]', text)
        if len(mark_list) == 0:
            continue
        max_index = max(int(x) for x in mark_list)
        if max_index >= len(img_arr):
            logger.warning(f"⚠️插图错位警告【{chap['title']}】文本标记最大下标:{max_index},截图图片总数:{len(img_arr)}")
    book = epub.EpubBook()
    book.set_identifier("novel_book")
    book.set_title(book_title)
    book.set_language("zh‑CN")
    epub_chapter_items = []
    for chap in chapters:
        chap_title = chap["title"]
        raw_text = chap["text"]
        img_b64_arr = chap["img_base64_list"]
        for img_idx, b64_str in enumerate(img_b64_arr):
            placeholder = f"[插图:{img_idx}]"
            if placeholder not in raw_text:
                continue
            if b64_str is None:
                raw_text = raw_text.replace(placeholder, "\n【插图加载失败】\n")
                continue
            asset_id = f"img_{chap['idx']}_{img_idx}"
            if asset_id not in img_assets:
                img_bytes = base64.b64decode(b64_str)
                image_item = epub.EpubImage(
                    uid=asset_id,
                    file_name=f"images/{asset_id}.jpg",
                    media_type="image/jpeg",
                    content=img_bytes
                )
                book.add_item(image_item)
                img_assets[asset_id] = True
            img_html_tag = f'<div style="text-align:center"><img src="images/{asset_id}.jpg" alt="插图{img_idx}" /></div>'
            raw_text = raw_text.replace(placeholder, img_html_tag)
        html_body = raw_text.replace("\n\n", "<br/><br/>")
        c = epub.EpubHtml(
            title=chap_title,
            file_name=f"chap_{chap['idx']}.xhtml",
            lang="zh‑CN",
            content=f"<h2>{chap_title}</h2><div>{html_body}</div>"
        )
        book.add_item(c)
        epub_chapter_items.append(c)
    book.toc = epub_chapter_items
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + epub_chapter_items
    epub.write_epub(epub_output, book, {})
    logger.info(f"🎉 EPUB打包完成！输出文件: {epub_output}")


# ---------------- 对外统一入口函数（模式选择） ----------------
from pathlib import Path
import asyncio


async def download_volume(book_id: int,
                          vol_number: int,
                          out_txt_path: str = "",
                          mode: str = "txt"):
    """
    :param book_id: 书籍id
    :param vol_number: 卷号
    :param out_txt_path: 备用输出路径（当前未使用）
    :param mode: "txt" =仅生成文本，上传txt; "epub"=生成txt+epub，仅上传epub
    :return: list[str] 文件路径列表
    """
    async with aiohttp.ClientSession() as session:
        vol_name_list, book_htmls = await getbook_html(book_id, session)
        vol_index = vol_number - 1
        target_volume_name = vol_name_list[vol_index]

    txt_file = config.OUTPUT_FOLDER / f"{target_volume_name}.txt"
    epub_file = config.OUTPUT_FOLDER / f"{target_volume_name}.epub"
    temp_json_path = config.get_temp_json_path()

    result_files = []
    if mode == "txt":
        # txt缓存：只要txt存在就命中
        if txt_file.exists():
            logger.info(f"✅缓存命中！已检测到文件，跳过下载：{txt_file}")
            result_files.append(str(txt_file))
            return result_files
    elif mode == "epub":
        # epub缓存：只要epub存在就算命中，忽略txt
        if epub_file.exists():
            logger.info(f"✅缓存命中！检测到epub，跳过下载，直接上传epub")
            result_files.append(str(epub_file))
            return result_files

    # ============ 缓存未命中，开始爬虫下载 ============
    file_lock = asyncio.Lock()
    worker_tasks = []
    worker_num = config.get_worker_count()

    if mode == "txt":
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write(f"==================== {target_volume_name} ====================\n")
        for wid in range(worker_num):
            t = asyncio.create_task(worker_txt(wid, str(txt_file), file_lock))
            worker_tasks.append(t)
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(
                producer(book_id, vol_number, session),
                *worker_tasks
            )
        logger.info(f"✅【TXT模式】卷 {vol_number}【{target_volume_name}】下载完毕")
        result_files.append(str(txt_file))

    elif mode == "epub":
        with open(temp_json_path, "w", encoding="utf‑8") as f:
            pass
        for wid in range(worker_num):
            t = asyncio.create_task(worker_epub(wid, file_lock))
            worker_tasks.append(t)
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(
                producer(book_id, vol_number, session),
                *worker_tasks
            )
        export_sorted_txt(str(temp_json_path), str(txt_file), target_volume_name)
        epub_name = str(epub_file)
        build_epub_from_json(str(temp_json_path), epub_name, target_volume_name)
        logger.info(f"✅【EPUB模式】全部任务结束！生成txt + epub")
        result_files.append(epub_name)
    else:
        raise ValueError('mode只能为 "txt" 或 "epub"')
    logger.info(result_files)
    return result_files


# if __name__ == "__main__":
#     import asyncio
#     async def test():
#         # 修改这里为你要测试的书籍ID、卷号
#         await download_volume(
#             book_id=9,
#             vol_number=4,
#             mode="epub"
#         )
#     asyncio.run(test())
