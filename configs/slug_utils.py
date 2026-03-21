from pypinyin import Style, pinyin
from slugify import slugify


def generate_slug(issue_number: int, title: str) -> str:
    """
    Generate a SEO friendly slug from an issue number and title.
    Example: 31-python-huan-jing-pei-zhi
    """
    # 1. 处理中文：将中文字符转换为拼音
    pinyin_list = pinyin(title, style=Style.NORMAL)
    pinyin_str = "-".join([item[0] for item in pinyin_list])

    # 2. 生成基础 slug
    base_slug = slugify(pinyin_str, lowercase=True)

    # 3. 拼接 issue 编号作为前缀，确保唯一性
    return f"{issue_number}-{base_slug}"


if __name__ == "__main__":
    # 测试
    test_cases = [
        (31, "2025年终总结：关注自己"),
        (28, "Python 环境配置：uv 和 VSCode"),
        (1, "Hello World!"),
    ]
    for n, t in test_cases:
        print(f"ID: {n}, Title: {t} -> Slug: {generate_slug(n, t)}")
