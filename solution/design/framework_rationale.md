# 框架选型与运用说明：为什么用 JiuwenSwarm，以及用到了它的什么

> 📦 **本包版本：v60r-qe26-20261003**（由 `_stamp_versions.py` 内嵌，取自 `_build_pkg_v57.py` 的 `TAG`；勿手改）

> 对应专家评审项「框架运用理由」。本文只写**有证据的事实**：
> 代码出处 `career_sim_runner/`（`constants.py` / `install.py` / `skill_contract.py` / `ws_client.py` / `prompts/`），
> 运行证据 `jiuwen_server.log` 与 **44 局** `score_report.json`。

## 1. 选型结论

| 决策 | 选择 | 依据 |
|---|---|---|
| 驱动框架 | **JiuwenSwarm** | 赛方指定的运行/评测载体；与 career-emulator 通过 MCP 工具协议直连 |
| 运行模式 | **`agent`** | 现版提交契约 `SUPPORTED_RUN_MODES = {"agent", "team"}`（`constants.py:27`）；server 日志实测 `mode=agent, sub_mode=None` |
| 模型 | DeepSeek V4.1 Flash（赛方统一） | 44 局 `token_usage.by_model` 实测；2026-09-17 起由 `deepseek-v4-flash` 切至 `deepseek-flash`（官方原值 `deepseek-v4.1-flash` 在本机报 400，已按运行时分发名对齐） |

> ⚠️ **一处需要更正的历史表述**：早期 README / 队友包里写的 `agent.plan` / `agent.fast` 是**旧版 runner 的 sub_mode 写法**，
> 现版 runner 未启用 sub_mode（server 日志 `sub_mode=None`），契约层也只接受 `agent` / `team`。
> `solution/manifest.json` 早已是 `"mode": "agent"`，README 与 `decision_report.md` 的旧表述已同步更正。

## 2. 为什么必须是框架，而不是裸 API 循环

| 需求 | 裸 API loop 的处境 | JiuwenSwarm 提供的能力（代码出处） |
|---|---|---|
| **工具编排** | 需自己实现 6 个 MCP 工具的调用、参数、错误分支 | 引擎侧工具集开箱可用：`show_employee_handbook` / `new_game` / `observe` / `take_action` / `check_latest_logs` / `ending_score`（`prompts/play_headless.md`） |
| **48 月长程会话** | 上下文必然超限，需自建压缩与恢复 | `session_id` 贯穿全局；**IDENTITY.md 常驻系统提示**（`install.py:140` 注释：经 `ContextAssembleRail` 在每次模型调用中保留，**上下文压缩后仍存活**）；超限后由 `play_headless_continue.md` 触发续跑：`observe` + `check_latest_logs` 回看历史后继续 |
| **技能挂载与环境隔离** | 需自己管理策略文件注入 | `solution/skills/*` 下每个含 `SKILL.md` 的目录被安装为 local skill，跑前 `_reset_skills_workspace` 清空重装（`install.py:96`）→ **每局环境一致**，无跨局污染 |
| **多文件技能包** | `references/` 需自建按需加载 | skill 目录**整目录** `copytree` 安装 → `references/*.md` 自动随包落地（`SKILL.md` 与附录同目录，第十六轮附录外置即依赖此机制） |
| **可观测性** | 需自建日志与统计 | 每局产出 `score_report.json`（含 `token_usage.by_model`）、`transcript-*.log`、`events-*.jsonl` → **44 局复盘 + 全部影子测试的数据源** |

**第 5 条是本方案方法论的硬前提**：我们所有策略改动都遵循"先拿历史数据验证根因、再动笔"（见 `skills_design.md` §9 迭代证据链），
没有框架落盘的 transcript / events / token 三件套，这套"零跑局成本验证"就无从谈起。第十八轮的引擎机制审计、
第十七轮的 `μ` 判据回放、第十五轮的 419 决策点影子测试，全部只读这三类落盘文件。

## 3. 为什么选 `agent` 而不是 `team`

