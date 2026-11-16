---
name: paper-reading
description: 把学术论文 PDF 做成单文件双栏精读批注 HTML：左栏原文+中文译文对照，每段按五维只标最关键一处高亮，右栏逐段批注（段落功能/逻辑角色/技巧与漏洞/标注），原刊插图裁切内联、点击放大，底部论证结构总览（问题→论点→证据→反驳→结论、一句话主张、最强/最弱处）。当用户要求论文精读网页、双栏批注、中英对照 HTML、论证结构分析页、把论文做成可离线打开的网页、annotated paper reader 时使用。
argument-hint: <paper.pdf> [输出目录]
---

# 论文双栏批注 HTML

## Overview

输入一篇论文 PDF，产出一个可离线打开的单文件 HTML：双语对照 + 逐段论证批注 +
内联原图 + 论证总览。版式固定（深海军蓝顶栏、米白纸张底、Lora 正文 + IBM Plex Sans 界面），
智力工作在批注与总览，不在排版。

## 产物与目录

在论文所在目录（或用户指定目录）工作，最终只留一个 `<paper>_annotated.html`。
过程产物：`_work/`（文本）、`figs/`（裁图）、`_partN.html`（分片）、`_shots/`（截图），
**交付前全部删除**。

## 工作流

### 1 提取

```bash
python scripts/pdf_text.py paper.pdf --out _work
python scripts/pdf_figures.py paper.pdf --list
```

读 `_work/text.txt` 全文。near-empty 页警告意味着扫描版，先 OCR 再继续。
图注提案的判读与重裁见 [references/figure-cropping.md](references/figure-cropping.md)。

### 2 裁图并目视

```bash
python scripts/pdf_figures.py paper.pdf --out figs --page-shots
```

用 Read 抽查至少 3 张 `figs/figNN.png`（含一张多子图、一张最矮的），
对照 `figs/pages/pageNN.png` 确认完整、无串图。**图注说明对着图写，不照抄正文对图的描述。**

### 3 规划

先定五件事再动笔：
- 章节划分与导航项（含摘要、尾件、参考文献、总览、复现档案）；
- 全局段号 ¶ 01…¶ NN 与每段主维度（判定规则见 [references/annotation-guide.md](references/annotation-guide.md)）；
- **全文照录清单**：正文自然段（跨页断段合并）、图表原始英文题注、刊头元信息、尾件三段、
  参考文献全录。缺任何一项就是摘要不是精读，细则见 annotation-guide 第 1 节；
- 每段挂哪几张图（图放在该段 `.zh` 之后；一组相关云图用 `fig-grid`）；
  每段的**唯一**高亮句：先按主维度定颜色，再从该段挑出删掉最可惜的一句，颜色必须与主维度同色；
- **哪些式号与表号必须呈现**：把正文里引用的 `式(N)` / `表 N` 全部列出来，逐条分配到段。
  原成品曾把五张表和全部显示公式整段丢掉，这一步就是防这个。
- **是否要复现档案**：论文含数值仿真（子程序、有限元、显式流程）时默认要，
  按 blocks.html 的 REPRO 块填九段式档案；纯理论或实验类论文把 `{{REPRO}}` 置空。

### 4 分片写作

不要一次 Write 整个 HTML。按章节写 `_part1.html`、`_part2.html`…，
每片只含 `section` 块；从 [assets/blocks.html](assets/blocks.html) 复制 ROW / FIGURE /
FIG_GRID / EQUATION / TABLE 块填充。图片一律写 `<img data-fig="figNN" alt="…">`，
不要手写 base64；公式写 `.eq` + `data-eq`，表格写 `.tbl` + `data-tbl`。

写作纪律（摘要）：
- 原文逐字保留，只合并排版断行；转义 `& < >`；下标上标用 `<sub>/<sup>`。
- 译文意译、不加高亮、术语全文一致；引用编号照抄，错误在批注里指出。
- 每段高亮最多 1 处，颜色＝该段主维度；批注末尾用 `标注` 栏逐字引用该片段。
  批注三栏都要落到具体段号或表/式编号，禁止空话。
- 数值回表格核对；原文歧义照抄并披露，不无声改写；图中未标注的量不猜。
- 显示公式用纯 CSS（`.frac` / `.brd` / `.op`），不引 MathJax，保住单文件离线。

### 5 装配

读 [assets/skeleton.html](assets/skeleton.html)，替换全部 `{{TOKEN}}`：
`{{SECTIONS}}` 处拼接各 `_partN.html` 内容，`{{NAV_ITEMS}}`、`{{FLOW_STEPS}}`、
`{{DUO_BOXES}}` 用 blocks.html 对应块填充。

