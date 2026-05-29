# 发现报告 MCP

这是发现报告（fxbaogao.com）的 MCP 接入项目，提供研究报告搜索、命中段落获取、PDF 下载地址获取和本地 PDF 下载能力。

本仓库是本地版 MCP Server，适合在本机通过 `stdio` 方式运行。发现报告也提供在线 HTTP 版 MCP，均可直接添加到 Claude 等 MCP 的客户端。

发现报告 API key。开通请咨询[发现报告客服（工作日9:00-18:00）](https://www.fxbaogao.com/seo/kefu)。

## 在线 HTTP 版

如果只需要使用在线版，不需要安装本仓库。直接添加远程 MCP：

```bash
claude mcp add --transport http fxbaogao --scope user https://api.fxbaogao.com/mcp/ \
  --header "Authorization: Bearer sk-xxx"
```

把 `sk-xxx` 替换为你的发现报告 API Key。

如果客户端支持 JSON 配置远程 MCP，可使用：

```json
{
  "mcpServers": {
    "fxbaogao": {
      "type": "http",
      "url": "https://api.fxbaogao.com/mcp/",
      "headers": {
        "Authorization": "Bearer sk-xxx"
      }
    }
  }
}
```

## 本地版

使用 `uvx` 启动：

```json
{
  "mcpServers": {
    "fxbaogao-mcp": {
      "command": "uvx",
      "args": ["fxbaogao-mcp@latest"],
      "env": {
        "FXBAOGAO_API_KEY": "<your_api_key>"
      }
    }
  }
}
```

本地开发时也可以从源码运行：

```bash
export FXBAOGAO_API_KEY=<your_api_key>
.venv/bin/python -m fxbaogao_mcp
```


## 工具

### `search_reports`

按关键词、机构、时间范围搜索发现报告研报。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `keywords` | string | 搜索关键词 |
| `orgNames` | string[] | 机构列表 |
| `startTime` | string | 如 `last7day`、`last1mon`、`last3mon`、`last1year`，或毫秒时间戳字符串 |
| `endTime` | string | 结束时间戳，毫秒 |

返回结果中会补充官网阅读链接：

```text
https://www.fxbaogao.com/view?id=<reportId>
```

### `get_paragraphs`

使用 `search_reports` 返回的 `reportId` 获取指定报告的摘要、目录和正文命中段落，`reportId` 必传。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `reportId` | integer | 报告 ID |
| `keyword` | string | 用于命中上下文的关键词 |

### `get_pdf_url`

使用 `search_reports` 返回的 `reportId` 获取报告 PDF 地址，`reportId` 必传。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `reportId` | integer | 报告 ID |

### `download_pdf`

根据报告 ID 下载 PDF 到本地工作区。

主要参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `reportId` | integer | 报告 ID |
| `output_dir` | string | 相对 `FXBAOGAO_WORKSPACE` 的输出目录，默认 `downloads` |
| `filename` | string | 保存文件名，默认 `<reportId>.pdf` |
| `overwrite` | boolean | 文件存在时是否覆盖 |


## 注意事项

本工具仅供学习和研究使用，请遵守发现报告的使用条款和相关法律法规。
