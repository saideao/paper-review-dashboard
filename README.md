# 论文修改看板（paper-review-dashboard）：论文审稿，出一份能勾选的修改清单

给它一篇论文（PDF 或 LaTeX 源码），它会当一个不友好的审稿人，分六遍查：

1. 声明和证据对不对得上；
2. 方法和实验；
3. 相关工作和引用；
4. 写作和结构；
5. 文字小错；
6. 格式和匿名。

每条意见都写清楚四件事：审稿人会怎么攻击、为什么是问题、修改思路、最小修复。最小修复用改前 / 改后对照给出。原文逐字引用，并带上页码。

结果是一个 HTML 文件，双击就能打开：总判断和维度打分、统计卡片、按类别分组的修改卡片、声明—证据表、文字小错表，左侧大纲可以跳转，每条都能勾选"已处理"。

页面的样子是固定的：模型只负责写数据，排版和交互都在一份现成的模板里，所以换哪个模型来审，出来的页面都一样。想先看看效果，打开 `skill/paper-review-dashboard/examples/demo_review.html` 和 `demo_cross.html`（一篇虚构论文的示例）。

它不绑定任何一家的 agent 或模型。Claude Code、Codex、Cursor 这类 agent，ChatGPT、Claude、Gemini 这类网页聊天，都能用。

## 两种用法

| 用法 | 做什么 | 得到什么 |
|---|---|---|
| **审稿（默认）** | 当前这个模型审一遍 | `review.html` |
| **交叉汇总** | 把两份或更多份审稿意见交给一个模型，由它当领域主席逐条核对，合并出共识、部分共识、分歧、仅 A / 仅 B……、无法判断 | `cross_review.html` |

想要多个模型交叉审稿的话，分三步：

1. 在几个不同的 agent 或聊天窗口里各审一遍，得到几份 `review.html`，最好来自不同公司的模型；
2. 在任意一个 agent 里，把论文和这几份 `review.html` 交给它做交叉汇总；
3. 先改共识，分歧的由你拍板。分歧条目会写出分歧点和"怎么判断谁对"。

交叉汇总的页面可以给每条选"采纳 / 不采纳 / 待定"，再一键导出成 Markdown，贴回给 AI，让它只改你采纳的条目。

## 在 agent 里用

把 `skill/paper-review-dashboard/` 装成你那个 agent 的 skill。以 Claude Code 为例：

```bash
ln -s "$(pwd)/skill/paper-review-dashboard" ~/.claude/skills/paper-review-dashboard
```

装好后，直接说"帮我审一下 paper.pdf，投 ICLR"，它就会审稿、写出 `review.html` 并自检。

有了几份审稿意见之后，说"把 review_1.html 和 review_2.html 交叉汇总一下"，它就会做交叉汇总。

## 在网页聊天里用

1. 把 `skill/paper-review-dashboard/prompts/review.md` 的全文贴进对话，把里面的【会议名】这类占位换成你的，再附上论文。模型会输出一份 JSON。
2. 用浏览器打开 `skill/paper-review-dashboard/templates/dashboard.html`，把 JSON 贴进去，点"生成清单"。
3. 想留一份的话，点页面底部的"保存成一个 HTML 文件"，得到 `review.html`，以后双击就能打开。

装了 Python 的话，也可以把 JSON 存成 `review.json`，运行：

```bash
python3 skill/paper-review-dashboard/scripts/build_review.py review.json
```

交叉汇总一样：在某个对话里贴 `prompts/cross.md`，附上论文和几份 `review.html`（或者几份 JSON），拿到 JSON 后同样贴进模板。

以前用旧版生成的 `review.html` 也能换成新样子：

```bash
python3 skill/paper-review-dashboard/scripts/build_review.py 旧的review.html -o review_new.html
```

想检查一份清单写得全不全，运行（只需要 Python 3）：

```bash
python3 skill/paper-review-dashboard/scripts/check_review.py review.html paper.pdf
```

它会检查数据块、修改思路和最小修复有没有填全，以及原文引用在论文里能逐字找到几条。找 PDF 里的原文需要装 `pdftotext`；给 `.tex` 源码就不需要。

## 参考：几个模型的表现

同一篇 20 页论文，用 Codex 跑，推理强度 xhigh：

| 用法 | 模型 | 用时 | token | 结果 |
|---|---|---|---|---|
| 审稿 | gpt-6.1-terra | 9 分钟 | 11 万 | 29 条意见，引用 28/29 逐字对上 |
| 审稿 | gpt-6-luna | 35 分钟 | 31 万 | 10 条意见，引用 10/10 逐字对上 |
| 交叉汇总 | gpt-6.1-terra | 8 分钟 | 17 万 | 31 条：共识 8、分歧 8、仅一方提出 13 等 |

## 为什么这么设计

- **多个模型、一个主席**：同一个模型审两遍，挑出来的毛病大同小异；换几个模型各审一遍，再逐条核对，能看出哪些问题大家都认、哪些只是一家之言。主席只看到审稿人 A、B、C 的代号，看不到模型名字。提示词里写了"同意不是礼貌"：试跑时，交叉的模型在一条分歧里直接承认了自己第一轮的误判。
- **共识不等于对**：模型之间的意见比它们和人类审稿人的意见更像，所以共识只用来决定先改哪条，不代表那条一定对。只有一家提出的意见没经过别家检验，单独列出。
- **原文逐字引用 + 页码**：引不出原句的意见，常常是模型想象出来的问题。逐字引用也让你能直接搜到出处，自检脚本会逐条核对。
- **先写修改思路，再给最小修复**：你先判断方向对不对，再看具体怎么改。能改一句就不改一段；改前只截一段最短的原文，短到在论文里只能搜到这一处。
- **不许无故叠甲**：给一句话加限定、把话说软，必须写出依据：原文哪里的证据撑不住这句话。
- **模型只写数据，页面用固定模板**：让模型每次从头写整页 HTML，样子不稳定，还要占掉一大截输出。现在模型只按固定格式写 JSON，模板负责渲染；改前 / 改后里哪些词变了，也由页面自己对比高亮。同一份数据可以交给另一个模型交叉汇总，也能被脚本自检。