`{{REPRO}}` 填复现档案（blocks.html 的 REPRO 块），规则：
- 八张 `data-rp` 卡片齐备（geometry / mesh / material / umat / solve / fail / results / env），
  每卡至少两条 dt/dd；
- `.rp-algo` 逐步写清子程序**每个增量步做什么**——这是复现时最容易缺的一环；
- `.rp-files` 列本地已有算例的文件、作用与可直接粘贴的命令；没有本地算例就删掉该小节；
- `.rp-gaps` 汇总「原文没说但复现必须知道」的条目，已解决的加 `class="resolved"`；
- 卡片内缺的信息要同时出现在该卡 `.gap` 与 `.rp-gaps`；
- 主公式用 `<a href="#pNN">式 (N)</a>` 回链正文，数值指向正文表号，都不重复抄；
- 每卡尽量配图：缩略图（`.rp-figs`）从正文已内联的 data URI 取、重编到 ~620px，
  其余用 `.rp-links` 指路；链接 id 先查出图表真实所在段，不要猜；
- 本地有算例却没留存结果图时，用其结果数据自绘一张放进 results 卡，图注写明「非论文图」。

配图选择、放大读数、自绘图的细则见
[references/annotation-guide.md](references/annotation-guide.md) 第 6 节。

不需要复现档案时把 `{{REPRO}}` 替换为空串并去掉 `#repro` 导航项。
写出 `<paper>_annotated.html`。

### 6 内联与结构校验

```bash
python scripts/inline_figs.py <paper>_annotated.html --figs figs
python scripts/check_html.py <paper>_annotated.html --strict-refs
```

`check_html.py` 校验标签闭合、段号左右配对、每 row 恰一个 note、每 row ≤1 处高亮且颜色与
批注维度一致、`标注` 栏确实引用了该片段、导航锚点可达、
mark/note class 合法、无残留占位符，并打印「公式 已呈现/被引用」「表格 已呈现/被引用」。
存在 `.repro` 时另查八张卡齐不齐、每卡至少两条定义、算法步骤 ≥3、缺口清单非空。
任何 FAIL 必须修掉再往下走；`--strict-refs` 下引用了却没呈现的式号/表号直接算 FAIL。

### 7 浏览器验收

```bash
python scripts/shoot.py <paper>_annotated.html --at p01,s3,overview --size 1400x2200 --out _shots
python scripts/shoot.py <paper>_annotated.html --at p01,overview --size 600x2400 --out _shots
```

用 Read 看截图：双栏对齐、译文块与批注卡配色、图不溢出、窄屏单栏。
手机宽度（<500px）与交互（lightbox 点击、Esc、导航 active 态）用 browser-use MCP 验证，
无头 CLI 在窄视口会钳制布局宽度。只看代码不算验收。

### 8 清理与交付

删除 `_work/`、`figs/`、`_part*.html`、`_shots/`、`*._shot.html`。
交付时给出文件链接与一句话内容摘要（段数、批注数、图数），并主动列出批注中发现的
可核实疑点。不写中间报告 md。

## 变体

- 非英文论文：左栏原文语言不变，译文语言按用户要求；`colhead` 文字相应改。
- 无图论文：跳过 2、6 的内联部分，`check_html.py` 仍要跑。
- 只要翻译不要批注：仍用本模板，但 note 三栏改为「术语 / 句式 / 背景」，并在交付说明里讲明偏离。
- 表格也要精读：`pdf_figures.py --kind both`，表格 id 为 `tabNN`。

## Resources

- `scripts/pdf_text.py` — 逐页文本提取，UTF-8 安全，ligature 归一，扫描页告警
- `scripts/pdf_figures.py` — 图注定位 + 区域裁切，`--list/--rect/--only/--page-shots/--loose`
- `scripts/inline_figs.py` — 图片转 base64 内联，自动 JPEG/PNG 与限宽，残留引用检查
- `scripts/check_html.py` — 结构校验器，FAIL 即退出码 1
- `scripts/shoot.py` — Edge/Chrome 无头锚点截图，自动禁用平滑滚动
- `assets/skeleton.html` — 整页骨架（CSS + lightbox + 导航脚本 + 占位符）
- `assets/blocks.html` — 可复制块：NAV_ITEM / SECTION / ROW / FIGURE / FIG_GRID / EQUATION / TABLE / REPRO / FLOW_STEP / DUO_BOX
- `references/annotation-guide.md` — 五维判定、批注写法、译文规则、证据纪律、疑点清单
- `references/figure-cropping.md` — 裁图提案原理、重裁工作流、排障表、体积预算