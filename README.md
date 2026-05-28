# 发现报告 MCP

这是发现报告（fxbaogao.com）的 MCP 接入项目，提供研究报告搜索、命中段落获取、PDF 下载地址获取和本地 PDF 下载能力。

本仓库是本地版 MCP Server，适合在本机通过 `stdio` 方式运行。发现报告也提供在线 HTTP 版 MCP，可直接添加到 Claude 等支持远程 MCP 的客户端。

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

搜索研究报告。

主要参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `keywords` | string | 搜索关键词，关键词和机构至少提供一个 |
| `org_names` / `orgNames` | string[] | 机构名称列表 |
| `start_time` / `startTime` / `time` | string / int | 开始时间，支持毫秒时间戳字符串，也支持 `last3day`、`last7day`、`last1mon`、`last3mon`、`last1year` |
| `end_time` / `endTime` | string / int | 结束时间，毫秒时间戳 |

返回结果中会补充官网阅读链接：

```text
https://www.fxbaogao.com/view?id=<reportId>
```

### `get_paragraphs`

根据报告 ID 和关键词获取摘要与命中正文段落。

主要参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `report_id` / `reportId` / `doc_id` / `id` | integer | 报告 ID |
| `keyword` | string | 用于命中上下文的关键词 |

### `get_report_content`

兼容旧工具名，内部调用 `get_paragraphs`。


### `get_pdf_url`

根据报告 ID 获取 PDF 下载地址。

主要参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `report_id` / `reportId` / `doc_id` / `id` | integer | 报告 ID |

### `download_pdf`

根据报告 ID 下载 PDF 到本地工作区。

主要参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `report_id` / `reportId` / `doc_id` / `id` | integer | 报告 ID |
| `output_dir` | string | 相对 `FXBAOGAO_WORKSPACE` 的输出目录，默认 `intermediate/downloads` |
| `filename` | string | 保存文件名，默认 `<reportId>.pdf` |
| `overwrite` | boolean | 文件存在时是否覆盖 |


## 注意事项

本工具仅供学习和研究使用，请遵守发现报告的使用条款和相关法律法规。
