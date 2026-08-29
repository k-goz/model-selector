# 生产部署事实来源

更新时间：2026-08-29

## 唯一正式生产路径

`main` 分支是发布分支，Vercel 项目 `ai-model-selector` 是唯一生产托管，`https://model.ai-selector.top` 是唯一对外验收域名。

```text
refresh-model-data.yml
        ↓
update-models.yml（采集、测试、生成、门禁）
        ↓
自动提交生成产物到 main
        ↓
Vercel Git Integration
        ↓
https://model.ai-selector.top
        ↓
deployment-health.yml
```

Vercel 备用 deployment URL 只用于诊断，不作为第二个生产事实来源。健康检查、README 和验收报告统一以自定义域名为准。

## 必须发布的静态产物

- `index.html`
- `en/index.html`
- `models_data.json`
- `ping_analysis.json`
- 页面中内联的 `assets/styles.css` 与 `assets/app.js` 生成结果
- 站点引用的其他受版本控制静态页面和资源

Vercel 当前 `outputDirectory` 为仓库根目录，`vercel.json` 不执行额外构建。生成器修改后必须先重新生成并通过门禁，不能只发布单个 HTML 文件。

## 已停用路径

旧 `Deploy to Aliyun` 仅上传 `index.html`，遗漏英文页、JSON、JS/CSS 生成结果和测速数据，无法形成一致部署。本阶段删除该工作流；若未来需要灾备，必须以完整、原子化、可健康检查的镜像方案通过 ADR 重新引入。

## 发布与回滚

正常发布：通过受测试的分支合并到 `main`，由 Vercel Git Integration 自动生成 Production deployment。

紧急回滚优先使用 Vercel 对上一条已验证 deployment 执行 rollback/promote；代码回滚点为 Git 标签 `phase16-baseline-20260829`。数据回滚后仍必须明确显示旧数据年龄，不能伪造新的采集时间。

## 生产验收命令

```bash
python3 check_deployment.py \
  --base-url https://model.ai-selector.top \
  --max-age-hours 2
```

同时核对：Vercel deployment 的 Git commit、线上 `models_data.json.meta.updated_at`、中英文页面显示时间、模型数量与当前 `main` 生成产物一致。
