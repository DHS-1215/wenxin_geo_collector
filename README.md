# 文心 GEO 采集系统

基于 Playwright + Chrome CDP 实现的百度文心助手 GEO 数据采集系统。

系统通过浏览器真实交互完成问题批量提交、回答正文提取、信源采集、批次管理、断点续跑以及 GEO 标准数据包导出，可用于品牌 / 产品在生成式 AI 搜索场景中的回答与信源数据采集。

## 1. 已实现能力

当前系统支持：

* 百度文心助手网页真实采集
* Chrome CDP 登录态复用
* CSV 产品题库驱动
* 文心「快速」回答模式
* 回答生成状态检测
* 回答正文提取与清洗
* 回答 Session ID 提取
* 模型元数据提取
* Deep Search 状态提取
* 回答信源列表提取
* 信源标题、URL、域名及标签提取
* 产品级批量任务
* 单题异常隔离
* Checkpoint 实时保存
* 批次断点续跑
* 失败任务重新执行
* GEO 标准五件套导出
* SHA-256 完整性校验
* 标准目录验证
* ZIP 标准包生成与验证
* Capacity / 风控迹象检测

## 2. 当前支持产品

### 鸿茅药酒

```text
product_id: hongmao_yaojiu
题库: input/hongmao_questions.csv
```

### 天益寿气血固本

```text
product_id: tianyishou_qixueguben
题库: input/tianyishou_questions.csv
```

系统采用产品配置 + CSV 题库方式运行，Collector 核心代码不依赖具体产品。

## 3. GEO 模式映射

当前输入题库包含：

```text
quick
expert
```

文心网页当前已确认的回答模式包括：

```text
fast = 快速
task = 工作任务
```

目前正式映射关系：

```text
GEO quick
    ↓
文心 fast
```

即：

```text
quick -> fast
```

当前尚未确认 GEO `expert` 与文心「工作任务」之间是否语义等价，因此：

```text
expert
```

任务暂时跳过，不进行错误映射。

系统不会为了满足任务数量而人为将：

```text
expert -> task
```

强行对应。

## 4. 项目结构

```text
wenxin_geo_collector/
├── app/
│   └── wenxin/
│       ├── answer.py
│       ├── batch.py
│       ├── capacity.py
│       ├── checkpoint.py
│       ├── checksum.py
│       ├── client.py
│       ├── exporter.py
│       ├── geo_contract.py
│       ├── input_loader.py
│       ├── packager.py
│       ├── products.py
│       ├── selectors.py
│       ├── serialization.py
│       ├── sources.py
│       ├── types.py
│       └── verifier.py
│
├── input/
│   ├── hongmao_questions.csv
│   └── tianyishou_questions.csv
│
├── output/
│   ├── checkpoints/
│   └── package/
│
├── scripts/
│   ├── run_wenxin_pipeline.py
│   └── probe_*.py
│
└── README.md
```

## 5. 环境要求

推荐环境：

```text
Python 3.11+
Google Chrome
Playwright
```

首先安装项目依赖：

```powershell
pip install -r requirements.txt
```

并安装 Playwright：

```powershell
playwright install chromium
```

系统默认通过 Chrome DevTools Protocol 连接：

```text
http://127.0.0.1:9222
```

运行 Pipeline 前，需要保证：

* Chrome 已通过 remote debugging 启动
* 9222 端口可访问
* 浏览器已经登录百度文心助手
* 文心网页可以正常发送问题

## 6. 正式运行

推荐使用统一入口：

```powershell
python -m scripts.run_wenxin_pipeline
```

系统会显示：

```text
请选择采集产品：

1. 鸿茅药酒
2. 天益寿气血固本

Q. 退出

请输入选项 [1/2/Q]:
```

选择产品后系统自动执行：

```text
读取题库
→ 创建 Batch
→ 连接 Chrome CDP
→ 批量采集
→ 保存 Checkpoint
→ GEO 标准映射
→ 导出数据包
→ Verify
→ ZIP
→ 最终汇总
```

## 7. 命令行运行

直接指定产品：

```powershell
python -m scripts.run_wenxin_pipeline --product hongmao
```

或：

```powershell
python -m scripts.run_wenxin_pipeline --product tianyishou
```

## 8. 断点续跑

每完成一道任务，系统都会立即保存 Checkpoint。

目录结构：

```text
output/checkpoints/<batch_id>/
├── batch_meta.json
└── results/
    ├── Q001_quick.json
    ├── Q002_quick.json
    └── ...
```

如果浏览器、网络或程序在中途异常退出，可以使用原来的 `batch_id` 恢复：

```powershell
python -m scripts.run_wenxin_pipeline `
    --product hongmao `
    --batch-id "wenxin_hongmao_yaojiu_xxxxxxxxxxxxxx"
```

恢复时：

