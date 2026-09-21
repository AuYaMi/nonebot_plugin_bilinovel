# nonebot-plugin-bilinovel

> NoneBot2 哔哩轻小说爬虫插件，搜索小说并下载生成 EPUB 电子书

##  安装

### pip 安装
```bash
pip install nonebot-plugin-bilinovel
```

### 浏览器内核

浏览器由 `nonebot-plugin-htmlrender` 统一管理，缺失时会在启动阶段自动安装；如需指定本地 Chrome（推荐，可修复部分站点的反爬检测），在 `.env` 中配置：

```dotenv
RENDER__PROVIDER=playwright
RENDER__PROVIDER_CONFIG__EXECUTABLE_PATH=C:/Program Files/Google/Chrome/Application/chrome.exe
```

> ⚠️ **请将 `EXECUTABLE_PATH` 替换为你本机 Chrome 的实际安装路径，否则插件无法启动！**
>
> 常见路径参考：
> - Windows: `C:/Program Files/Google/Chrome/Application/chrome.exe`
> - macOS: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
> - Linux: `/usr/bin/google-chrome`

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
# 章节并发数，并发多容易限流
BILINOVEL_WORKER_COUNT = 2

# 事件响应器优先级（数字越小优先级越高）
BILINOVEL_SEAR_PRIORITY = 4
BILINOVEL_DOWN_PRIORITY = 5
```

浏览器由 `nonebot-plugin-htmlrender` 提供的共享实例驱动（配置项前缀 `render`），按需覆盖，例如指定本地 Chrome：

```dotenv
RENDER__PROVIDER=playwright
RENDER__PROVIDER_CONFIG__EXECUTABLE_PATH=C:/Program Files/Google/Chrome/Application/chrome.exe
```

> ⚠️ **请将 `EXECUTABLE_PATH` 替换为你本机 Chrome 的实际安装路径，否则插件无法启动！**
>
> 常见路径参考：
> - Windows: `C:/Program Files/Google/Chrome/Application/chrome.exe`
> - macOS: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
> - Linux: `/usr/bin/google-chrome`

## ⚠️ 使用须知

1. 本插件仅用于个人学习研究。
2. 请勿高频、大规模爬取网站，避免给目标站点造成压力。
3. 下载内容版权归原作者与平台所有。

## 📁 文件输出

生成的 EPUB 文件将会保存至插件运行目录下。

## 📝 更新日志

### v0.1.5

- 迁移到 `nonebot-plugin-htmlrender` 共享浏览器实例，不再自行创建浏览器
- 依赖版本全部添加 `>=x,<y` 范围限制
- 配置类改为 NoneBot 标准 `Config` + `get_plugin_config`，配置项使用 `BILINOVEL_` 前缀
- logger 统一使用 `nonebot.log`，移除 loguru 依赖
- 新增反爬检测：识别网站返回的假内容并触发重试

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