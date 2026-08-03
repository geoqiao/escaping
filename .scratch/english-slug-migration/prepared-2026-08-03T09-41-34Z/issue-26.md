---
slug: optimal-binning-for-continuous-data-in-python
description: "在做数据分析时，经常要对连续型数据进行分箱。面临的主要问题是：怎么分箱才是最优的？"
created_date: "2024-10-26"
---

在做数据分析时，经常要对连续型数据进行分箱。面临的主要问题是：怎么分箱才是最优的？

一个常见的场景是，老板想看用户在不同年龄段的占比以及消费情况，这时如果将所有年龄全部展示出来会话，表格会非常长，不容易阅读。一般情况下，我们会把相近的年龄做一个区间，来展示不同年龄区间数据。这就需要用到分箱，把年龄划分成不同的区间。

## 常用的分箱方法

1. 等距分箱：比如数据集的年龄区间为 1-60 岁，以每 10 岁作为一个区间，划分为 6 个区间。
2. 等频分项：比如数据集总共有 100 个客户，按照年龄从小到大排序，每 10 个客户作为一个区间。

但是这两种分箱都回答不了老板的另一个灵魂问题：你这样分能看清客户特征吗？是最合理的吗？

确实，以上两种分箱操作起来比较简单，而且 pandas 自带了`.cut` 方法。然而，要解决最优分箱，以上两种方法都不太合适。

如何进行最优分箱，就要引出今天的主角：`optbinning`

## 最优分箱 - optbinning

`optbinning`是一个由 Python 编写的可以寻找连续型变量最优分箱的库，他的功能十分强大，甚至可以直接用来开发评分卡模型。大家如果感兴趣可以从他的[官网](https://gnpalencia.org/optbinning/index.html)了解更多。这里主要介绍他的分箱功能。

简单来说，optbinning 同时支持等频、等距、CART、MDLP 等四种分箱方法。前两种不做赘述：

1. `CART`全称**Classification and Regression Trees**：即分类回归树，使用决策树的分叉方法来寻找信息增益最大的分箱区间
2. `MDLP`全称**Minimum Description Length Principle**：即最小描述长度原则，考虑模型复杂度与数据拟合度之间的平衡

对于详细的底层算法，可以查看一些详细的教程介绍。作为一个资深调包侠，在日常业务场景中，我认为`cart`适用性更广，也更好解释。（建议可以看一下吴恩达老师对于决策树模型的讲解，很容易懂，用来自己理解或者让业务领导理解都非常好用）

## 实操举例

这里使用 optbinning 官网文档的例子来向大家演示如何实操分箱：

### 首先加载数据集

```python
import numpy as np
import pandas as pd
from sklearn.datasets import load_breast_cancer #著名的癌症数据集
from optbinning import OptimalBinning #今天的主角，分箱器

data = load_breast_cancer() #加载数据集
df = pd.DataFrame(data.data, columns=data.feature_names) #转化为pandas可以读取的dataframe
```

breast_cancer 简单来说就是通过肿瘤的半径、纹理、光滑度等数据，来预测肿瘤良性或恶性。这里我们主要使用**半径**来分箱。

### 获取变量及结果

```python
variable = "mean radius"
x = df[variable].values
y = data.target
```

### 实例化分箱器并进行训练

```python
optb = OptimalBinning(name=variable, dtype="numerical", prebinning_method="cart") #实例化分箱器，dtype是指将要分箱的变量的数据类型，这里使用"numerical"，代表变量为数值，prebinning_method是使用的分箱方法，这里使用“cart”

optb.fit(x, y)  #分箱
```

### 输出分箱结果

```python
binning_result = optb.binning_table.build() #使用build方法会输出为一个dataframe，方便使用pandas读取
```

打印`binning_result`之后会看到一个如下样式的表格：

<img width="628" alt="image" src="https://github.com/user-attachments/assets/a23f875d-f893-4d41-9ecb-ec7ceecb7a05">

其中每一列的含义如下：

- **Bin**: 由最优切分点界定的区间。
- **Count**: 每个区间内记录的数量。
- **Count (%)**: 每个区间内记录的百分比。
- **Non-event**: 每个区间内非事件记录的数量（𝑦=0）。
- **Event**: 每个区间内事件记录的数量（𝑦=1）。
- **Event rate**: 每个区间内事件记录的百分比。
- **WoE**: 每个区间的证据权重（Weight-of-Evidence）。
- **IV**: 每个区间的信息值（Information Value，也称为杰弗瑞斯散度）。
- **JS**: 每个区间的詹森-香农散度（Jensen-Shannon divergence）。

其中`bin`列就是找到的最优区间了；`IV`（Information Value）是我们在进行信用卡数据分析时用到的一个非常重要的指标，反映了特征与目标之间的相关性，后续有机会分箱评分卡模型制作的时候我会再仔细写。

## 结语

是不是非常简单！核心代码其实就三行：实例化分箱器、fit、输出分箱结果。

实际使用中，可以针对自己的业务场景对代码增加判断是否数值型变量、输出到 excel 等操作。

其实`optbinning`库还提供了很多非常好用的接口，比如只获取分箱区间、将分箱结果映射到原始数据集等等操作，大家可以从[文档](https://gnpalencia.org/optbinning/index.html)中看到更多技巧。
