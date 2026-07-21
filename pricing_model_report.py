import sys
sys.path.insert(0, '/Users/ericyhm/drone-insurance-ai-demo')
from risk_engine import score_drone_risk, DRONE_RISK_DB

print('=' * 72)
print('  无人机保险报价模型 | 基于 ccgp.gov.cn 政府采购数据校准')
print('=' * 72)

# 一、机身险基础费率
print()
print('一、机身险基础费率（%/年）')
print('-' * 56)
print(f'{"风险等级":<16} {"最低%":>8} {"最高%":>8}')
print('-' * 56)
print(f'{"低风险  🟢":<16} {"2.5":>8} {"4.0":>8}')
print(f'{"中低风险 🟡":<16} {"4.0":>8} {"6.0":>8}')
print(f'{"中高风险 🟠":<16} {"6.0":>8} {"10.0":>8}')
print(f'{"高风险  🔴":<16} {"10.0":>8} {"15.0":>8}')
print()
print('  参考: DJI Care Refresh 消费级3-8%')
print('        政府采购行业级 6-10%')

# 二、三者险费率
print()
print('二、三者险费率（‰）')
print('-' * 44)
print(f'{"保额":<16} {"费率‰":>8} {"保费/年":>12}')
print('-' * 44)
for limit, rate in [(500000,0.35), (1000000,0.45), (2000000,0.55), (5000000,0.70), (10000000,0.85)]:
    premium = limit * rate / 1000
    print(f'{"¥"+str(limit//10000)+"万":<16} {str(rate):>8} {"¥"+str(int(premium)):>12}')

# 三、按机型报价
print()
print('三、按机型年保费（标准场景: 巡检/郊区/机长/三者险200万）')
print('-' * 72)
print(f'{"机型":<26} {"设备价":>8} {"机身险":>10} {"三者险":>10} {"总保费":>10}')
print('-' * 72)

for model in ['DJI Mini 4 Pro', 'DJI Air 3', 'DJI Mavic 3 Pro', 'DJI Mavic 4',
              'DJI Mavic 3T (企业版)', 'DJI Matrice 30T (M30T)', 'DJI H30T',
              'DJI Matrice 350 RTK', 'DJI FlyCart 30']:
    info = DRONE_RISK_DB.get(model)
    if not info:
        continue
    price = info['base_price_cny']
    r = score_drone_risk(model, '巡检/测绘', 150,
                         'CAAC超视距驾驶员（机长）', '城市郊区', price,
                         third_party_limit=2000000, fleet_size=1)
    hull_p = int(r['hull_premium_min_cny'])
    tp_p = int(r['third_party_premium_cny'])
    total_p = int(r['total_premium_min_cny'])
    print(f'{model:<26} ¥{price:>6,} ¥{hull_p:>6,} ¥{tp_p:>6,} ¥{total_p:>6,}')

# 四、政府采购比价
print()
print('四、政府采购比价（数据源: ccgp.gov.cn）')
print('-' * 72)

# 标书1: 上海消防
print('【标书1】上海消防救援总队特勤支队2026年无人机保险')
print('  预算: ¥180,000 | 16架 + 2镜头 | 三者险≥200万')
print('  服务: 7x24h报案 + 1h对接 + 48h定损')

fleet_plan = [
    ('DJI Matrice 350 RTK', 65000, 2, 'M350RTK'),
    ('DJI Matrice 30T (M30T)', 35000, 2, 'M30T'),
    ('DJI H30T', 40000, 2, 'H30T'),
    ('DJI Mavic 3T (企业版)', 25000, 10, 'Mavic 3T'),
]
total_ai = 0
for model, hull, qty, name in fleet_plan:
    r = score_drone_risk(model, '应急/消防', 200,
                         'CAAC超视距驾驶员（机长）', '城市密集区', hull,
                         third_party_limit=2000000, fleet_size=16)
    per = int(r['total_premium_min_cny'])
    subtotal = per * qty
    total_ai += subtotal
    print(f'    {name:<10} ¥{per:>6,}/架 x {qty} = ¥{subtotal:>8,}')

