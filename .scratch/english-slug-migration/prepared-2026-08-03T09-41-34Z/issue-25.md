---
slug: filter-pandas-dataframes-with-loc
description: "TL;DR"
created_date: "2024-10-07"
---

## TL;DR

建议使用 `DataFrame.loc` 方法，支持类似 SQL 中的`where`条件对`rows`筛选，也支持对`column`进行筛选。

## The Zen of Python

如果在 Python 文件中输入 `import this`，便可以看到 Python 之禅的全文。其中有一条：

> There should be one-- and preferably only one --obvious way to do it.

很明显，Pandas 从 2008 年发展到现在，已经跟这些原则没有什么关系了，光是筛选 DataFrame 的方法就有 n 种，我能想到的：

```python
df[df["foo"]>0]
df.loc[df["foo"]>0,:]
df.iloc[0,1]
df.filter(items=['foo', 'bar'])
df.query('foo > bar')
```

刚开始，对于我这个初学者来说，Google 搜到什么就用什么。实际结果就是自己的代码非常乱，一个文件用到的筛选方法非常多，这个代码第一遍写的时候知道是干嘛的，第二遍看的时候真的没人一下子能看懂。

**每种筛选方法有什么区别**：大家可以参考[ai 回答](https://www.perplexity.ai/search/df-loche-df-query-de-qu-bie-KTT8Yo9MQRa8qEFB_CmEzw#10)

## 为什么推荐.loc 方法

**首先我们先创建一个测试用数据集**：

```python
data = {
	"Name": ["Alice", "Bob", "Charlie", "David", "Eva"],
	"Age": [25, 30, 35, 40, 28],
	"Gender": ["Female", "Male", "Male", "Male", "Female"],
	"Salary": [50000, 60000, 70000, 80000, 55000],
	"Country": ["USA", "Canada", "USA", "UK", "Canada"],
}

df = pd.DataFrame(data)
```

**主要理由如下**：

1. 支持同时筛选 rows 和 columns，`.loc`支持以逗号隔开的两个参数：第一个参数对 rows 进行操作，第二参数对 columns 进行操作

```python
df.loc[:,:] # 取所有行和所有列
df.loc[df["age"]>30] # 取age > 30 的行 和 所有列
df.loc[df["age"]>30, ["Name", "Salary"]] # 取age > 30 的行 和 Name、Salary列
df.loc[df["age"]>30, ["Name", "Salary"]]
df.loc[0:3,:] # 取索引为0-3的行 和 所有列
df.loc[(df["Age"] > 30) & (df["Gender"] == "Male"), ["Name","Salary"]] # 取age > 30且 Gender = Male 的行 和Name、Salary列
```

2. 支持对 rows 进行复杂条件判断筛选：

```python
df.loc[(df["Age"] > 30) & (df["Gender"] == "Male"), ["Name","Salary"]] # 取age > 30且 Gender = Male 的行 和Name、Salary列
```

3.  对行或列进行**区间**形式的筛选：

```python
df.loc[0:3,:] # 取索引为0-3的行 和 所有列
df.loc[0:3,"Name":"Salary"] # 取索引为0-3的行 和 Name - Salary的所有列
```

4. 再花哨点，把筛选条件作为变量

```python
# 取age > n且 Gender = Male 的行 和Name、Salary列
n = 30
df.loc[(df["Age"] > n) & (df["Gender"] == "Male"), ["Name","Salary"]]
```

## .loc 的缺点

这么全面的方法也有缺点：

1. **性能问题**：在处理非常大的 DataFrame 时，`.loc`可能会比其他方法（如`.query`或布尔索引）慢，尤其是当涉及复杂条件时。

2. **复杂条件可读性差**：当涉及多个复杂条件时，使用布尔索引结合`.loc`可能导致代码变得冗长且难以阅读。

## 结语

综上，基本上`.loc`方法基本可以满足日常工作中会碰到的 90%以上的筛选场景，不用纠结，选`.loc`准没错！
