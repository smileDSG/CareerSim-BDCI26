#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
过拟合暴露度审计 —— 精确层（只读）

定义
    把 dev 真值表在**交付包全部文本文件**里做逐字匹配。
    命中的比例 = 交付包里「可被 Test 池直接判废」的内容占比（下界）。

    三个指标：
      指标 1  选项原文命中率（≥ MINLEN 字的条目才算，太短容易误报）
      指标 2  事件标题命中率
      指标 3  命中行正文占比（字符数 / 包内正文总字符数）

dev 真值从哪来
    dev 剧本不公开。本脚本**不内嵌任何 dev 内容**，真值表由环境变量指向：
        export CARERSIM_DEV_TRUTH="/path/to/appendix-g-event-delta-map.md"
    文件预期格式：
        `## <事件标题>` 每行一个；`- 「<选项原文>」` 每行一个。

用法
    export CARERSIM_DEV_TRUTH=/path/to/appendix-g.md
    python _overfit_audit.py [目标包目录，默认 .]
"""
import os
import re
import sys
import glob

MINLEN = 8  # 少于这个字数的条目不参与（避免「是」「否」这类噪声）

EXCLUDE_DIRS = {".venv", "node_modules", "__pycache__", ".git", "outputs"}
EXCLUDE_SUFFIX = (".zip", ".png", ".jpg", ".pdf", ".xlsx", ".py")


def dev_corpus(path):
    txt = open(path, encoding="utf-8").read()
    titles = [t.strip() for t in re.findall(r"^##\s+(.+)$", txt, re.M)]
    opts = [o.strip() for o in re.findall(r"^\s*-\s*«?「?(.+?)」?\**\s*$", txt, re.M)]
    return titles, opts


def package_texts(pkg):
    out = []
    for p in glob.glob(os.path.join(pkg, "**", "*"), recursive=True):
        if not os.path.isfile(p):
            continue
        if p.endswith(EXCLUDE_SUFFIX):
            continue
        if any(part in EXCLUDE_DIRS for part in p.replace("\\", "/").split("/")):
            continue
        try:
            out.append((p, open(p, encoding="utf-8").read()))
        except UnicodeDecodeError:
            pass
    return out


def ratio(hits, total):
    return (hits / total * 100.0) if total else 0.0


def main():
    truth = os.environ.get("CARERSIM_DEV_TRUTH", "")
    if not truth or not os.path.isfile(truth):
        sys.stderr.write(
            "[skip] 未设置 CARERSIM_DEV_TRUTH 或路径不存在。\n"
            "       export CARERSIM_DEV_TRUTH=/path/to/appendix-g-event-delta-map.md\n"
            "       本脚本只做逐字匹配，dev 真值不内嵌（它既不该公开，也不是本仓库的内容）。\n"
        )
        return 0

    pkg = sys.argv[1] if len(sys.argv) > 1 else "."
    titles, opts = dev_corpus(truth)
    opts_k = [o for o in opts if len(o) >= MINLEN]
    titles_k = [t for t in titles if len(t) >= MINLEN]

    texts = package_texts(pkg)
    corpus = "\n".join(t for _, t in texts)

    h_opt = sum(1 for o in opts_k if o in corpus)
    h_tit = sum(1 for t in titles_k if t in corpus)

    hit_lines, hit_chars, total_chars = set(), 0, 0
    for path, body in texts:
        lines = body.splitlines()
        total_chars += sum(len(l) for l in lines)
        for i, line in enumerate(lines):
            if any(o in line for o in opts_k) or any(t in line for t in titles_k):
                hit_lines.add((path, i))
                hit_chars += len(line)

    print("目标包        : %s" % os.path.abspath(pkg))
    print("dev 语料      : 标题 %d（参与 %d）+ 选项 %d（参与 %d）"
          % (len(titles), len(titles_k), len(opts), len(opts_k)))
    print("扫描文件数    : %d" % len(texts))
    print("")
    print("指标 1 选项原文逐字命中   : %3d / %3d = %6.2f%%" % (h_opt, len(opts_k), ratio(h_opt, len(opts_k))))
    print("指标 2 事件标题逐字命中   : %3d / %3d = %6.2f%%" % (h_tit, len(titles_k), ratio(h_tit, len(titles_k))))
    print("指标 3 命中行正文占比     : %6d / %6d = %6.2f%%"
          % (hit_chars, total_chars, ratio(hit_chars, total_chars)))
    print("")
    if hit_lines:
        print("命中明细（前 20 行）：")
        for path, i in sorted(hit_lines)[:20]:
            print("  %s:%d" % (path, i + 1))
    else:
        print("未发现逐字命中。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
