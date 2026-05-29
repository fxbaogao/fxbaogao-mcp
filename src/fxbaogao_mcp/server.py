import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote, urljoin

import httpx
from mcp.server.fastmcp import FastMCP


USER_AGENT = "fxbaogao-mcp/1.0.2"
PDF_URL_KEYS = {"pdfurl", "url", "fileurl", "downloadurl"}
RELATIVE_PDF_URL_KEYS = PDF_URL_KEYS | {"data"}


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
        "User-Agent": USER_AGENT,
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
        report_id = report.get("reportId")
        if report_id is not None:
            report["reportUrl"] = f"https://www.fxbaogao.com/view?id={report_id}"

    return result


def _coerce_report_id(value: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("reportId must be an integer") from exc


def _looks_like_pdf_reference(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith(("http://", "https://", "/")) or ".pdf" in lowered


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
                if not isinstance(child, str):
                    walk(child)
                    continue
                if lowered in PDF_URL_KEYS or (lowered in RELATIVE_PDF_URL_KEYS and _looks_like_pdf_reference(child)):
                    normalized = _normalize_pdf_url(child)
                    if normalized:
                        urls.append({"field": str(key), "url": normalized})
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
    description="""按关键词、机构、时间范围搜索发现报告研报。

keywords string 搜索关键词
orgNames string[] 机构列表
startTime string 如 last7day、last1mon、last3mon、last1year，或毫秒时间戳字符串
endTime string 结束时间戳，毫秒
"""
)
async def search_reports(
    keywords: Optional[str] = None,
    orgNames: Optional[List[str]] = None,
    startTime: Optional[Union[int, str]] = None,
    endTime: Optional[Union[int, str]] = None,
) -> str:
    body: Dict[str, Any] = {
        "keywords": keywords or "",
        "orgNames": orgNames or [],
    }

    if startTime is not None:
        body["startTime"] = _string_or_none(startTime)
    if endTime is not None:
        body["endTime"] = _string_or_none(endTime)

    result = await _request_json("POST", "/mofoun/agent/search", body)
    return json.dumps(_add_report_urls(result), ensure_ascii=False)


@app.tool(
    name="get_paragraphs",
    description="""使用 search_reports 返回的 reportId 获取指定报告的摘要、目录和正文命中段落，reportId 必传。

reportId integer 报告 ID
keyword string 用于命中上下文的关键词
"""
)
async def get_paragraphs(
    reportId: int,
    keyword: str,
) -> str:
    result = await _request_json(
        "POST",
        "/mofoun/agent/paragraph",
        {"reportId": reportId, "keyword": keyword},
    )
    return json.dumps(result, ensure_ascii=False)


@app.tool(
    name="get_pdf_url",
    description="""使用 search_reports 返回的 reportId 获取报告 PDF 地址，reportId 必传。

reportId integer 报告 ID
"""
)
async def get_pdf_url(
    reportId: int,
) -> str:
    result = await _request_json("GET", f"/mofoun/agent/download?reportId={quote(str(reportId))}")
    payload = {
        "reportId": reportId,
        "resources": _extract_pdf_urls(result),
        "raw": result,
    }
    return json.dumps(payload, ensure_ascii=False)


@app.tool(
    name="download_pdf",
    description="""根据报告 ID 下载 PDF 到本地工作区。

参数说明：
- reportId: 报告 ID
- output_dir: 相对 workspace 的输出目录，默认 downloads
- filename: 保存文件名，默认 <reportId>.pdf
- overwrite: 文件存在时是否覆盖
"""
)
async def download_pdf(
    reportId: int,
    output_dir: str = "downloads",
    filename: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    report_id = _coerce_report_id(reportId)
    target_dir = _ensure_under_workspace(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    target_filename = _sanitize_filename(filename or f"{report_id}.pdf")
    if not target_filename.lower().endswith(".pdf"):
        target_filename += ".pdf"
    target_path = target_dir / target_filename

    if target_path.exists() and not overwrite:
        return json.dumps(
            {
                "reportId": report_id,
                "path": str(target_path),
                "size": target_path.stat().st_size,
                "skipped": True,
                "reason": "file_exists",
            },
            ensure_ascii=False,
        )

    pdf_info = json.loads(await get_pdf_url(reportId=report_id))
    resources = pdf_info.get("resources") or []
    if not resources:
        raise RuntimeError(f"No PDF URL found for reportId {report_id}")

    pdf_url = resources[0]["url"]
    headers = _headers("application/pdf,*/*") if settings.API_BASE_URL in pdf_url else {
        "Accept": "application/pdf,*/*",
        "User-Agent": USER_AGENT,
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
            "reportId": report_id,
            "path": str(target_path),
            "size": target_path.stat().st_size,
            "pdfUrl": pdf_url,
            "skipped": False,
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    app.run(transport="stdio")
