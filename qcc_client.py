"""
企查查企业核验 API 客户端 v3
=============================
认证方式: 
  - Query: key=AppKey
  - Header: Token=MD5(key+Timespan+SecretKey), Timespan=Unix时间戳
"""
import json, time, hashlib, urllib.request, urllib.parse

QCC_API_URL = "https://api.qichacha.com/EnterpriseInfo/Verify"
QCC_APPKEY = "b0dc59dac28e4636a25aa3b3b3052a3b"
QCC_SECRETKEY = "813BBC405D426F74B8ABCA8720A960F7"


def _make_token(timespan: str) -> str:
    """生成Token: MD5(key+Timespan+SecretKey) 32位大写"""
    raw = QCC_APPKEY + timespan + QCC_SECRETKEY
    return hashlib.md5(raw.encode()).hexdigest().upper()


def verify_company(company_name: str) -> dict:
    """核验企业信息"""
    timespan = str(int(time.time()))
    token = _make_token(timespan)

    params = {"key": QCC_APPKEY, "searchKey": company_name}
    url = QCC_API_URL + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Token": token,
        "Timespan": timespan,
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"Status": "000", "Message": str(e), "Result": None}


def extract_risk_score(qcc_data: dict) -> dict:
    """将企查查企业数据转为投保人风险评分"""
    result = qcc_data.get("Result")
    if not result or result.get("VerifyResult") != 1:
        return {"risk_factor": 1.0, "note": "企业未查到或不存在", "data": None}

    data = result.get("Data", {})
    status = data.get("Status", "")
    years_in_biz = 0
    start_date = data.get("StartDate", "")
    if start_date:
        try:
            from datetime import datetime
            start = datetime.strptime(start_date, "%Y-%m-%d")
            years_in_biz = (datetime.now() - start).days / 365
        except:
            pass

    # 风险评分因子
    risk_factor = 1.0

    # 经营状态
    if "注销" in status or "吊销" in status:
        risk_factor = 2.5  # 高风险，不可投保
    elif "停业" in status:
        risk_factor = 1.8
    elif "存续" in status:
        risk_factor = 0.9  # 正常

    # 成立年限越长风险越低
    if years_in_biz < 1:
        risk_factor *= 1.3
    elif years_in_biz < 3:
        risk_factor *= 1.1
    elif years_in_biz > 10:
        risk_factor *= 0.85

    return {
        "risk_factor": risk_factor,
        "note": f"企业核验通过: {data.get('Name', '')}",
        "data": {
            "company_name": data.get("Name", ""),
            "credit_code": data.get("CreditCode", ""),
            "legal_person": data.get("OperName", ""),
            "status": status,
            "start_date": start_date,
            "years_in_biz": round(years_in_biz, 1),
            "registered_capital": data.get("RegistCapi", ""),
            "insured_count": data.get("InsuredCount", ""),
            "address": data.get("Address", ""),
            "industry": (data.get("Industry") or {}).get("Industry", ""),
            "scale": data.get("Scale", ""),
            "is_small_micro": data.get("IsSmall", ""),
        }
    }


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "小米科技有限责任公司"
    result = verify_company(name)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("Status") == "200":
        risk = extract_risk_score(result)
        print("\n=== 风险评分 ===")
        print(json.dumps(risk, ensure_ascii=False, indent=2))
