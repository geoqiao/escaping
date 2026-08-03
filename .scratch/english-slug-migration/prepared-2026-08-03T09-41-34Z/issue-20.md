---
slug: build-an-rss-manager-with-fastapi
description: "背景"
created_date: "2024-05-10"
---

# 背景

最近两三年，我逐渐卸载了抖音、微博等社交媒体，主要从RSS订阅获取信息。卸载部分社交媒体让我有了一点时间做其他事情，比如听播客、学Python、阅读......

这个练习是我的[CS50P](https://cs50.harvard.edu/python/2022/)final project的延续，主要目的是学习一些web的开发框架、使用Python操作数据库。


## why fastAPI

对比了Django 还有 Flask：

1. 感觉Django太重了，没有方便的装饰器，不适合新手
2. Flask感觉有点乱，主要命令行我没有弄明白
3. fastAPI对type hints的支持很好，感觉也更简单

## why SQLite

SQLite只有一个文件，操作起来很简单，也不用配置什么环境

# 思路
我想实现对RSS订阅源的添加、查询、删除功能，所以思路很简单
1. 创建一个SQLite数据库，要包含`订阅链接`、`标题`、`tag`、`网址`、`添加时间`等字段
2. 定义CRUD函数
3. 将函数返回值给到fastAPI，并渲染前端页面

# 上手开干

## 创建数据库

这里我使用SQLAlchemy库来实现，搜索中推荐这个库的文章很多，ORM支持很不错

> ORM：指的是对象关系映射(Object-Relational Mapping)，主要作用是将数据库中的表结构映射到对象上,使开发者可以使用面向对象的方式来操作数据库,而不需要直接编写SQL语句。

使用SQLAlchemy创建SQLite数据库，设计`feeds`表的字段，并为字段添加类型要求

```python
class Base(DeclarativeBase):
    pass


class Subscription(Base):
    __tablename__ = "feeds"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(nullable=False)
    tag: Mapped[Optional[str]]
    link: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.now)
    
    def __repr__(self) -> str:
        return f"Feed(id={self.id!r}, url={self.url!r},title={self.title},tag={self.tag!r},link={self.link!r})"
```

## 定义CRUD函数

这里主要学习了SQLAlchemy的ORM查询方法。

一开始觉得直接写SQL语句更好，只用掌握一种SQL语法就行了；后来查询后，好像直接写SQL语句有安全风险，比如SQL注入。

> SQL注入：用户前端输入框填写SQL语句，导致后端数据泄露、篡改等等问题

**ORM语法示例**：

以下代码通过数据库中的ID字段查询对应的订阅链接。我感觉这种写法还能接受，不过还是感觉直接写SQL语句的话心智负担更小一点，因为可以少学一种语法。

```python
def get_feed_by_id(feed_id: int):
    with Session(engine) as session:
        feed = session.query(Subscription).filter(Subscription.id == feed_id).first()
    
    return feed
```


## fastAPI接口

其实fastAPI部分很好写，只要我们获取到返回值，并且传给前端页面就好了

Django框架中需要配置的视图函数、URL路径等等都不在一个文件中，但是fastAPI通过一个简单的装饰器将这些工作都做好了

```python
@app.get("/feeds_list")
async def get_rss_feeds(request: Request):
    feeds = get_all_feeds()
    return template_dir.TemplateResponse("feeds_list.html", {"request": request, "feeds": feeds})

```

## 命令行运行程序

通过命令行运行，在 http://127.0.0.1:8000 预览程序

```shell
uvicorn main:app --reload 
```

[项目地址](https://github.com/geoqiao/RSS_db)

> 纯属兴趣驱动，如有不准确的地方欢迎交流

**预览效果如下**
<img width="1336" alt="image" src="https://github.com/geoqiao/geoqiao.github.io/assets/105639506/869f0d88-fdb0-4f7a-911c-6c8e39b260df">

