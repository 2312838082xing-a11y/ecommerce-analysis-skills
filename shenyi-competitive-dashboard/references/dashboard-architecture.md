# Dashboard 架构参考

## 目录

1. 输出结构
2. 页面与模块
3. 数据契约
4. 数据安全嵌入
5. 状态与渲染
6. 核心交互
7. 图表与格式化
8. 验证

## 1. 输出结构

输出一个可直接打开的 HTML 文件，通过固定版本 CDN 引用 Chart.js 4.4.1。CSS、业务数据和渲染逻辑保存在 HTML 内，不增加服务器或构建工具依赖。

## 2. 页面与模块

页面包含：标题与口径摘要、Tab 导航、Tab 级估值切换、动态模块区和数据说明。

典型 Tab：

- 竞争店铺总览
- 用户确认的一个或多个单品价格带

不要从价格自动猜价格带。Tab 数量和归属来自用户配置。

### 店铺模块

| 模块 | 数据 | 展示 |
|---|---|---|
| 趋势 | 店铺月度指标 | 折线图与摘要表 |
| 流量 | 店铺流量 | 顶层对比与三级明细 |
| 搜索词 | 店铺关键词 | 店铺、月份筛选表 |
| 竞争格局 | 已展示指标 | 带证据的策略标签 |

### 单品模块

| 模块 | 默认链接范围 | 展示 |
|---|---|---|
| 趋势 | Top1 | 折线图与表格 |
| GMV 估算 | Top1 | 低/中/高区间与累计值 |
| 流量 | Top1 | 三级树形明细 |
| 搜索词 | Top1 | 月份分组表 |
| SKU | 所有有效链接 | 占比与估算人数 |
| 策略 | Top1及已展示证据 | 证据卡片 |

Top1 必须基于共同观察窗口排名。模块说明中显示商品链接和排名窗口。

## 3. 数据契约

推荐结构：

```javascript
{
  "meta": {
    "schema_version": "2.0",
    "estimate_default": "mid",
    "source_files": ["example.xlsx"],
    "generated_at": "2026-07-05"
  },
  "store": {
    "stores": ["店铺A"],
    "dates": ["2026-02-01"],
    "traffic_periods": ["2026-02-01 ~ 2026-02-28"],
    "data": {
      "店铺A": {
        "category": "竞店1",
        "dates": ["2026-02-01"],
        "visitors": [{"low":100,"mid":150,"high":200}],
        "buyers": [{"low":10,"mid":15,"high":20}],
        "conv_rate": [{"low":0.05,"mid":0.075,"high":0.1}],
        "cart_adds": [null],
        "favorites": [null]
      }
    },
    "traffic": {"店铺A": {"period": {"top": {}, "l1": {}, "l2": {}}}},
    "keywords": {"店铺A": []}
  },
  "product": {
    "competitors": ["竞品A"],
    "data": {
      "竞品A": {
        "price": 13600,
        "price_note": "参考价 ¥13,600",
        "price_tier": "mid",
        "all_link_ids": ["656821090235"],
        "links": []
      }
    }
  }
}
```

每条商品链接至少包含：`product_name`、`product_id`、`dates`、五个指标数组、`total_buyers_mid`、`keywords`、`skus`、`traffic`。缺失指标数组用与 `dates` 等长的 `null`，不能缩短数组。

店铺流量使用 `{top:{}, l1:{}, l2:{}}` 对象结构，单品链接流量使用记录数组。两者的渲染函数分开处理，不增加额外迁移层。

## 4. 数据安全嵌入

新建页面优先使用 `application/json` 数据块，而不是把用户数据拼接成可执行 JavaScript：

```html
<script id="dashboard-data" type="application/json">{"store":{},"product":{}}</script>
<script>
  const D = JSON.parse(document.getElementById('dashboard-data').textContent);
</script>
```

序列化时至少将 `<` 转义为 `\u003c`，防止商品名或搜索词中的 `</script>` 提前结束数据块。不要把未经转义的名称插入 `innerHTML` 或内联 `onclick`。

静态结构可用模板字符串；动态文本使用 `textContent`。事件使用 `addEventListener` 和 `data-*` 属性：

```javascript
container.addEventListener('click', (event) => {
  const button = event.target.closest('[data-action]');
  if (!button) return;
  if (button.dataset.action === 'set-estimate') setEstimate(button.dataset.level);
});
```

商品跳转 URL 只使用清洗后的数字 ID，并设置 `rel="noopener noreferrer"`。

## 5. 状态与渲染

集中保存状态，避免模块各自维护不一致副本：

```javascript
const state = {
  activeTab: 'store',
  estimate: {store: 'mid'},
  trafficPeriod: {},
  keywordEntity: {},
  skuCompetitor: {}
};

const charts = new Map();
```

估值切换应从 Tab 入口统一触发该 Tab 全部模块重绘。不要手工维护容易漏项的散落调用；用模块注册表：

```javascript
const productRenderers = [renderProdTrend, renderProdGmv, renderProdTraffic,
  renderProdKeywords, renderProdSku, renderProdStrategy];

function renderProductTab(tier) {
  productRenderers.forEach((render) => render(tier, state));
}
```

创建图表前销毁同 canvas 的旧实例：

```javascript
function replaceChart(id, config) {
  charts.get(id)?.destroy();
  const chart = new Chart(document.getElementById(id), config);
  charts.set(id, chart);
  return chart;
}
```

## 6. 核心交互

- Sticky 估值条放在 Tab 级，不能被模块容器裁切。
- 收起流量父级时同步收起后代。
- 图表旁保留数据表或摘要。
- 调色板数量不少于同时展示的系列数，并保持竞品颜色跨模块一致。

## 7. 图表与格式化

格式化函数必须处理 `null`、零和非有限数：

```javascript
function fmtNumber(value) {
  if (value == null || !Number.isFinite(value)) return '-';
  if (Math.abs(value) >= 10000) return `${(value / 10000).toFixed(1)}万`;
  return new Intl.NumberFormat('zh-CN', {maximumFractionDigits: 0}).format(value);
}

function fmtPercent(value) {
  if (value == null || !Number.isFinite(value)) return '-';
  return `${(value * 100).toFixed(2)}%`;
}
```

GMV 图表显示估值口径，并在 tooltip 或说明中写明公式。不要给估算值增加没有依据的小数精度。

## 8. 验证

### 静态检查

1. 从自有脚本块提取 JavaScript，使用 `node --check`。
2. 检查数据 JSON 可解析，并运行 `scripts/validate_data.py`。
3. 检查所有静态 ID 唯一；所有渲染目标存在。
4. 搜索内联事件、未转义动态 `innerHTML`、未清洗商品 ID。

### 浏览器冒烟测试

1. 打开所有 Tab，观察控制台。
2. 切换 low/mid/high，确认所有相关数值变化。
3. 切换店铺、竞品和月份。
4. 展开/收起三级流量。
5. 点击商品链接并核对 ID。
6. 重复切换 Tab，确认图表不叠加。
