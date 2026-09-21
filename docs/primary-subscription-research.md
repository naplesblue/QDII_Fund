# 场内申购数据实测

测试日期：2026-09-11（北京时间）。从实际部署 VPS 发起只读请求；没有修改线上字段、触发申购或全量抓取。

## 结论

四只 ETF 的官方数据接口均返回 2026-09-11 清单，代码、日期和申购状态均可核对，具备小范围接入可行性。尚未验证全市场覆盖率、持续可用性及零值完整语义。LOF 161128 的官方交易状态接口没有明确场内渠道，不能用于确认场内申购限额。

| 代码 | 名称 | 最小单位（份） | 全基金日上限（份） | 单账户日上限（份） |
|---|---|---:|---|---|
| 513100 | 纳指 ETF 国泰 | 1,000,000 | 累计申购 3,000,000 | 累计申购 1,000,000 |
| 513390 | 纳指100 ETF 博时 | 1,000,000 | 累计申购 1,000,000 | 累计申购 1,000,000 |
| 513110 | 纳指 ETF 华泰柏瑞 | 1,000,000 | 累计申购 1,000,000 | 原始值 `-`，未取得数值 |
| 159696 | 纳指 ETF 易方达 | 1,000,000 | 净申购 15,000,000 | 净申购 1,000,000 |

四只均返回允许申购及赎回。数值单位为基金份额，不是人民币金额，也不是实时剩余额度。最小单位净值分别为 1,987,318.22、2,230,922.84、2,281,735.35、1,850,016.05 元；这不是精确申购所需现金，实际还涉及现金替代、预估现金和费用等。

## 上交所接口

官方入口：https://etf.sse.com.cn/fundlist/funddetail/index.shtml?code=513100

页面的 `/xhtml/js/api.js` 与 `/xhtml/js/funddetail_new.js?v=V3.1.1` 给出真实调用方式：

```text
GET https://query.sse.com.cn/commonQuery.do
?isPagination=false
&sqlId=COMMON_SSE_CP_JJLB_ETFJJGK_GGSGSHQD_JBXX_C
&FUNDID2=513100
Referer: https://etf.sse.com.cn/
```

必须校验 `result[].TRADE_CODE` 和 `TRADING_DAY`。错误参数 `FUND_ID` 会被忽略，曾返回其他基金的旧记录，因此“HTTP 200”不足以证明成功。

字段：`CREATION_REDEMPTION`、`CREATION_REDEMPTION_UNIT`、`CREATION_LIMIT`、`CREATION_LIMIT_PER_ACCT`、`NET_CREATION_LIMIT`、`NET_CREATION_LIMIT_PER_ACCT`。页面将部分上限字段的 0 显示为 `-`；未核清底层规范前，不能把 0 自动解释为不限或禁止申购。优先读取明确的申购状态。

原始响应：`work/primary-probe/513100.json`、`513390.json`、`513110.json`。

## 易方达深市 ETF 接口

官方入口：https://www.efunds.com.cn/Mobile/fund/159696.shtml

页面内嵌脚本提供：

```text
GET https://api.efunds.com.cn/xcowch/front/etffund/baseinfo?fundCode=159696&listType=1&tDate=2026-09-11
```

`listType=1` 是场内申赎清单，集合申购为另一个类型。响应 `status=1`；校验 `data.tDate`、`etfInfo.C_FUNDID`、`etfInfo.D_TRADINGDAY` 和 `map.SECURITYID`。

159696 的 `CREATION=是`、`REDEMPTION=是`、`CREATIONREDEMPTIONUNIT=1000000`、`NETCREATIONLIMIT=15000000`、`NETCREATIONLIMITPERUSER=1000000`；累计申购上限两个字段为 `无`。只展示明确披露的净上限，不把 `无` 转换成无限额。

原始响应：`work/primary-probe/159696.json`。

## LOF 验证限制

```text
GET https://api.efunds.com.cn/xcowch/front/fund/tradestatus/161128?date=2026-09-11
```

响应 `status=1`；个人和机构下均有非直销机构、网上直销、直销中心，全部 `subscription=false`，`limit` 为空。没有明确的场内渠道标识，不能将该响应直接写入“场内申购额度”。需继续核查最新生效公告是否覆盖场内、账户合并方式及渠道限制。

第三方检索结果对 161128 出现 10 元、暂停申购、不限额等相互冲突的描述，不作为有效场内限额证据。

原始响应：`work/primary-probe/161128-status.json`。

## 接入建议

- 首先接入已验证的上交所 ETF 及易方达 ETF；其他基金保留未获取，不能声称完整覆盖深市。
- 分别保存累计/净申购、全基金/单账户上限及最小申购单位，统一单位为份。
- 保留原始值、清单交易日、获取时间和官方来源；净值日期与清单日期不同不应混淆。
- 仅作为当日披露上限；不承诺实时剩余额度或实际申购确认。
- 按交易日缓存，沿用共享请求锁和失败冷却；重试不得反复扫上游。
- 本地到交易所连接失败，VPS 获取成功但发生过间歇 DNS 错误；易方达页面曾传输中断，但独立数据 API 返回完整 JSON。生产应校验完整响应并处理失败。
