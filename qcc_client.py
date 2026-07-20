"""
企查查企业核验 API 客户端 v2
============================
接口: api.qichacha.com/EnterpriseInfo/Verify
"""

import json, urllib.request, urllib.parse

QCC_API_URL = "https://api.qichacha.com/EnterpriseInfo/Verify"
QCC_API_KEY = "M0ldHwyR3w7l67oTbVzZJ1mlEfzgtW7wHNNXL9miGbp95oxU"


def verify_company(company_name: str, credit_code: str = "") -> dict:
    """核验企业信息"""
    params = {"key": QCC_API_KEY, "searchKey": company_name}
    if credit_code:
        params["searchKey"] = credit_code
    url = QCC_API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data
    except Exception as e:
        return {"Status": "000", "Message": str(e), "Result": None}


def extract_enterprise_risk(qcc_result: dict) -> dict:
    """将企查查返回数据转为风险评估因子"""
    result = qcc_result.get("Result")
    if not result:
        return {
            "risk_score": 0,
            "risk_factors": {},
            "note": qcc_result.get("Message", "无数据"),
        }
    # 这里后续根据企查查返回的具体字段做评分
    # 示例字段: 经营状态、注册资本、成立日期、法人、股东等
    return {
        "risk_score": 0,
        "risk_factors": {},
        "raw_data": result,
        "note": "已获取企业数据",
    }


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "上海市消防救援总队"
    result = verify_company(name)
    print(json.dumps(result, ensure_ascii=False, indent=2))
