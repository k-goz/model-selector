# 每周价格校验爬取任务

## 任务概述

每周一次，用浏览器工具打开5个SPA定价页，读取最新价格，更新 generate.py 中硬编码映射，提交推送。

## 需要爬取的5个平台

| # | 平台 | 定价页URL | 对应函数 | generate.py 行号 |
|---|---|---|---|---|
| 1 | 智谱AI | https://bigmodel.cn/pricing | `zp()` | 765 |
| 2 | 火山引擎 | https://www.volcengine.com/product/doubao | `vp()` | 786 |
| 3 | 腾讯混元 | https://cloud.tencent.com/document/product/1729 | `tp()` | 925 |
| 4 | 讯飞星火 | https://xinghuo.xfyun.cn/sparkapi | `xp()` | 944 |
| 5 | 百度文心 | https://qianfan.baidubce.com/pricing | `bp()` | 817 |

## 执行步骤

### 第1步：依次打开5个定价页，读取价格

对每个平台：

1. 用浏览器工具打开定价页URL
2. 等页面完全加载（SPA需要几秒）
3. 找到价格表格，记录每个模型的 **输入价格** 和 **输出价格**（单位：CNY/百万token）
4. 将读取到的价格整理成如下格式：

```
## 智谱AI 价格（来源：https://bigmodel.cn/pricing）
| 模型 | 输入价格(¥/M tokens) | 输出价格(¥/M tokens) |
|---|---|---|
| glm-5 | 6 | 22 |
| glm-4.7 | 2 | 8 |
| ... | ... | ... |
```

### 第2步：对比现有硬编码，找出变化

对每个平台，对比刚读取的官方价格与 generate.py 中对应函数的硬编码值：

- 价格相同的 → 跳过
- 价格不同的 → 记录变化（旧值→新值）
- 官网有但硬编码没有的新模型 → 记录为新增

输出变化汇总：
```
## 价格变化汇总
### 智谱AI
- glm-5: 输入 6→4 (-33%), 输出 22→16 (-27%)
- glm-4.7: 无变化

### 火山引擎
- doubao-1.5-pro-32k: 输入 0.5→0.3 (-40%), 输出 2→1.5 (-25%)
```

### 第3步：更新 generate.py

对每个有变化的模型，修改对应函数中的元组值。

**修改规则**：
- 只改价格数字（元组的前2个元素），不改上下文、标签、场景
- 如果是新增模型，在字典末尾添加一行，格式与现有行一致
- 修改后在函数的文档字符串中更新日期

### 第4步：更新 ground_truth.json

对 ground_truth.json 中受影响的模型，更新 input/output 值和 updated 日期。

### 第5步：验证

1. 运行 `python3 -c "import py_compile; py_compile.compile('generate.py', doraise=True)"` 验证语法
2. 运行 `python3 verify_ground_truth.py` 验证 Ground Truth 断言
3. 如果断言失败，检查是否修改正确

### 第6步：提交

```
git add generate.py ground_truth.json
git commit -m "fix: 周度价格校验更新 $(date +%Y-%m-%d)"
git push
```

## 各平台硬编码当前值（供对比）

### 智谱AI zp()
```python
"glm-5":         (6, 22, ...)    # 旗舰
"glm-5-turbo":   (5, 22, ...)    # 高性能
"glm-5.1":       (8, 24, ...)    # 旗舰
"glm-4.7":       (2, 8, ...)     # 主力
"glm-4.7-flashx":(0.5, 3, ...)   # 快速
"glm-4.7-flash": (0, 0, ...)     # 免费
"glm-4-plus":    (5, 5, ...)     # 旗舰降价90%
"glm-5v-turbo":  (5, 5, ...)     # 视觉旗舰
"glm-z1-air":    (0.5, 2, ...)   # 推理便宜
"glm-4.5":       (2, 8, ...)     # 主力
"glm-4.5-air":   (0.5, 3, ...)   # 轻量
"glm-4.6":       (2, 8, ...)     # 主力
```

### 火山引擎 vp()
```python
"doubao-1.6-pro-32k":    (0.8, 8, ...)   # 旗舰
"doubao-1.5-pro-32k":   (0.5, 2, ...)   # 主力性价比
"doubao-1.5-pro-128k":  (5, 5, ...)     # 长上下文
"doubao-lite-32k":      (0.15, 0.6, ...) # 极便宜
"doubao-1.5-lite-32k":  (0.15, 0.6, ...) # 极便宜
"doubao-vision":        (3, 3, ...)      # 视觉
"doubao-coder":         (2, 8, ...)      # 代码
"doubao-seed-1.6":      (0.8, 8, ...)   # 旗舰
"doubao-seed-1.6-flash":(0.8, 0.8, ...) # 快速
"doubao-seed-1.6-vision":(3, 3, ...)    # 视觉旗舰
"doubao-seed-1.6-thinking":(4, 16, ...) # 推理旗舰
"doubao-seed-2.0-pro":  (1, 4, ...)     # 旗舰最新版
"doubao-seed-2.0-mini": (0.8, 2, ...)   # 轻量
"doubao-smart-router":  (0.8, 2, ...)   # 智能路由
```

### 腾讯混元 tp()
```python
"hunyuan-turbos":      (0.8, 2, ...)   # 快速便宜
"hunyuan-turbo":       (1, 4, ...)     # 主力
"hunyuan-pro":         (4, 16, ...)    # 旗舰
"hunyuan-large":       (4, 16, ...)    # 旗舰长上下文
"hunyuan-lite":        (0, 0, ...)     # 免费
"hunyuan-standard":    (0.8, 2, ...)   # 性价比
"hunyuan-standard-vision": (2, 2, ...) # 视觉
"hunyuan-vision":      (4, 4, ...)     # 视觉旗舰
"hunyuan-coder":       (2, 8, ...)     # 代码
"hunyuan-t1":          (1, 4, ...)     # 推理旗舰
"hunyuan-turbos-vision": (1, 1, ...)   # 视觉便宜
```

### 讯飞星火 xp()
```python
"generalv3.5":        (2, 8, ...)     # 主力
"generalv3":          (1.5, 5, ...)   # 性价比
"4.0Ultra":           (5, 20, ...)    # 旗舰
"generalv2":          (0.5, 1.5, ...) # 便宜
"spark-lite":         (0, 0, ...)     # 免费
"generalv3.5-vision": (2, 8, ...)     # 视觉
```

### 百度文心 bp()（主要模型）
```python
"ernie-5.0":    (8, 24, ...)   # 旗舰
"ernie-4.5":    (8, 24, ...)   # 旗舰
"ernie-4.5-turbo": (4, 12, ...) # 主力
"ernie-4.0":    (120, 120, ...) # 旗舰(老)
"ernie-x1":     (4, 16, ...)   # 推理旗舰
"ernie-3.5":    (12, 12, ...)  # 主力
"ernie-speed-pro": (12, 12, ...) # 快速
"ernie-speed":  (8, 8, ...)    # 快速
"ernie-lite-pro": (8, 8, ...)  # 便宜
"ernie-lite":   (4, 4, ...)    # 极便宜
```

## 注意事项

1. **只改价格数字**，不要改上下文长度、标签、场景等字段
2. **单位必须是 CNY/百万token**，与 generate.py 中一致。如果官网显示的单位不同（如 CNY/千token），需要换算
3. **如果有模型下线或价格大幅上涨（>50%）**，不要直接改，先在输出中标注"[需确认]"
4. **如果页面打不开或价格表格找不到**，记录"[爬取失败]"，不要修改任何代码
5. **每次只改有变化的模型**，没变化的不要动
