# 裁图与排障

## 提案是怎么算出来的

`pdf_figures.py` 对每页：
1. 用行级文本找图注。默认要求编号后带标点（`Figure 4.` / `Fig. 4:` / `Figure 4 |`），
   这样正文里的「Figure 4 shows…」不会被误判。期刊不用标点时加 `--loose`。
2. 图注向上找裁切区。优先用**内嵌位图的 bbox 并集**（过滤掉落在页面外的异常 bbox，
   某些期刊的图会报出负坐标）；没有位图（纯矢量图）时退回到「上方最后一条正文行的下沿」。
3. 同一页多个图注按 y 排序，后一个图的上界取前一个图注的下沿，避免串图。

输出 `basis` 字段：`images` 可信度高；`prose` / `gap` 需要目视确认；
`TOO-SMALL` 表示提案高度不足，几乎一定是误判，必须人工给 rect。

## 标准工作流

```bash
python scripts/pdf_figures.py paper.pdf --list                 # 看提案
python scripts/pdf_figures.py paper.pdf --out figs --page-shots  # 裁图 + 整页预览
```

用 Read 打开 `figs/pages/pageNN.png` 与 `figs/figNN.png` 对照，确认：
- 图完整，没切掉坐标轴、色标、子图标签；
- 没混入正文行或上一个图；
- 子图 (a)(b) 都在。

不对就单张重裁，坐标从整页预览上量（预览是 110 dpi，PDF 坐标是 pt，
换算：pt = px / 110 * 72）：

```bash
python scripts/pdf_figures.py paper.pdf --out figs --only fig19 \
  --rect fig19=18:90,85,505,177
```

`--rect` 会追加一条 manual 提案；配合 `--only` 只重渲染这一张。

## 常见情况

| 现象 | 原因 | 处理 |
|---|---|---|
| 一张图只裁到一半 | 期刊把每个子图存成独立位图，且有一个 bbox 在页面外被过滤 | 用 `--rect` 手动给并集 |
| 裁出来是空白 | 纯矢量图且上方没有正文行，`gap` 提案落空 | `--page-shots` 目视后 `--rect` |
| 图注匹配数为 0 | 期刊图注无标点，或图注是图片 | `--loose`；仍为 0 则全部 `--rect` |
| 双栏论文串栏 | 图注 x 范围即栏宽，通常正确；跨栏大图会只裁到一栏 | `--rect` 给跨栏坐标 |
| 表格要一起裁 | 默认只裁 figure | `--kind both`，表格 id 为 `tabNN` |
| 扫描版 PDF 无文本 | `pdf_text.py` 会报 near-empty 页 | 先 OCR（如 ocrmypdf），再跑本链路 |

## 体积预算

220 dpi 裁出的 PNG，云图类单张可达 1.5 MB。`inline_figs.py` 默认
`--max-width 1000 --quality 82 --format auto`：大于 100 KB 或宽于 700 px 转 JPEG，
其余保留 PNG 以保住线稿锐度。20 张图的成品约 2–3 MB，可接受。
线稿为主、追求锐度时加 `--format png`；体积优先时 `--max-width 860 --quality 76`。

## 无头截图

`shoot.py` 在源文件旁写 `*._shot.html` 临时副本，截完即删；副本放同目录是为了让
尚未内联的相对路径图片仍能解析。

机制（两个无头坑的对策）：
- 无头 `--screenshot` **不重绘初始视口外的内容**，直接滚到锚点会截出空白。
  副本改为把 `body` 上移锚点偏移量（按真实滚动钳制），让目标留在视口内。
- 平移后 sticky 导航不会钉顶，副本把 `.sectionnav` 设为 `fixed` 复现真实滚动态。
- 同时注入 `scroll-behavior:auto` 与禁用动画，保证确定性。

输出文件名带视口后缀：`p02_1400x900.png`，桌面与移动端互不覆盖。
近乎纯色的截图会报 `WARN looks blank`。

布局扫一遍：`--at p01,s3,p20,overview --size 1400x2200`。
窄屏：`--size 600x2400`。**低于约 500px 的请求会被无头窗口钳制布局宽度**，
420px 截出来会横向裁切；手机宽度验收改用 browser-use MCP 的移动模拟。
交互（lightbox 点击、Esc 关闭、导航 active 态）CLI 截不了，同样用 MCP：
navigate_page → click `.fig-frame` → take_screenshot → press_key Escape。