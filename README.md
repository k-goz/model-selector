# 🤖 模型选择器

> 实时拉取 OpenRouter 价格，按场景推荐 AI 模型，一键复制 `/model` 切换命令。

**👉 **访问在线版本：** https://model-selector-sigma.vercel.app

---

## 功能特点

- 🌍 **实时价格** — 直接调 OpenRouter API，无需手动查价
- 🏷️ **7 大场景** — 日常对话 / 写作文案 / 编程代码 / 深度推理 / 视觉图片 / 深度研究 / 免费模型
- 💰 **价格可视化** — 绿色=免费，蓝色=<$0.5，黄色=$0.5-3，红色=>$3
- 📋 **一键复制** — 点任意卡片直接复制 `/model provider/model-id` 命令
- 🔍 **实时搜索** — 输入关键词即时过滤所有模型
- ⚡ **无需注册** — 打开即用，完全免费

---

## 使用方法

### 在线使用（推荐）
直接访问 👉 **https://model-selector-sigma.vercel.app**

### 本地使用
```bash
# 克隆仓库
git clone https://github.com/k-goz/model-selector.git
# 用浏览器打开
open index.html
```

### 更新价格数据
```bash
python3 generate.py   # 需要先安装 python3
```

---

## 部署到 Vercel（免费）

### 方法一：导入 GitHub（推荐）

1. 访问 [vercel.com/new](https://vercel.com/new)
2. 点击 "Import Git Repository"
3. 选择 `k-goz/model-selector`（或你自己的 fork）
4. Framework Preset 选 **Other**
5. 点击 Deploy，30 秒完成！
6. 获得 `https://你的名字.vercel.app` 永久链接

### 方法二：命令行部署
```bash
npm i -g vercel
cd model-selector
vercel --prod
```

---

## 项目结构

```
model-selector/
├── index.html      # 主页面（直接用浏览器打开即可）
├── README.md        # 项目说明
└── generate.py      # 价格数据生成脚本（可选）
```

---

## 技术细节

- **数据来源**：OpenRouter 公开 API `https://openrouter.ai/api/v1/models`
- **无需 API Key**：公共接口，任何人都可以直接调用
- **前端渲染**：纯 HTML/CSS/JS，无后端依赖
- **模型数量**：精选 32 个常用模型，覆盖 OpenRouter 全部 349+ 模型

---

## 许可证

MIT License — 随意使用、修改、分发。

---

* 数据来源：[OpenRouter](https://openrouter.ai) · 模型选择器非官方工具
