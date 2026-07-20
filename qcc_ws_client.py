"""
企查查 MCP WebSocket 客户端
=============================
通过 WebSocket 连接企查查 MCP Server
"""
import json
import asyncio
import sys

QCC_WS_URL = "wss://agent.qcc.com/mcp/ws"
QCC_API_KEY = "M0ldHwyR3w7l67oTbVzZJ1mlEfzgtW7wHNNXL9miGbp95oxU"


async def mcp_call(method: str, params: dict = None) -> dict:
    """通过WebSocket调用企查查MCP"""
    import websockets
    headers = {"Authorization": f"Bearer {QCC_API_KEY}"}
    async with websockets.connect(QCC_WS_URL, additional_headers=headers,
                                  proxy=None) as ws:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1,
        }
        await ws.send(json.dumps(payload))
        resp = await asyncio.wait_for(ws.recv(), timeout=15)
        return json.loads(resp)


async def list_tools():
    """列出所有可用MCP工具"""
    result = await mcp_call("tools/list")
    return result


async def get_company_by_query(keyword: str):
    """搜索企业"""
    result = await mcp_call("mcp__qcc-company__get_company_by_query", {
        "keyword": keyword
    })
    return result


async def get_company_detail(keyword: str):
    """获取企业详情"""
    result = await mcp_call("mcp__qcc-company__get_company_detail", {
        "keyword": keyword
    })
    return result


async def get_company_risk_scan(keyword: str):
    """企业风险扫描"""
    result = await mcp_call("mcp__qcc-risk__get_company_risk_scan", {
        "keyword": keyword
    })
    return result


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list_tools"
    kw = sys.argv[2] if len(sys.argv) > 2 else ""

    if cmd == "list_tools":
        result = asyncio.run(list_tools())
    elif cmd == "search":
        result = asyncio.run(get_company_by_query(kw or "上海消防"))
    elif cmd == "detail":
        result = asyncio.run(get_company_detail(kw or "上海消防"))
    elif cmd == "risk":
        result = asyncio.run(get_company_risk_scan(kw or "上海消防"))
    else:
        result = {"error": f"Unknown command: {cmd}"}

    print(json.dumps(result, ensure_ascii=False, indent=2))
