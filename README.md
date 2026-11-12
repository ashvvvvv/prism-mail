# PrismMail · 大肥鱼主题归档 (`archive/deepseek`)

本分支独立封存 **PrismMail · 棱镜邮局** 的「大肥鱼二次元主题」（`frontend-deepseek`），与 `main` 主分支上的正式运行代码完全隔离。

## 包含内容

- `frontend-deepseek/src/`：完整 Vue 3 + Pinia + Tailwind 主题组件与深浅色样式源码
- `frontend-deepseek/public/`：全部 8 张定制插画与 Q 版素材原图
  - `deepseek-hero-day.jpg` / `deepseek-hero-night.jpg` / `deepseek-hero.jpg`
  - `deepseek-portrait-letter.jpg`
  - `deepseek-chibi-hug.png` / `deepseek-chibi-rice.png` / `deepseek-chibi-think.png` / `deepseek-chibi.jpg`

## 本地预览或恢复构建

```bash
cd frontend-deepseek
npm install
npm run dev    # 本地开发预览
npm run build  # 构建静态产物至 dist/
```
