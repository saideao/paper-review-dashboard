#!/usr/bin/env python3
"""自检一份审稿清单（review.html 或 cross_review.html，也可以是还没装进模板的 .json）。

用法：
    python3 check_review.py review.html
    python3 check_review.py review.json                # 生成页面之前先查数据
    python3 check_review.py review.html 论文.pdf      # 顺带核对原文引用（需要 pdftotext）
    python3 check_review.py cross_review.html main.tex # LaTeX 源码也行，可以给多个 .tex

检查：JSON 数据块齐不齐、是不是合法 JSON，条目数，修改思路和最小修复有没有填全，
编号有没有重复，声明表里"说过头 / 对不上 / 无证据"的有没有对应卡片，
以及原文引用能不能在论文里逐字找到。只用 Python 标准库，不改任何文件。
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.S | re.I)


def load_blocks(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":      # 还没装进模板的数据文件
        a, b = text.find("{"), text.rfind("}")
        try:
            return json.loads(text[a:b + 1])
        except json.JSONDecodeError as e:
            sys.exit(f"  ✗ {path.name} 不是合法 JSON：{e}")
    data = {}
    for attrs, body in SCRIPT_RE.findall(text):
        if not re.search(r"""type\s*=\s*["']application/json["']""", attrs, re.I):
            continue
        m = re.search(r"""id\s*=\s*["']([^"']+)["']""", attrs)
        key = m.group(1) if m else "?"
        try:
            data[key] = json.loads(body)
        except json.JSONDecodeError as e:
            data[key] = None
            print(f"  ✗ 数据块 {key} 不是合法 JSON：{e}")
    return data


def norm(s) -> str:
    s = str(s).replace("-\n", "").replace("\ufb01", "fi").replace("\ufb02", "fl")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def paper_text(paths) -> str:
    out = []
    for p in paths:
        if p.suffix.lower() == ".pdf":
            if not shutil.which("pdftotext"):
                print("  （没装 pdftotext，跳过原文核对）")
                return ""
            out.append(subprocess.run(["pdftotext", str(p), "-"], capture_output=True, text=True).stdout)
        else:
            t = p.read_text(encoding="utf-8", errors="ignore")
            t = re.sub(r"(?<!\\)%.*", "", t)                                # 注释
            t = re.sub(r"\\(?:emph|textbf|textit|texttt|mathrm|text)\{([^{}]*)\}", r"\1", t)
            out.append(t)
    return norm("\n".join(out))


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    review = pathlib.Path(sys.argv[1])
    sources = [pathlib.Path(p) for p in sys.argv[2:]]
    for p in [review, *sources]:
        if not p.is_file():
            sys.exit(f"找不到文件：{p}")

    print(f"自检 {review.name}")
    data = load_blocks(review)
    cross = bool(data.get("merged"))
    need = ["summary", "merged" if cross else "issues", "claims", "typos"]
    missing = [k for k in need if k not in data]
    print("  类型：" + ("交叉汇总" if cross else "审稿"))
    print("  数据块：" + ("齐全" if not missing else "缺 " + "、".join(missing)))

    paper = paper_text(sources) if sources else ""
    problems = 0

    def quote_ok(q: str) -> bool:
        parts = [x for x in re.split(r"…|\.\.\.|\n", q or "") if len(norm(x)) > 10]
        return all(norm(x) in paper for x in parts)

    main_key = "merged" if cross else "issues"
    items = data.get(main_key) or []
    if items:
        ids = [x.get("id") for x in items]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        no_appr = [x.get("id") for x in items if not x.get("approach")]
        no_fix = [x.get("id") for x in items if not x.get("fixes") and not x.get("needs_author")
                  and x.get("category") not in ("分歧", "无法判断")]  # 交叉汇总里判"不改"的分歧可以没有修复
        prio = {}
        for x in items:
            prio[x.get("priority", "?")] = prio.get(x.get("priority", "?"), 0) + 1
        line = f"  卡片 {len(items)} 条（" + " / ".join(f"{k} {v}" for k, v in sorted(prio.items())) + "）"
        if cross:
            cats = {}
            for x in items:
                cats[x.get("category", "?")] = cats.get(x.get("category", "?"), 0) + 1
            line += "，" + " / ".join(f"{k} {v}" for k, v in cats.items())
        print(line)
        for label, bad in [("编号重复", dup), ("缺修改思路", no_appr), ("既没最小修复也没'需要作者补充'", no_fix)]:
            if bad:
                problems += 1
                print(f"  ✗ {label}：{', '.join(map(str, bad))}")
        if cross:
            bad = [x.get("id") for x in items if x.get("category") == "分歧" and not (x.get("disagreement") and x.get("how_to_decide"))]
            if bad:
                problems += 1
                print(f"  ✗ 分歧条目缺'分歧点'或'怎么判断谁对'：{', '.join(bad)}")
        if paper:
            miss = [x.get("id") for x in items if not quote_ok(x.get("quote"))]
            print(f"  卡片原文逐字对上 {len(items) - len(miss)}/{len(items)}" + (f"，对不上：{', '.join(miss)}" if miss else ""))

    claims = data.get("claims") or []
    if claims:
        v = {}
        for c in claims:
            v[c.get("verdict", "?")] = v.get(c.get("verdict", "?"), 0) + 1
        print(f"  声明 {len(claims)} 条（" + " / ".join(f"{k} {n}" for k, n in v.items()) + "）")
        if not cross:
            ids = {x.get("id") for x in items}
            orphan = [c.get("id") for c in claims if c.get("verdict") in ("说过头", "对不上", "无证据")
                      and not any(i.strip() in ids for i in re.split(r"[,，、\s]+", c.get("issue_id") or "") if i.strip())]
            if orphan:
                problems += 1
                print(f"  ✗ 有问题的声明没有对应卡片：{', '.join(orphan)}")
        if paper:
            ok = sum(1 for c in claims if quote_ok(c.get("claim")))
            print(f"  声明原文逐字对上 {ok}/{len(claims)}")

    typos = data.get("typos") or []
    if typos:
        line = f"  文字小错 {len(typos)} 处"
        if paper:
            miss = [t.get("id") for t in typos if not quote_ok(t.get("quote"))]
            line += f"，原文逐字对上 {len(typos) - len(miss)}/{len(typos)}" + (f"，对不上：{', '.join(miss)}" if miss else "")
        print(line)

    if not sources:
        print("  （没给论文文件，跳过原文核对）")
    if missing or problems:
        print("结论：有问题要补，见上面的 ✗")
        sys.exit(1)
    print("结论：结构完整" + ("；对不上的引用回原文改成逐字原句" if paper else ""))


if __name__ == "__main__":
    main()
