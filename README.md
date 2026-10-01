# keyword_overlap

跨广告组关键词重叠判定库（纯 Python 标准库，无第三方依赖）。

两个广告组“重复”指：存在一条同时被两组接纳的搜索词。`find_overlap`
返回 token 数最少、同长度字典序最小的见证搜索词；不存在时返回 `None`
（表示任意长度都不可能通过）。

## 用法

```python
from keyword_overlap import AdGroup, Keyword, find_overlap

left = AdGroup(Keyword("phrase", ("a", "b")))
right = AdGroup(Keyword("phrase", ("b", "a")))
find_overlap(left, right, [])          # -> ('a', 'b', 'a')

neg = [Keyword("exact", ("a", "b", "a"))]
find_overlap(left, right, neg)         # -> ('b', 'a', 'b')
```

- `Keyword(match_type, tokens)`：正向词支持 `exact` / `phrase` / `broad`，
  否词仅支持 `exact` / `phrase`；`tokens` 为非空小写 ASCII 单词序列。
- `AdGroup(positive, negatives)`：一条正向词 + 若干组级否词。
- `find_overlap(left, right, account_negatives)`：账号级否词作为第三个参数。
- 保留 token `"OTHER"` 代表未出现在配置中的任意单词，不得用于配置；
  候选字母表中普通 token 按 ASCII 排序，`"OTHER"` 排最后。

## 运行测试

```sh
python3 -m unittest -v
```
