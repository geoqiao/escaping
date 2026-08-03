---
slug: learn-sql-in-plain-english
description: "描述"
created_date: "2023-07-15"
---

## 描述

1. 分享自己学习 SQL 的经验。
2. `WITH 临时表名 AS 子查询` 是 SQL 中一个常用的语法，这篇分享会介绍这个语法。
3. SQL 很简单，只需要知道一些英文单词什么意思，就可以读懂。

## 英文单词列表

select：选择**哪些字段**
from：从**哪个表**选择这段
where：从某个表中符合**哪些条件的数据**进行选择
left join：就是 excel 中的 vlookup

## 用 excel 思维读 SQL 代码

理解了以上的几个单词，你就可以读懂 SQL 代码了，比如如下的代码片段：

```sql
SELECT
	table1.id
	,table2.name
FROM table1
LEFT JOIN table2
ON table1.id = table2.id
WHERE table1.column1 = '1'
```

在这个示例中，`table1`  和  `table2`  是两个不同的表，我们在 `table1` 中写了一个 `vlookup` ，这个公式以两张表中的 `id` 字段为条件关联，把 `table2`  中的 `name` 字段匹配到了 `table1` ，并且匹配完成后进行了一个筛选，只选择 `table1` 中 `column1` 字段为 `'1'` 的行。
