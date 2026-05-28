import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote, urljoin

import httpx
from mcp.server.fastmcp import FastMCP


class Settings:
    """应用配置"""

    API_BASE_URL: str = os.getenv("FXBAOGAO_API_BASE_URL", "https://api.fxbaogao.com").rstrip("/")
    PDF_BASE_URL: str = os.getenv("FXBAOGAO_PDF_BASE_URL", "https://dr.fxbaogao.com/").rstrip("/") + "/"
    HTTP_TIMEOUT: float = float(os.getenv("HTTP_TIMEOUT", "60.0"))
    DOWNLOAD_TIMEOUT: float = float(os.getenv("DOWNLOAD_TIMEOUT", "120.0"))


settings = Settings()

app = FastMCP("FxbaogaoMcp")
client = httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT)


def _api_key() -> str:
    api_key = os.getenv("FXBAOGAO_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing FXBAOGAO_API_KEY. Please export FXBAOGAO_API_KEY=<your_api_key> "
            "before starting the MCP server."
        )
    return api_key


def _headers(accept: str = "application/json") -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Accept": accept,
        "User-Agent": "fxbaogao-mcp/0.1.4",
    }


async def _request_json(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    headers = _headers()
    if payload is not None:
        headers["Content-Type"] = "application/json"

    response = await client.request(
        method,
        f"{settings.API_BASE_URL}{path}",
        json=payload,
        headers=headers,
    )
    response.raise_for_status()
    if not response.content:
        return None
    return response.json()


def _string_or_none(value: Optional[Union[int, str]]) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _add_report_urls(result: Any) -> Any:
    if not isinstance(result, dict):
        return result

    data = result.get("data")
    if isinstance(data, list):
        reports = data
    elif isinstance(data, dict) and isinstance(data.get("dataList"), list):
        reports = data["dataList"]
    else:
        reports = []

    for report in reports:
        if not isinstance(report, dict):
            continue
        report_id = report.get("reportId", report.get("docId"))
        if report_id is not None:
            report["reportUrl"] = f"https://www.fxbaogao.com/view?id={report_id}"

    return result


def _require_report_id(report_id: Optional[int] = None, doc_id: Optional[int] = None, id: Optional[int] = None) -> int:
    value = report_id if report_id is not None else doc_id if doc_id is not None else id
    if value is None:
        raise RuntimeError("Missing reportId")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("reportId must be an integer") from exc


def _normalize_pdf_url(value: str) -> Optional[str]:
    value = value.strip()
    if not value:
        return None
    if value.startswith(("http://", "https://")):
        return value
    return urljoin(settings.PDF_BASE_URL, value.lstrip("/"))


def _extract_pdf_urls(data: Any) -> List[Dict[str, str]]:
    urls: List[Dict[str, str]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lowered = str(key).lower()
                if lowered in ("data", "pdfurl", "url", "fileurl", "downloadurl") and isinstance(child, str):
                    normalized = _normalize_pdf_url(child)
                    if normalized:
                        urls.append({"field": str(key), "url": normalized})
                else:
                    walk(child)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(data)

    seen = set()
    deduped: List[Dict[str, str]] = []
    for item in urls:
        url = item["url"]
        if url not in seen:
            seen.add(url)
            deduped.append(item)
    return deduped


def _sanitize_filename(filename: str) -> str:
    filename = re.sub(r"[\\/:*?\"<>|]+", "_", filename).strip()
    filename = re.sub(r"\s+", " ", filename)
    if not filename or filename in (".", ".."):
        return "report.pdf"
    return filename[:180]


def _ensure_under_workspace(output_dir: str) -> Path:
    workspace = Path(os.getenv("FXBAOGAO_WORKSPACE", os.getcwd())).resolve()
    target_dir = (workspace / output_dir).resolve()
    try:
        target_dir.relative_to(workspace)
    except ValueError as exc:
        raise RuntimeError(f"outputDir must stay under workspace: {workspace}") from exc
    return target_dir


@app.tool(
    name="search_reports",
    description="""搜索发现报告研报。新接口通过 /mofoun/agent/search 完成，需要设置 FXBAOGAO_API_KEY。

参数说明：
- keywords: 搜索关键词，关键词和机构至少提供一个
- org_names/orgNames: 机构名称列表，如 ["中信证券", "华泰证券"]
- start_time/startTime/time: 开始时间，支持毫秒时间戳字符串或 last3day、last7day、last1mon、last3mon、last1year
- end_time/endTime: 结束时间，毫秒时间戳字符串
- authors/page_size: 兼容旧参数；新 agent/search 接口不再使用
"""
)
async def search_reports(
    keywords: Optional[str] = None,
    authors: Optional[List[str]] = None,
    org_names: Optional[List[str]] = None,
    orgNames: Optional[List[str]] = None,
    start_time: Optional[Union[int, str]] = None,
    startTime: Optional[Union[int, str]] = None,
    end_time: Optional[Union[int, str]] = None,
    endTime: Optional[Union[int, str]] = None,
    time: Optional[str] = None,
    page_size: Optional[int] = None,
) -> str:
    _ = authors, page_size
    body: Dict[str, Any] = {
        "keywords": keywords or "",
        "orgNames": orgNames if orgNames is not None else org_names or [],
    }

    resolved_start_time = startTime if startTime is not None else start_time
    resolved_end_time = endTime if endTime is not None else end_time
    if resolved_start_time is not None:
        body["startTime"] = _string_or_none(resolved_start_time)
    elif time is not None:
        body["startTime"] = time
    if resolved_end_time is not None:
        body["endTime"] = _string_or_none(resolved_end_time)

    result = await _request_json("POST", "/mofoun/agent/search", body)
    return json.dumps(_add_report_urls(result), ensure_ascii=False)


@app.tool(
    name="get_paragraphs",
    description="""根据报告 ID 和关键词获取摘要与命中正文段落。

参数说明：
- report_id/reportId/doc_id/id: 报告 ID
- keyword: 用于命中上下文的关键词
"""
)
async def get_paragraphs(
    keyword: str,
    report_id: Optional[int] = None,
    reportId: Optional[int] = None,
    doc_id: Optional[int] = None,
    id: Optional[int] = None,
) -> str:
    resolved_report_id = _require_report_id(
        report_id=reportId if reportId is not None else report_id,
        doc_id=doc_id,
        id=id,
    )
    result = await _request_json(
        "POST",
        "/mofoun/agent/paragraph",
        {"reportId": resolved_report_id, "keyword": keyword},
    )
    return json.dumps(result, ensure_ascii=False)


@app.tool(
    name="get_pdf_url",
    description="""根据报告 ID 获取 PDF 下载地址。

参数说明：
- report_id/reportId/doc_id/id: 报告 ID
"""
)
async def get_pdf_url(
    report_id: Optional[int] = None,
    reportId: Optional[int] = None,
    doc_id: Optional[int] = None,
    id: Optional[int] = None,
) -> str:
    resolved_report_id = _require_report_id(
        report_id=reportId if reportId is not None else report_id,
        doc_id=doc_id,
        id=id,
    )
    result = await _request_json("GET", f"/mofoun/agent/download?reportId={quote(str(resolved_report_id))}")
    payload = {
        "reportId": resolved_report_id,
        "resources": _extract_pdf_urls(result),
        "raw": result,
    }
    return json.dumps(payload, ensure_ascii=False)


@app.tool(
    name="download_pdf",
    description="""根据报告 ID 下载 PDF 到本地工作区。

参数说明：
- report_id/reportId/doc_id/id: 报告 ID
- output_dir: 相对 workspace 的输出目录，默认 intermediate/downloads
- filename: 保存文件名，默认 <reportId>.pdf
- overwrite: 文件存在时是否覆盖
"""
)
async def download_pdf(
    report_id: Optional[int] = None,
    reportId: Optional[int] = None,
    doc_id: Optional[int] = None,
    id: Optional[int] = None,
    output_dir: str = "intermediate/downloads",
    filename: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    resolved_report_id = _require_report_id(
        report_id=reportId if reportId is not None else report_id,
        doc_id=doc_id,
        id=id,
    )
    target_dir = _ensure_under_workspace(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    target_filename = _sanitize_filename(filename or f"{resolved_report_id}.pdf")
    if not target_filename.lower().endswith(".pdf"):
        target_filename += ".pdf"
    target_path = target_dir / target_filename

    if target_path.exists() and not overwrite:
        return json.dumps(
            {
                "reportId": resolved_report_id,
                "path": str(target_path),
                "size": target_path.stat().st_size,
                "skipped": True,
                "reason": "file_exists",
            },
            ensure_ascii=False,
        )

    pdf_info = json.loads(await get_pdf_url(reportId=resolved_report_id))
    resources = pdf_info.get("resources") or []
    if not resources:
        raise RuntimeError(f"No PDF URL found for reportId {resolved_report_id}")

    pdf_url = resources[0]["url"]
    headers = _headers("application/pdf,*/*") if settings.API_BASE_URL in pdf_url else {
        "Accept": "application/pdf,*/*",
        "User-Agent": "fxbaogao-mcp/0.1.4",
    }
    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    try:
        async with httpx.AsyncClient(timeout=settings.DOWNLOAD_TIMEOUT, follow_redirects=True) as download_client:
            async with download_client.stream("GET", pdf_url, headers=headers) as response:
                response.raise_for_status()
                with tmp_path.open("wb") as output:
                    async for chunk in response.aiter_bytes():
                        output.write(chunk)
        tmp_path.replace(target_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    return json.dumps(
        {
            "reportId": resolved_report_id,
            "path": str(target_path),
            "size": target_path.stat().st_size,
            "pdfUrl": pdf_url,
            "skipped": False,
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    app.run(transport="stdio")
