# nonebot-plugin-bilinovel

> NoneBot2 哔哩轻小说爬虫插件，搜索小说并下载生成 EPUB 电子书

##  安装

### pip 安装
```bash
pip install nonebot-plugin-bilinovel
```

### 安装 Playwright 浏览器内核

```bash
playwright install chromium
```

## 🎯 使用命令

### 参数标记约定

- `< >` 必填参数，不可省略
- `[ ]` 可选参数，可以省略

| 指令 | 语法 | 说明 |
| --- | --- | --- |
| `/sear` | `/sear <小说名称>` | 搜索哔哩轻小说，返回书本 id |
| `/down` | `/down <书本id> <卷号> [下载格式]` | 下载小说并生成 EPUB 或 txt |

> 搜索示例：`/sear 关于我转生变成史莱姆这档事`
>           `/sear 游戏人生`
>
> 下载示例：`/down 9 1 epub` 即下载书籍 id 为 9 的第一卷，导出格式为 epub
>
> [下载格式不填默认txt]

## 📸 运行效果

### 搜索小说

发送 `/sear 魔法禁书` 搜索小说：

![搜索效果](assets/sear.png)

### 下载 TXT

发送 `/down 4187 1` 下载第一卷 TXT 格式：

![下载TXT](assets/down_txt.png)

### 下载 EPUB

发送 `/down 4187 1 epub` 下载第一卷 EPUB 格式：

![下载EPUB](assets/down_epub.png)

## ⚙️ .env自定义参数配置


可调整参数列表：

```
# Playwright浏览器无头开关，True：无头 /False：有头
BROWSER_HEADLESS = True
# 章节并发数，并发多容易限流
WORKER_COUNT = 2
```


## ⚠️ 使用须知

1. 本插件仅用于个人学习研究。
2. 请勿高频、大规模爬取网站，避免给目标站点造成压力。
3. 下载内容版权归原作者与平台所有。

## 📁 文件输出

生成的 EPUB 文件将会保存至插件运行目录下。

## 📝 更新日志

### v0.1.4

- 修复 EPUB 模式下 Cloudflare 广告弹窗遮挡插图截图的问题
- 修复下载小说时因网络中断导致下载失败的问题

### v0.1.3

- 无头模式改用本地 Chrome 渲染，修复 EPUB 模式下插画检测不到的问题
- 修复临时文件路径，避免目录不存在导致崩溃
- 添加下载完整性校验：缓存文件章节数不匹配时自动重新下载
- TXT 下载使用临时文件，下载完成后重命名，防止中断留下半成品

### v0.1.2

- 添加项目主页链接，修复 NoneBot 商店发布检查问题
- README 添加运行效果截图