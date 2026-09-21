import aiohttp
from lxml import etree
from nonebot.log import logger
from nonebot_plugin_htmlrender import get_default_application
from .config import *
     
async def search_book(keyword):
    from playwright.async_api import expect
    playwright = get_default_application().extensions.playwright
    async with playwright.page(viewport={"width":1280,"height":720}) as page:
        # ==========新增：仅拦截图片，其他资源全部放行==========
        async def block_images(route, request):
            if request.resource_type == "image":
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", block_images)

        url = 'https://www.bilinovel.com/search.html'
        await page.goto(url, timeout=30000)
        await page.wait_for_load_state("networkidle")
        search_input = page.locator("id=searchkey")
        await search_input.wait_for(timeout=15000)
        await search_input.fill(keyword)
        await search_input.press("Enter")
        await expect(page.locator("id=a_addbookcase").or_(page.locator('//b[@class="hot"]'))).to_be_visible(timeout=15000)
        if await page.locator("#a_addbookcase").is_visible():
            book_url = await page.locator("//div[@class='book-detail-btn']/ul/li[1]/a").get_attribute("href")
            book_name = await page.locator("//div/h1").inner_text()
            novel_id = book_url.split("/novel/")[1].split("/")[0]
            return book_name,novel_id
        else:
            h3_text = await page.locator('//h3').text_content()
            book_urls = await page.locator("//li/a").evaluate_all("items=>items.map(e=>e.href)")
            book_names = await page.locator("//li/a/div/img").evaluate_all("items=>items.map(e=>e.alt)")
            ids = []
            if not book_names:
                logger.warning(h3_text)
                return h3_text
            for book_url in book_urls:
                novel_id = book_url.split("/novel/")[1].split("/")[0].split(".")[0]
                ids.append(novel_id)
            return book_names,book_urls,ids




        

async def getbook_html(book_id: int, session: aiohttp.ClientSession):

    url = f'https://www.bilinovel.com/novel/{book_id}/catalog'
    HEADERS = get_random_headers()
   
    async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        resp_text = await resp.text(encoding="utf-8")
        # logger.info(resp_text)
        e = etree.HTML(resp_text)
        book_nums = e.xpath('//div/ul/li[@class="chapter-bar chapter-li"]/a/h3/text()')
        book_htmls = e.xpath('//div/ul/li[@class="chapter-bar chapter-li"]/a/@href')
        if not book_nums:
            logger.error('该id不存在')
            return [],[]
        # logger.info(book_htmls)
        # logger.info(book_nums)
        return book_nums,book_htmls
   


async def main():
    keyword = "游戏人生"
    print(f"正在搜索：{keyword}")
    res = await search_book(keyword)
    print("====搜索返回结果====")
    print(f"返回类型: {type(res)}")
    print(f"内容: {res}")

if __name__ == "__main__":
    asyncio.run(main())