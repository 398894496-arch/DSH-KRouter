# 真人出题（第四套）/ A question set written by a person

前三套留出题都是 Claude Opus 在单独的 claude.ai 会话里写的（见 `../HELDOUT.md`）。这一套请**真人**来写，用自己平时
说话的方式问。它有两个用处：

1. 一套和模型无关的留出题，用来判断本地向量检索能不能作为可选功能发布；
2. 「越用越准」测评：同一件事问两次，第一次的问法交给 KRouter 的夜间学习，看第二次换个说法问时，它有没有学会。

The first three held-out sets were written by Claude Opus in separate claude.ai sessions. This one should be written
by a person, in their own words. It serves as a model-independent held-out set, and as the "learns from use" bench:
each thing is asked twice, the first wording goes through KRouter's nightly learning, and the second is scored.

## 谁来写

最好是没看过 KRouter 代码、也没看过前三套题的人。维护者本人写也可以，但要在日志里注明。写之前不要运行 KRouter，
也不要用任何检索工具试问题：只读 `../vault3/` 里的页面。

## 写什么

在 `../vault3/` 上写 50 件事，每件事两种问法（一共 100 个问题）：

| 类型 `kind` | 数量 | 是什么 | 要填 |
|---|---|---|---|
| `correction`（改过） | 15 | 某条规则后来改了：库里有 `（旧）` / `(old)` 页和新页，答案在**新页** | `page`、`evidence` |
| `current`（现行） | 15 | 只有一页讲这件事，答案就在那一页 | `page`、`evidence` |
| `neighbour`（库里没有） | 20 | 听起来像库里有，其实没有：借用某页的说法，但问的是那页没讲的东西 | `absent` |

- `week1` 和 `week2`：同一件事的两种问法，像你隔一周又想起来问一次。用词可以不同，但都要是你会自然说出口的话。
  不要照抄页面原文，也不要故意绕弯。
- `page`：答案所在页，写相对 `vault3/` 的路径，例如 `Handbook/API deprecation.md`。日志页（`Daily log/`、`工作日志/`）
  不能当答案页。
- `evidence`：答案页里能回答这个问题的那一句，**原样复制**。
- `absent`：`neighbour` 题里那个库里任何一页都没有的词（两种问法里都要出现这个词）。例如库里有「支付接口超时」，
  你问「搜索接口超时」，`absent` 就填 `搜索接口`。
- 中英文各一半左右，跟着页面的语言走就行。

## 格式

复制 `template.csv`，用表格软件或文本编辑器填，存成 UTF-8 的 CSV。`intent` 是你给每件事起的编号（`h01`、`h02`……），
`EXAMPLE` 开头的行是示例，校验时会跳过，可以删掉。

## 写完以后

```bash
python3 bench/memory_honesty/human_set/check_human_set.py my_questions.csv
```

它只检查格式和事实（答案页存在且没被取代、`evidence` 原句在答案页上、`absent` 词在问题里且不在任何页上），不运行
KRouter，也不打印任何系统的答案。全部通过后，它会写出 `human_pairs.jsonl.gz`。把这个文件交给维护者，维护者先在
`../HELDOUT.md` 里登记怎么用，再跑。

The checker only checks format and facts; it never runs KRouter or prints any system's answers.
