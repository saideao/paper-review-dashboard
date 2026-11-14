#!/usr/bin/env python3
"""把审稿数据装进固定的页面模板，生成 review.html 或 cross_review.html。

用法：
    python3 build_review.py review.json                 # 写出 review.html（数据里有 merged 就写 cross_review.html）
    python3 build_review.py review.json -o 输出.html
    python3 build_review.py 旧的review.html -o 新.html   # 把旧页面里的数据换到新模板上

输入是一个 JSON 文件：{"summary": {...}, "issues": [...], "claims": [...], "typos": [...]}，
交叉汇总把 issues 换成 merged。也可以直接给一份带数据块的 HTML。
只用 Python 标准库。页面的样式和交互都在 templates/dashboard.html 里，这个脚本只填数据。
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "templates" / "dashboard.html"
SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.S | re.I)
KEYS = ["summary", "issues", "merged", "claims", "typos"]


def load(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if re.search(r"<script[^>]+application/json", text, re.I):
        data = {}
        for attrs, body in SCRIPT_RE.findall(text):
            if not re.search(r"application/json", attrs, re.I):
                continue
            m = re.search(r"""id\s*=\s*["']([^"']+)["']""", attrs)
            if m:
                data[m.group(1)] = json.loads(body)
        return data
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < 0:
        sys.exit(f"{path} 里没找到 JSON")
    return json.loads(text[a:b + 1])


def block(key: str, value) -> str:
    body = json.dumps(value, ensure_ascii=False, indent=1)
    body = body.replace("</", "<\\/").replace("<!--", "\\u003c!--")
    return f'<script type="application/json" id="{key}">{body}</script>'


def main() -> None:
    args = sys.argv[1:]
    out = None
    if "-o" in args:
        i = args.index("-o")
        out = pathlib.Path(args[i + 1])
        del args[i:i + 2]
    if len(args) != 1:
        sys.exit(__doc__)
    src = pathlib.Path(args[0])
    if not src.is_file():
        sys.exit(f"找不到文件：{src}")
    if not TEMPLATE.is_file():
        sys.exit(f"找不到模板：{TEMPLATE}")

    data = load(src)
    cross = bool(data.get("merged"))
    main_key = "merged" if cross else "issues"
    if not isinstance(data.get("summary"), dict) or not data.get(main_key):
        sys.exit("数据不完整：需要 summary，以及 issues（审稿）或 merged（交叉汇总）")

    html = TEMPLATE.read_text(encoding="utf-8")
    for key in KEYS:
        pat = re.compile(r'<script type="application/json" id="%s">.*?</script>\n?' % key, re.S)
        if not pat.search(html):
            sys.exit(f"模板里缺数据块 {key}")
        if key in ("issues", "merged") and key != main_key:
            html = pat.sub("", html, count=1)          # 只留用到的那一块，别的工具靠它分辨类型
        else:
            value = data.get(key, {} if key == "summary" else [])
            html = pat.sub(lambda _: block(key, value) + "\n", html, count=1)

    if out is None:
        out = src.with_name("cross_review.html" if cross else "review.html")
        if out.resolve() == src.resolve():
            sys.exit("输出会覆盖输入，请用 -o 指定另一个文件名")
    out.write_text(html, encoding="utf-8")
    n = len(data[main_key])
    kind = "交叉汇总" if cross else "导入的审稿意见" if data["summary"].get("mode") == "import" else "审稿"
    print(f"已写出 {out}（{kind}，{n} 条意见，"
          f"声明 {len(data.get('claims') or [])} 条，文字小错 {len(data.get('typos') or [])} 处）")


if __name__ == "__main__":
    main()
