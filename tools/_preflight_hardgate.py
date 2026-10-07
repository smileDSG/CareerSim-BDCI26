#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
硬门禁预检（只读）—— 照官方"判 0 清单"逐条查包

背景
    官方 validate 只查三项（布局 / manifest 字段 / frontmatter），**它查不到真正的判 0 原因**。
    四天公示里约 32% 的队伍被清零，最高频死法是：
        mode 写错、把隐藏事件后果预写成查表、在 skill 里写死情节答案、
        从规则数据解码、尝试读取隐藏状态、缺 manifest、提交包含模型。

分级
    OK   = 通过
    WARN = 官方口径模糊、需要人来判断
    FAIL = 官方明确判 0 的项（出现即不许提交）

用法
    python _preflight_hardgate.py [目标包目录，默认 .]
"""
import json
import os
import re
import sys

SIZE_LIMIT = 2 * 1024 * 1024      # 2MB
CHAR_LIMIT = 58_590               # 常驻层安全线（信封 60,000 − 外壳 ≈910，再留 500 余量）

BANNED_VALUE_TABLE = ("事件", "选项", "增减值", "delta", "cap", "门槛")   # 仅用于定位上下文，不是黑名单
HIDDEN_STATE_TOKENS = ("hidden_risk", "hidden", "hidden_state")
DECODE_TOKENS = ("decode", "解码", "dumps(", "json.load")


def walk(pkg):
    for root, dirs, files in os.walk(pkg):
        dirs[:] = [d for d in dirs if d not in {".venv", ".git", "__pycache__", "node_modules"}]
        for f in files:
            yield os.path.join(root, f)


def read(p):
    try:
        return open(p, encoding="utf-8").read()
    except UnicodeDecodeError:
        return ""


def main():
    pkg = sys.argv[1] if len(sys.argv) > 1 else "."
    results = []

    def add(level, name, detail):
        results.append((level, name, detail))

    files = list(walk(pkg))
    total_size = sum(os.path.getsize(p) for p in files)

    # ── A 组：布局 / manifest / frontmatter（官方 validate 的三项）
    man = os.path.join(pkg, "manifest.json")
    ok_m = os.path.isfile(man)
    add("OK" if ok_m else "FAIL", "A1 manifest.json 存在且可解析", "")

    mode = ""
    team = name = instruction = ""
    if ok_m:
        try:
            m = json.load(open(man, encoding="utf-8"))
            mode = str(m.get("mode", ""))
            team, name = str(m.get("team", "")), str(m.get("name", ""))
            instruction = str(m.get("instruction", ""))
        except Exception as e:
            add("FAIL", "A1 manifest.json 解析失败", repr(e))

    add("OK" if mode == "agent" else "FAIL", "A2 mode 合法", "mode=%r（只认 agent）" % mode)
    add("OK" if all([team, name, instruction]) else "WARN", "A3 team/name/instruction 非空",
        "len=%d / %d / %d" % (len(team), len(name), len(instruction)))

    sk_files = [p for p in files
                if p.replace("\\", "/").count("/skills/") and p.endswith("SKILL.md")]
    skill_ids = sorted({os.path.basename(os.path.dirname(p)) for p in sk_files})
    add("OK" if sk_files else "FAIL", "A4 包结构 skills/<id>/SKILL.md",
        "找到 %d 个技能：%s" % (len(skill_ids), skill_ids))

    model_files = [p for p in files if p.lower().endswith((".bin", ".safetensors", ".pt", ".gguf"))]
    add("OK" if not model_files else "FAIL", "A5 包内不含模型文件",
        "".join(model_files[:3]) if model_files else "")

    add("OK" if total_size <= SIZE_LIMIT else "FAIL", "A6 体积 ≤ 2MB",
        "%.3f MB" % (total_size / 1024 / 1024))

    fm_ok = all(read(p).lstrip().startswith("---") for p in sk_files) if sk_files else False
    add("OK" if fm_ok else "FAIL", "A7 SKILL.md frontmatter 合法", "")

    # ── B 组：判 0 内容红线
    # B1 只扫「Agent 真正会加载的运行时 markdown」（skills/**），不扫 README / design ——
    # 那些是人类读的交付文档，全文讲"我们删掉了哪些真值"本来就会提到引号与增减值，
    # 把它们算进去会让检测器永远红。
    runtime = sorted(p for p in files
                     if p.replace("\\", "/").count("/skills/") and p.lower().endswith(".md"))
    rt_text = "\n".join(read(p) for p in runtime)
    all_text = "\n".join(read(p) for p in files)

    # 判据：**连续 ≥ RUN_MIN 行**都同时出现「≥8 字的引号串 + 紧邻的有符号整数」才算查表。
    # 真值表会长这样（几十行连着）；单条命中只是我们的规则里在引用引擎术语或复盘教训。
    RUN_MIN = 3

    def table_like(paths):
        best, best_at, samples = 0, None, []
        for p in paths:
            run, at = 0, None
            for i, line in enumerate(read(p).splitlines(), 1):
                hit = (re.search(r"「[^」]{8,}」", line)
                       and (re.search(r"」[^，。；\n]{0,8}[+\-−]\s*[1-9]\b", line)
                            or re.search(r"[+\-−]\s*[1-9]\b[^，。；\n]{0,8}「", line)))
                if hit:
                    run += 1
                    at = at or i
                    if len(samples) < 5:
                        samples.append("%s:%d" % (os.path.relpath(p, pkg), i))
                else:
                    if run > best:
                        best, best_at = run, (p, at)
                    run, at = 0, None
            if run > best:
                best, best_at = run, (p, at)
        return best, best_at, samples

    rt_run, rt_at, rt_samples = table_like(runtime)
    add("FAIL" if rt_run >= RUN_MIN else "OK",
        "B1 「事件+选项+增减值」查表结构（运行时文件连续 ≥%d 行）" % RUN_MIN,
        "最长连续 %d 行%s%s" % (rt_run,
                            ("（%s:%d）" % (os.path.relpath(rt_at[0], pkg), rt_at[1]) if rt_at else ""),
                            ("，例如 " + " ".join(rt_samples)) if rt_samples else ""))

    pkg_run, _, _ = table_like([p for p in files if p not in runtime])
    add("OK", "B1b 同结构（含 design/ / README）", "最长连续 %d 行（不计入判定）" % pkg_run)

    hidden_hits = [t for t in HIDDEN_STATE_TOKENS if t in rt_text]
    benign = rt_text.count("读不到") + rt_text.count("不可见") + rt_text.count("不返回")
    add("WARN" if (hidden_hits and benign) else ("OK" if not hidden_hits else "FAIL"),
        "B2 不含「读取隐藏状态」指令",
        "命中 %s，其中「读不到/不可见/不返回」语境 %d 处" % (hidden_hits, benign))

    decode_hits = sum(rt_text.count(t) for t in DECODE_TOKENS)
    add("OK" if not decode_hits else "WARN", "B3 运行时文件里的「解码」措辞", "%d 处" % decode_hits)

    preset = sum(all_text.count(t) for t in ("写死答案", "预设输出", "硬编码预设"))
    add("OK" if not preset else "WARN", "B4 预设答案类关键词分布",
        "出现 %d 次（全包，多为设计文档）" % preset)

    # ── C 组：工程线
    for p in sk_files:
        body = read(p)
        n = len(body)
        lvl = "OK" if n <= CHAR_LIMIT else "FAIL"
        add(lvl, "C1 %s ≤ %d" % (os.path.relpath(p, pkg), CHAR_LIMIT),
            "%d 字符（窗余 %d）" % (n, CHAR_LIMIT - n))
        crlf = body.count("\r\n")
        if crlf:
            add("FAIL", "C2 %s 行尾统一 LF" % os.path.relpath(p, pkg), "%d 处 CRLF" % crlf)
    add("OK", "C2 行尾统一 LF", "")

    w = max((len(l) for _, l, d in results), default=40)
    for lvl, nm, detail in results:
        print("[ %-4s ] %-*s %s" % (lvl, w, nm, detail))

    f = sum(1 for l, _, _ in results if l == "FAIL")
    a = sum(1 for l, _, _ in results if l == "WARN")
    print("")
    print("结论：FAIL=%d  WARN=%d" % (f, a))
    if f:
        print("➡ 不许提交（FAIL 项 = 官方明确判 0 的项）")
    elif a:
        print("➡ 可提交（WARN 项需人工确认口径）")
    else:
        print("➡ 可提交")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
