#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
过拟合暴露度审计 —— 模糊层（8-gram 逐行交集）

为什么需要这一层
    精确层只做逐字匹配。包里条目只要被**截短/改写 2–5 字**，整条就躲过去了，
    但在 Test 池眼里它还是同一条规则。三种漏网形态（详见 ../docs/06）：
        A 截尾：dev 结尾多 1 个实义词，包里删掉          ← 精确层无感
        B 换连接：逗号 → 「＋」，字符全变语义不变          ← 精确层无感
        C 删状语：去掉「继续 / 尽快 / 直接」等前缀状语
    所以这里把 dev 语料切成 N-gram，与包内逐行取交集，
    贪心扩展出**最长连续命中片段**并回显 dev 出处。

    注：本脚本的文档**不复现任何 dev 原文** —— 写反过拟合的文档本身也得反过拟合。

dev 真值同样不内嵌，走环境变量：
    export CARERSIM_DEV_TRUTH="/path/to/appendix-g-event-delta-map.md"

用法
    python _overfit_fuzzy.py [目标包目录，默认 .]
"""
import os
import re
import sys
import glob

N = 8  # gram 长度；调小更敏感（容易误报），调大更准（容易漏）

EXCLUDE_DIRS = {".venv", "node_modules", "__pycache__", ".git", "outputs"}
EXCLUDE_SUFFIX = (".zip", ".png", ".jpg", ".pdf", ".xlsx", ".py")


def dev_docs(path):
    txt = open(path, encoding="utf-8").read()
    titles = [t.strip() for t in re.findall(r"^##\s+(.+)$", txt, re.M)]
    opts = [o.strip() for o in re.findall(r"^\s*-\s*«?「?(.+?)」?\**\s*$", txt, re.M)]
    return [d for d in titles + opts if len(d) >= N]


def grams(s, n=N):
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def package_lines(pkg):
    out = []
    for p in glob.glob(os.path.join(pkg, "**", "*"), recursive=True):
        if not os.path.isfile(p) or p.endswith(EXCLUDE_SUFFIX):
            continue
        if any(part in EXCLUDE_DIRS for part in p.replace("\\", "/").split("/")):
            continue
        try:
            body = open(p, encoding="utf-8").read()
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(body.splitlines()):
            if line.strip():
                out.append((p, i + 1, line))
    return out


def main():
    truth = os.environ.get("CARERSIM_DEV_TRUTH", "")
    if not truth or not os.path.isfile(truth):
        sys.stderr.write("[skip] 未设置 CARERSIM_DEV_TRUTH 或路径不存在（dev 真值不内嵌）。\n")
        return 0

    pkg = sys.argv[1] if len(sys.argv) > 1 else "."
    docs = dev_docs(truth)
    dev_g = set()
    for d in docs:
        dev_g |= grams(d)

    lines = package_lines(pkg)

    # 哪些 dev 条目命中了当前行
    hit_map = {}
    for d in docs:
        g = grams(d)
        for idx, (path, ln, _) in enumerate(lines):
            if g & dev_g and g & grams(lines[idx][2]):
                hit_map.setdefault(idx, []).append(d)

    print("目标包      : %s" % os.path.abspath(pkg))
    print("dev 语料    : %d 条，%d-gram 去重后 %d 个" % (len(docs), N, len(dev_g)))
    print("扫描行      : %d" % len(lines))
    print("")

    hits = 0
    for idx, sources in sorted(hit_map.items()):
        hits += 1
        if hits > 40:
            print("...（仅显示前 40 处）")
            break
        path, ln, line = lines[idx]
        src = max(sources, key=len)
        print("── %s:%d" % (path, ln))
        print("   包内：%s" % line.strip()[:120])
        print("   dev ：%s" % src[:120])
    print("")
    print("模糊层命中行：%d / %d" % (hits, len(lines)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