```text
SUCCESS 任务
→ 直接读取 Checkpoint
→ 不重复向文心发送问题

FAILED / 未完成任务
→ 重新执行
```

完整成功后继续自动生成 GEO 标准包。

## 9. 分段测试

支持通过：

```text
--limit
```

限制本轮运行任务数量。

例如：

```powershell
python -m scripts.run_wenxin_pipeline `
    --product hongmao `
    --limit 3
```

此时系统只完成前三道任务并保存 Checkpoint，不生成最终标准包。

之后使用相同 `batch_id` 恢复即可继续剩余任务。

## 10. GEO 标准包

完整批次成功后输出：

```text
output/package/<batch_id>/
├── manifest.json
├── tasks.jsonl
├── answers.jsonl
├── sources.jsonl
└── checksums.json
```

同时生成：

```text
output/package/<batch_id>.zip
```

ZIP 根目录严格包含：

```text
manifest.json
tasks.jsonl
answers.jsonl
sources.jsonl
checksums.json
```

不包含额外父目录或临时文件。

## 11. 数据关系

标准数据关系为：

```text
task_id
   ↓
answer_id
   ↓
occurrence_id
```

分别对应：

```text
Task
Answer
Source Occurrence
```

ID 使用稳定哈希生成，避免直接依赖网页临时对象。

## 12. Checksum

系统对以下业务文件生成 SHA-256：

```text
manifest.json
tasks.jsonl
answers.jsonl
sources.jsonl
```

并写入：

```text
checksums.json
```

Verifier 会重新计算文件 SHA-256，并与 `checksums.json` 对比。

校验失败时标准包不会被认为通过。

## 13. Package Verify

Verifier 会检查：

* 标准文件是否完整
* JSON / JSONL 是否合法
* schema_version
* geo_batch_version
* platform_code
* task 数量
* answer 数量
* source 数量
* task_id 唯一性
* answer_id 唯一性
* occurrence_id 唯一性
* Task → Answer 引用关系
* Answer → Source 引用关系
* question_id 一致性
* mode_code 一致性
* source_count_raw 一致性
* SHA-256 完整性
* ZIP 文件结构

只有全部通过后才输出：

```text
WENXIN GEO PIPELINE: PASS
```

## 14. 当前验证结果

### 鸿茅药酒

真实环境验证：

```text
Runnable Tasks: 8
Success: 8
Failed: 0
```

并完成：

```text
Directory Verify: PASS
ZIP Verify: PASS
```

### 天益寿气血固本

真实环境验证：

```text
Runnable Tasks: 8
Success: 8
Failed: 0
```

并完成：

```text
Directory Verify: PASS
ZIP Verify: PASS
```

### 断点续跑

已验证真实场景：

```text
第一次执行：
Q001 - Q003

第二次执行：
恢复 Q001 - Q003
继续 Q004 - Q008
```

前三个成功任务没有重新向文心发送请求。

最终：

```text
8 / 8 SUCCESS
Directory Verify: PASS
ZIP Verify: PASS
```

### Capacity

已执行连续采集探测：

```text
Attempted: 4
Success: 4
Failed: 0
Risk Detected: 0
```

此外，产品批量测试中已多次完成连续 8 个 quick 任务。

因此目前可以确认：

> 在已测试的真实环境和请求节奏下，文心助手连续批量采集能够稳定运行，暂未观察到明显网页级限流、验证码或访问限制。

该结果仅代表当前测试范围，不代表百度官方未公开的最大请求频率或调用上限。

## 15. 风控策略

系统采用保守采集策略：

* 页面操作间加入随机缓冲
* 批量任务之间加入间隔
* 不进行高频并发请求
* 不尝试绕过验证码
* 不尝试绕过登录验证
* 检测疑似限流或风控提示
* 出现异常时停止或保存 Checkpoint
* 后续通过原 Batch 恢复

Capacity Probe 仅用于观察当前环境下的稳定性，不用于探测或绕过平台安全限制。

## 16. 当前限制

目前已知限制：

1. 仅正式支持 GEO `quick` 模式。
2. `expert` 尚未找到与文心网页严格等价的回答模式。
3. 依赖有效的百度登录态。
4. 网页 DOM 改版后 Selector 可能需要更新。
5. 当前基于浏览器 UI 自动化，而非官方 API。
6. 最大安全连续采集量尚未进行大规模压力测试。
7. 当前不对百度未公开的请求限制做假设。

## 17. 当前版本

```text
Collector Version: 0.1.0
Schema Version: geo_package_v1
GEO Batch Version: geo_batch_v1
Platform Code: wenxin
Platform Name: 百度文心助手
```

## 18. 项目状态

当前核心采集链路已经完成真实环境验证：

```text
CSV
→ Wenxin
→ Answer
→ Sources
→ Batch
→ Checkpoint
→ Resume
→ GEO Package
→ SHA-256
→ Verify
→ ZIP
```

项目已进入 v1.0 收尾阶段。
