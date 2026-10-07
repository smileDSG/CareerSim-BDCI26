# tools/ —— 提交前的自检脚本

> **这些脚本是本仓库里唯一能"零成本复现结论"的东西。**
> 跑一局要 ¥4.5–9 和 30–47 分钟；跑这套只要 1–3 分钟，而且**结论更硬**。

## 0. 先读这条：dev 真值不在这里

dev 剧本是官方的保密资产，**我们既不该复制它，也不该把它塞进公开仓库**。
所以 `tools/` 里的过拟合审计脚本**不内嵌任何 dev 内容**，真值表由环境变量指向：

```bash
export CARERSIM_DEV_TRUTH="/path/to/appendix-g-event-delta-map.md"
```

拿到 dev 数据集之后（从官方引擎包里来），指向它就能跑。
**如果你手上没有 dev 数据，这两个脚本会干净地 skip 掉，不会编造结果** —— 这是有意的。

## 1. 精确层

```bash
python tools/_overfit_audit.py solution
```

三个指标（见 `docs/06`）：

| 指标 | 含义 |
|---|---|
| ① | 选项原文逐字命中率（≥8 字） |
| ② | 事件标题逐字命中率 |
| ③ | 命中行正文占比 |

**期望**：全部 `0.00%`。

## 2. 模糊层（8-gram）

```bash
python tools/_overfit_fuzzy.py solution
python tools/_overfit_scan_lines.py solution   # 逐行版 + 回显 dev 出处
```

**这一层才是真正抓"改写型引用"的。** 逐字匹配对"少两个字"完全无感；8-gram 能看到
`dev：向 Leader 争取以兼职形式参与「新项目」` 和 `包内：向 Leader 争取以兼职形式参与` 是同一条。

**期望**：`模糊层命中行：0`。

## 3. 硬门禁（照官方判 0 清单）

```bash
python tools/_preflight_hardgate.py solution
```

| 组 | 检查 |
|---|---|
| A1–A7 | manifest 布局 / mode / 字段 / skills 结构 / 无模型文件 / 体积 / frontmatter |
| **B1** | 「事件 + 选项 + 增减值」查表结构（**FAIL = 官方明确判 0**） |
| B2 | 「读取隐藏状态」指令（WARN：出现处是否都在"读不到/不可见"语境） |
| B3 | 「解码」措辞 |
| B4 | 预设答案类关键词 |
| C1–C2 | 常驻层 ≤ 58,590 字符 ／ 行尾统一 LF |

**期望**：`FAIL=0 WARN=0`。

> 注意 A 组就是官方 `validate_submission()` 的三项。**它过了 ≠ 能交** ——
> 真正的判 0 死法（B1、mode、写死答案）不在官方 validate 里。

## 4. 我们当时的完整绿灯（r9 / 现行交付件）

```
[ OK ] A1 manifest.json 存在且可解析        keys=['instruction','mode','name','team']
[ OK ] A2 mode 合法                          mode='agent'
[ OK ] A3 manifest.team/name/instruction 非空   len=12 / 16 / 10678
[ OK   ] A1 manifest.json 存在且可解析
[ OK   ] A2 mode 合法                            mode='agent'（只认 agent）
[ OK   ] A3 manifest.team/name/instruction 非空   len=12 / 16 / 10678
[ OK   ] A4 包结构 skills/<id>/SKILL.md           找到 2 个技能：['cor-career', 'cor-window']
[ OK   ] A5 包内不含模型文件
[ OK   ] A6 体积 ≤ 2MB                           0.592 MB
[ OK   ] A7 SKILL.md frontmatter 合法
[ OK   ] B1 「事件+选项+增减值」查表结构（运行时文件连续 ≥3 行）  最长连续 1 行
[ OK   ] B1b 同结构（含 design/ / README）          最长连续 2 行（不计入判定）
[ WARN ] B2 不含「读取隐藏状态」指令                命中 hidden_risk，均为「读不到／不可见」语境
[ OK   ] B3 运行时文件里的「解码」措辞               0 处
[ WARN ] B4 预设答案类关键词分布                    43 次（全包，多为设计文档）
[ OK   ] C1 skills/cor-career/SKILL.md ≤ 58590    58535 字符（窗余 55）
[ OK   ] C1 skills/cor-window/SKILL.md ≤ 58590     4973 字符（窗余 53617）
[ OK   ] C2 行尾统一 LF
结论：FAIL=0  WARN=2   ➡ 可提交（WARN 项需人工确认口径）
```

## 5. 纪律（同一条坑踩过两次）

> **改 SKILL.md 之后，README 里写的行数/字符数必须一起回填。**
> 我们 qe22、qe24 各踩了一次（README 目录行还写旧值 → 包被重建一次）。
> 自检里应该加一条：*README 自述数字 vs 实测* 比对。

## 6. 不在 tools/ 里的（因为会花钱 / 依赖本地环境）

| 东西 | 为什么不给 |
|---|---|
| `run_game*.sh` | 端口漂移、Windows 计划任务、safe-delete shim、代理 unset —— 全是本机特化，给你也跑不起来 |
| `_offline_score_latest.py` | 要 import 引擎自己的 `EndingScoreCalculator`，依赖装了 `career_emulator` 的 venv |
| `play_shadow_rules_v3/v4.md` | 影子测试报告，读着有用（方法论），跑起来要历史 jsonl |

这几篇的**方法**都写在 `docs/07-工程与跑局复现.md`，方法比脚本值钱。
