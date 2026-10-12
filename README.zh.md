# KRouter

**让你的编程 agent 记住你们定过什么，也记住后来改成了什么。**

Claude Code、Codex、Cursor、DeepSeek Harness 共用同一份记忆：一个 [Obsidian](https://obsidian.md) 里的纯 Markdown 文件夹，你自己能看、能改。问一句「我们发版流程是怎么定的」，agent 会给出答案，并告诉你出自哪一页。纠错之后，新结论直接取代旧结论，不会两个一起冒出来。库里没有的，agent 会被明确告知「库里没有」，而不是拿一条差不多的凑数。

[![ci](https://github.com/398894496-arch/KRouter/actions/workflows/ci.yml/badge.svg)](https://github.com/398894496-arch/KRouter/actions/workflows/ci.yml) [![release](https://img.shields.io/github/v/release/398894496-arch/KRouter)](https://github.com/398894496-arch/KRouter/releases/latest) [![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE) · English: [`README.md`](README.md)

![周一定了 A，周三改成 B，周四 agent 答 B 并引用那条纠错；库里没有的问题直接拒答](docs/img/demo.gif)

## 安装

```bash
curl -fsSL https://raw.githubusercontent.com/398894496-arch/KRouter/main/scripts/bootstrap.sh | sh
```

Windows（PowerShell）：`irm https://raw.githubusercontent.com/398894496-arch/KRouter/main/scripts/bootstrap.ps1 | iex` · Claude Code 插件：`/plugin install krouter --marketplace 398894496-arch/KRouter`（需要 Claude Code 2.1.275 或更高；在 shell 里用 `claude plugin install krouter --marketplace 398894496-arch/KRouter` 需要 2.1.292）。第三方插件市场不会自动更新：运行 `claude plugin update krouter@krouter`，或在 `/plugin` → Marketplaces → krouter 里选 Enable auto-update。

唯一的前提是 Python 3。安装脚本会建一个库（已有的库用 `--vault` 指定，一个文件都不覆盖），通过 MCP 把 Claude Code 和 Codex 接上，然后问你两个问题。

## 装完五分钟

1. **「要把本机已有的 agent 会话导进来吗？」** 答应后，近 7 天的 Claude Code 和 Codex 会话会变成页面，每个会话一页，内容是你的提问和每轮最后的回答。像 key 的文字会先脱敏，全程不出本机。
2. **「要让模型提炼一下定了什么吗？」** 答应后，你已经在用的模型（登录好的 CLI 或 API key）会在最近几个会话的页面顶上写出「定了什么、改了什么」。发之前它会先告诉你要发多少字。
3. 问你的 agent：*「上周我们关于 X 是怎么定的？」* 它会从库里查，给出答案和出处页；库里没有，就直说没有。

之后每晚的任务（同样先问你）会导入前一天的会话、做提炼、整理库，不用你维护。

## 和常见 agent 记忆的区别

| | KRouter | 常见的 agent 记忆 |
|---|---|---|
| 记忆放在哪 | 你能打开、编辑、比对、同步的 Markdown 页 | 数据库或向量库 |
| 纠错之后 | 新页取代旧页，旧页标成「已取代」 | 新旧两条都能匹配上，只能指望对的那条排前面 |
| 什么都对不上时 | 返回 `recall: none`，agent 会说库里没有 | 拿最接近的一条，说得很肯定 |
| 每条答案 | 带出处页和回执 | 通常没有出处 |
| 谁在用 | 本机所有 agent 共用一个库（MCP、skill、规则） | 通常只服务一个工具 |

**在用 [claude-mem](https://github.com/thedotmack/claude-mem)？** 不用卸掉。导入器目前是 beta：按 claude-mem 公开的表结构测过，还没在真实安装上跑过。安装时会发现它的记忆库并问你要不要导入：会话总结变成页面，每个项目的决定汇成一页，等你确认。你的模型还能把这些决定理一遍，分出哪些还有效、哪些被后来的决定取代了，这一步是 claude-mem 自己不做的。Claude Code 插件也能做到 claude-mem 让人觉得「有记忆」的那两件事，只是存成纯 Markdown：会话结束时自动记下；开新会话时，自动带上这个仓库里你确认过的决定和最近的纠错，每条都注明出处页。仓库按路径区分，不按文件夹名。这两件事都要你先同意导入才会做。

## 什么会离开本机

查询从不外发：查找走本地的 SQLite 全文索引，每次约 110 ms。导入会话也只在本机做。只有你点过头的步骤才会把文字发给模型，就是提炼会话和夜间整理两步，发给你本来就在用的 CLI 或 API key，用 `--dry-run` 可以先看会发多少。key 和标成机密的页从不外发，也从不引用。细节见 [`SECURITY.md`](SECURITY.md)。

## 老实的数字

| 测了什么 | 结果 |
|---|---|
| 该拒答时拒答（公开测试集，CI 跑） | 离题问题英文 12/12、中文 6/6 拒答 |
| 没见过的题上的错误引用率（[记忆诚实度测试集](docs/BENCHMARK.md)） | 约 22–25%，纯全文检索约 60%。在测试集自己的题上是 0%，但那套题上发现并修过 bug，只能算开发集数字 |
| 精确命中和向量检索比（「已取代」和「近邻」题，CI 跑） | 精确命中会拒答；TF-IDF、MiniLM、BGE-M3 会引一个近邻 |
| 作者库里的真实查询 | 盲评从 0.62 到 1.47（满分 2）。**这是开发集**，在留出题上没有提升。2026-10-16 会对新流量再做一次盲评 |

方法和还没做好的地方：[`docs/VERIFY.md`](docs/VERIFY.md)。

## 更多

- [工作原理和全部选项](docs/DETAILS.zh.md)：安装参数、夜间写手、精确命中和排序召回、问答卡、四种 agent 接入
- [`SECURITY.md`](SECURITY.md)：每条模型通道能看到什么、能做什么
- [`docs/FOR-AGENTS.md`](docs/FOR-AGENTS.md)：给 agent 判断 KRouter 适不适合它的用户时参考的事实
- [`CHANGELOG.md`](CHANGELOG.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md)：适合新人的 issue 都打了标签

*原名 DSH-KRouter，旧链接、旧 clone 地址和旧安装命令都会自动跳转。* MIT 协议。
