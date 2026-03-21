from pypinyin import Style, pinyin
from slugify import slugify


def generate_slug(issue_number: int, tags: list[str]) -> str:
    """
    Generate a SEO friendly slug from an issue number and tags.
    Format: {issue_number}-{tag1}-{tag2}...
    """
    # 1. 处理标签：将所有标签转换为 slug 格式并用连字符连接
    # 如果没有标签，则只返回编号
    if not tags:
        return str(issue_number)

    processed_tags = []
    for tag in tags:
        # 将标签转换为拼音（以防标签是中文）
        pinyin_list = pinyin(tag, style=Style.NORMAL)
        pinyin_str = "".join([item[0] for item in pinyin_list])
        processed_tags.append(slugify(pinyin_str, lowercase=True))

    tags_slug = "-".join(processed_tags)

    # 2. 拼接 issue 编号作为前缀
    return f"{issue_number}-{tags_slug}"


if __name__ == "__main__":
    # 测试
    test_cases = [
        (31, ["年终总结", "生活"]),
        (28, ["Python", "环境配置"]),
        (1, []),
    ]
    for n, t in test_cases:
        print(f"ID: {n}, Tags: {t} -> Slug: {generate_slug(n, t)}")
