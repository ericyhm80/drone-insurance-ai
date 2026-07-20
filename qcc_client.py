"""
企查查 MCP 客户端封装
=====================
通过 agent.qcc.com MCP 协议查询企业信息
"""

import json
import urllib.request

QCC_MCP_URL = "https://agent.qcc.com/mcp/v1"
QCC_API_KEY = "M0ldHwyR3w7l67oTbVzZJ1mlEfzgtW7wHNNXL9miGbp95oxU"


def mcp_call(method: str, params: dict = None) -> dict:
    """调用企查查MCP Server"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": 1,
    }
    req = urllib.request.Request(
        QCC_MCP_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {QCC_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def get_company_info(company_name: str) -> dict:
    """查询企业信息"""
    return mcp_call("mcp__qcc-company__get_company_by_query", {
        "keyword": company_name
    })


def get_company_risk(company_name: str) -> dict:
    """查询企业风险扫描"""
    return mcp_call("mcp__qcc-risk__get_company_risk_scan", {
        "keyword": company_name
    })


if __name__ == "__main__":
    # 测试查询
    result = get_company_info("上海市消防救援总队")
    print(json.dumps(result, ensure_ascii=False, indent=2))