1. **账本连续性**：本策略的全部决策依赖一张逐月滚动的账本，真值源唯一（`observe` 的 `current_state.status`）。多智能体交接会把"单一真值源"拆成多份记忆，交接丢一位就是一次误判——而单次误判的代价可以是 −5 分（爆雷，永久）甚至淘汰。
2. **角色单一**：赛题是**一个**职场角色做连续 48 个月决策，没有天然的角色分工面；`team` 引入的协调开销换不来决策质量。
3. **成本**：`team` 会成倍放大 token，而已实测 token 与成绩**无正相关**（n=33，r = **−0.360**，见 `token_analysis.md` 结论 1）——**多花钱、无收益**。

## 4. 实际用上的能力清单

| 框架能力 | 本方案用在何处 | 证据 |
|---|---|---|
| MCP 工具协议 | `observe → 决策 → take_action` 的主循环；`check_latest_logs` 用于上下文恢复 | `prompts/identity.md` 核心规则 1–4 |
| IDENTITY.md 常驻系统提示 | 承载"已安装技能清单 + 参赛者策略指令"，压缩后不丢 | `install.py:137-154`；play40 transcript 首轮即出现"read the SKILL.md first" |
| 技能（local skill）机制 | **两个 skill**：`cor-career`（主·判据层，769 行）+ `cor-window`（配套·调度层，197 行），另加 `cor-career/references/` 7 个文件（6 张附录 + 1 份机制词典） | `skill_contract.py:125` 自动发现 `skills/*/SKILL.md`，**无数量限制**（实测 2 个 skill 一次安装到位，`validate` 报 `All 2 skill(s) have valid SKILL.md frontmatter`） |
| 断点续跑 | 长程 48 月跨多次上下文压缩 | `prompts/play_headless_continue.md` |
| token / transcript / events 落盘 | 44 局复盘、影子测试器、本文全部数据 | `outputs/OpenMAIC-COR/<ts>/` |

## 5. 框架能力与策略设计的互相咬合（不是"套壳"）

框架的两个特性直接塑造了策略形态：

1. **上下文会被压缩** → 策略不能依赖"Agent 记住上个月发生了什么"，必须依赖**每次都能重新读到的真值**。
   所以 SKILL 里账本的唯一真源被硬性规定为 `observe` 回包的 `status`，并配"账本缺值不猜、按固定默认值处理"的防幻觉规则（`SKILL.md` §1.1）。
2. **token 与成绩无正相关** → 策略正文宁可写长、写死判定阶梯，也不让 Agent 现场推理权衡。
   966 行技能正文（主 769 + 配套 197）换来的，是把"每局反复试错"的成本一次性前置掉（`token_analysis.md` 结论 1、3）。
   第二十一轮补的 60 行尤其典型：写死事件先验被五局实测证伪后，宁可把"算本局实测斜率"的三步算法整段写进正文，也不让 Agent 现场猜。
3. **单文件过大会被截断**（play40 transcript 实测 `The skill content was truncated/offloaded.`）→ 正文必须控制在"一次加载完整"的量级，
   查表类内容靠 skill 目录自带的 `references/` 按需加载（第十六轮，主文件 1007 → 636 行）。

## 6. 降级路径

| 触发 | 降级动作 | 影响 |
|---|---|---|
| 单局超时 | 策略正文不依赖规划层，可独立工作；必要时关掉长思考、保留 SKILL 调用 | 决策质量由 SKILL 保证，规划层只是增益 |
| 成本过高 | 附录 A–F **已外置**为 `references/appendix-*.md`（406 行，占整个技能包正文 29%），按需加载 | 单次主文件注入约省 5pp 上下文占比（约 39% → 34%）；⚠️ 实测**未带来单局 token 总量下降**（agent 会主动加载附录，`token_analysis.md` 结论 2 第 2 点诚实披露） |
| 加载失败（读不到附录） | 走 `SKILL.md` §2.3 语义兜底并**显式标注「未查表」**；未命中禁止跨事件外推 | 保底不误判，代价是精度下降 |
| 框架层异常（ws 断连等） | runner 侧 ping/timeout 已调参；局内则按 `SKILL.md` §7 失败恢复处理 | 见 `skills_design.md` §8 |
