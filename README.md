# task26100236

跨广告组关键词重叠判定库（纯 Python 标准库，无第三方依赖）。

“重复”不指配置文本相同，而指存在一条同时被两个广告组接纳的搜索词。
`find_overlap` 返回共同接纳的搜索词中 token 数最少、同长度字典序最小的
那条具体搜索词作为审计见证；不存在时返回 `None`（任意长度都无解）。

## 匹配语义

- `exact`：搜索词与配置的 token 序列完全相等。
- `phrase`：配置序列作为连续片段出现（顺序与重复次数都有效）。
- `broad`：配置中每个不同 token 至少出现一次，不限顺序，配置中的重复
  token 不增加次数要求。
- 正向词支持三种类型；否词只支持 `exact` / `phrase`。
- 一条搜索词被某组接纳，当且仅当它匹配该组正向词，且不匹配该组任何
  组级否词及任何账号级否词。

候选词表 = 全部输入中出现的 token + 保留 token `"OTHER"`（代表未出现在
配置中的任意单词，不得出现在配置里）。普通 token 按 ASCII 字典序排序，
`"OTHER"` 排在最后。

## 用法

```python
from keyword_overlap import find_overlap

left = {"positive": ("phrase", ["a", "b"])}
right = {"positive": ("phrase", ["b", "a"])}
account_negatives = [("exact", ["a", "b", "a"])]

witness = find_overlap(left, right, account_negatives)
# ("b", "a", "b") —— exact 否词只禁止完全相等，不当子串禁止
```

输入也可以是 `Keyword` / `AdGroup` 数据类，或
`{"positive": ..., "negatives": [...]}` 字典；关键词可写成
`(match_type, tokens)` 二元组或 `{"match_type": ..., "tokens": [...]}`。
返回值为 token 元组，或 `None`。

## 实现要点

- `keyword_overlap/model.py`：数据模型与输入校验。
- `keyword_overlap/automaton.py`：单组接纳自动机。phrase 用 KMP 追踪
  最长已匹配前缀；exact 追踪相等前缀；broad 记录已见 token 集合；
  phrase 否词一旦完整命中即剪枝，exact 否词只在终点判定。
- `keyword_overlap/search.py`：在左右两台自动机的乘积状态空间上按
  （长度, 字典序）做 BFS，首个双方接纳的状态即为最短见证；状态数有限，
  队列耗尽即证明任意长度无解。

## 运行测试

```sh
python3 -m unittest discover -s tests -t . -v
```

测试除断言期望见证外，还用独立的规格级判定函数暴力枚举短搜索词，
验证返回的见证确实被双方接纳且不存在更短或字典序更小的解。