print(f'    {"AI纯保费合计":>34} ¥{total_ai:>8,}')
service_fee = 180000 - total_ai
print(f'    {"剩余(服务+利润+镜头险)":>34} ¥{service_fee:>8,}')
print(f'    {"服务占比":>34} {service_fee/180000*100:.0f}%')
print()
print('  -> AI可替代服务部分(66%)，将保费降至 ¥95,000-120,000')

# 五、场景报价速查
print()
print('五、场景报价速查（三者险200万）')
print('-' * 72)
print(f'{"场景":<40} {"设备":>7} {"机身险":>8} {"三者险":>8} {"总计":>8}')
print('-' * 72)

scenarios = [
    ('航拍爱好者·郊区·机长·Mini 4 Pro', 'DJI Mini 4 Pro',
     '航拍摄影', 50, 'CAAC超视距驾驶员（机长）', '野外/农村', 10000),
    ('巡检公司·郊区·机长·M350RTK·200h', 'DJI Matrice 350 RTK',
     '巡检/测绘', 200, 'CAAC超视距驾驶员（机长）', '城市郊区', 65000),
    ('消防应急·城市·机长·M30T·200h', 'DJI Matrice 30T (M30T)',
     '应急/消防', 200, 'CAAC超视距驾驶员（机长）', '城市密集区', 35000),
    ('警用侦查·城市·机长·Mavic 3T·300h', 'DJI Mavic 3T (企业版)',
     '警用侦查/监控', 300, 'CAAC超视距驾驶员（机长）', '城市密集区', 25000),
    ('运载投送·郊区·机长·FlyCart 30', 'DJI FlyCart 30',
     '运载/物资投送', 500, 'CAAC超视距驾驶员（机长）', '城市郊区', 125000),
    ('农业植保·农村·视距内·T60·200h', 'DJI Agras T60',
     '农业植保', 200, 'CAAC视距内驾驶员', '野外/农村', 60000),
]

for desc, model, usage, hours, pilot, env, hull in scenarios:
    r = score_drone_risk(model, usage, hours, pilot, env, hull,
                         third_party_limit=2000000, fleet_size=1)
    t = int(r['total_premium_min_cny'])
    h = int(r['hull_premium_min_cny'])
    tp = int(r['third_party_premium_cny'])
    print(f'{desc:<40} ¥{hull:>5,} ¥{h:>5,} ¥{tp:>5,} ¥{t:>5,}')

# 六、定价公式
print()
print('六、定价公式')
print('-' * 72)
print('  总保费 = 机身险保费 + 三者险保费')
print('  机身险 = 保额 x 费率%(2.5%-15% 按风险等级)')
print('  三者险 = 保额 x 费率‰(0.35‰-0.85‰ 按保额分档)')
print('  机队折扣 = 每多一架减0.5分(最多减5分)')
print()
print('  校准基准: 上海消防特勤支队2026标书(ccgp.gov.cn)')
print(f'  -> ¥180,000 / 16架 = 均价¥{180000//16:>5,}/架')
print(f'  -> 其中: 纯保费≈¥{total_ai//16:>5,}/架, 服务费≈¥{service_fee//16:>5,}/架')
print()
print('七、数据来源')
print('-' * 72)
print('  1. ccgp.gov.cn 中国政府采购网 - 上海消防标书(直接抓取)')
print('  2. ccgp.gov.cn 公告列表(10页筛选) - 攀枝花/深圳/临沂等')
print('  3. DJI Care Refresh 官方定价 - 消费级基准')

print()
print('=' * 72)
print('  v0.8 | 晶世科保 | 参考平安/中再/Munich Re/Allianz行业标准')
print('=' * 72)
