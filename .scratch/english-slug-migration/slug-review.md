# Historical Blog English Slug Review

Status: **completed on 2026-08-03**  
Repository: `geoqiao/geoqiao.github.io`  
Source: all 34 published `type:blog` GitHub Issues

## Finding

`config.yaml` is not missing a Blog slug setting. Under the accepted Issue Content Contract, each Blog owns its stable route key in the GitHub Issue body front matter:

```yaml
---
slug: three-to-eight-meaningful-english-words
description: ...
created_date: "YYYY-MM-DD"
---
```

All 34 published Blog Issues currently contain valid unique slugs. The historical migration generated many of them as pinyin, even though the contract recommends three to eight meaningful English words. This review proposes 29 changes and keeps 5 already-English slugs unchanged.

## Candidate map

| Issue | Title | Current slug | Proposed slug | Result |
|---:|---|---|---|---|
| #1 | rye - 好用的Python包管理工具 | `rye-hao-yong-de-pythonbao-guan-li-gong-ju` | `rye-python-package-manager-guide` | change |
| #2 | excel 学习经验分享 | `excel-xue-xi-jing-yan-fen-xiang` | `practical-excel-learning-tips` | change |
| #3 | with_sql _as_english | `with-sql-as-english` | `learn-sql-in-plain-english` | change |
| #4 | 关于历史 | `guan-yu-li-shi` | `history-as-a-rolling-wheel` | change |
| #5 | 空调剥削理论的提出 | `kong-diao-bo-xue-li-lun-de-ti-chu` | `air-conditioning-exploitation-theory` | change |
| #6 | Out of the depth of misfortune comes bliss | `out-of-the-depth-of-misfortune-comes-bliss` | `out-of-the-depth-of-misfortune-comes-bliss` | keep |
| #7 | 总得活着吧？ | `zong-de-huo-zhao-ba` | `why-we-still-choose-to-live` | change |
| #8 | 基于 GitHub issues 的个人 blog 搭建 | `ji-yu-github-issues-de-ge-ren-blog-da-jian` | `github-issues-blog-setup-guide` | change |
| #9 | What's on my Mac | `what-s-on-my-mac` | `what-s-on-my-mac` | keep |
| #10 | Shottr- 原生、轻巧且功能强大的免费macOS截图工具 | `shottr-yuan-sheng-qing-qiao-qie-gong-neng-qiang-da-de-mian-fei-tu-gong` | `shottr-lightweight-macos-screenshot-tool` | change |
| #11 | Python环境安装-Anaconda为例 | `pythonhuan-jing-an-zhuang-anacondawei-li` | `install-python-with-anaconda` | change |
| #12 | 重器轻用-Obsidian | `zhong-qi-qing-yong-obsidian` | `use-obsidian-the-simple-way` | change |
| #13 | 我的第一个完整的机器学习项目-Titanic总结 | `wo-de-di-yi-ge-wan-zheng-de-ji-qi-xue-xi-xiang-mu-titaniczong-jie` | `my-first-titanic-machine-learning-project` | change |
| #14 | Coke Machine Challenge | `coke-machine-challenge` | `coke-machine-challenge` | keep |
| #15 | 总有一些 app 只能 Windows 用 | `zong-you-yi-xie-app-zhi-neng-windows-yong` | `run-windows-apps-on-mac-with-vmware` | change |
| #16 | Vim？ Don't be afraid ！ | `vim-don-t-be-afraid` | `vim-don-t-be-afraid` | keep |
| #17 | App Defaults 2023 | `app-defaults-2023` | `app-defaults-2023` | keep |
| #18 | Python编辑器-我的VSCode配置 | `pythonbian-ji-qi-wo-de-vscodepei-zhi` | `my-vscode-setup-for-python` | change |
| #20 | 基于 fastAPI 的 CRUD 练习- RSS 订阅管理 | `ji-yu-fastapi-de-crud-lian-xi-rss-ding-yue-guan-li` | `build-an-rss-manager-with-fastapi` | change |
| #21 | 使用 Python 和 GitHub Pages 搭建个人博客 | `shi-yong-python-he-github-pages-da-jian-ge-ren-bo-ke` | `build-a-python-blog-on-github-pages` | change |
| #23 | uv - GitHub 20k star 的终极 Python 项目管理工具 | `uv-github-20k-star-de-zhong-ji-python-xiang-mu-guan-li-gong-ju` | `uv-python-project-management-guide` | change |
| #24 | 为 GitHub Pages 个人博客添加 YAML 配置功能 - 基于 Python | `wei-github-pages-ge-ren-bo-ke-tian-jia-yaml-pei-zhi-gong-neng-ji-yu` | `add-yaml-config-to-github-pages-blog` | change |
| #25 | 不要纠结了！在Pandas中数据筛选就用它 - Python | `bu-yao-jiu-jie-liao-zai-pandaszhong-shu-ju-shai-xuan-jiu-yong-ta` | `filter-pandas-dataframes-with-loc` | change |
| #26 | 如何对连续型数据进行分箱 - Python | `ru-he-dui-lian-xu-xing-shu-ju-jin-xing-fen-xiang-python` | `optimal-binning-for-continuous-data-in-python` | change |
| #27 | Python 环境配置从零开始： uv、pdm 和 VSCode 的最佳实践 | `python-huan-jing-pei-zhi-cong-ling-kai-shi-uv-pdm-he-vscode-de-zui-jia` | `python-setup-with-uv-pdm-and-vscode` | change |
| #28 | 配置 VSCode 的免费 AI 编程助手：Ollama 、Groq和 Continue 扩展 | `pei-zhi-vscode-de-mian-fei-ai-bian-cheng-zhu-shou-ollama-groqhe-kuo` | `free-vscode-ai-with-ollama-groq-and-continue` | change |
| #29 | 2024年终总结：控制预期，坚持下去 | `2024nian-zhong-zong-jie-kong-zhi-yu-qi-jian-chi-xia-qu` | `2024-review-manage-expectations-and-keep-going` | change |
| #30 | 我喜欢冬天的下午走路去成都的茶馆喝茶 | `wo-xi-huan-dong-tian-de-xia-wu-zou-lu-qu-cheng-du-de-cha-guan-he-cha` | `winter-walks-to-chengdu-teahouses` | change |
| #31 | 2025年终总结：关注自己 | `2025nian-zhong-zong-jie-guan-zhu-zi-ji` | `2025-review-focus-on-yourself` | change |
| #32 | Vibe Coding 实战后感 - github_blog with Trae | `vibe-coding-shi-zhan-hou-gan-github-blog-with-trae` | `vibe-coding-github-blog-with-trae` | change |
| #34 | 不懂Git、不会前端，一个文科生的GitHub Blog | `bu-dong-git-bu-hui-qian-duan-yi-ge-wen-ke-sheng-de-github-blog` | `build-a-github-blog-without-git-or-frontend` | change |
| #35 | 从 Superpowers 学习高质量 AI 协作：一份给策略分析师的 Claude Code 指南 | `cong-superpowers-xue-xi-gao-zhi-liang-ai-xie-zuo-yi-fen-gei-ce-lue-fen` | `superpowers-claude-code-guide-for-strategy-analysts` | change |
| #36 | 从 Obsidian 到博客：我如何用一条命令把笔记变成网站 | `cong-obsidian-dao-bo-ke-wo-ru-he-yong-yi-tiao-ming-ling-ba-bi-ji-bian` | `publish-obsidian-notes-with-one-command` | change |
| #41 | What's on My Pi Agent?：把 90% 的 Codex Desktop 装进终端 | `what-s-on-my-pi-agent-ba-90-de-codex-desktop-zhuang-jin-zhong-duan` | `terminal-codex-workflow-with-pi-and-herdr` | change |

## Validation

The proposed set has been mechanically checked:

- 34 entries and 34 unique slugs;
- every slug matches lower-case ASCII kebab-case;
- every slug contains 3–8 hyphen-separated words;
- maximum length is 51 characters, below the 80-character contract limit;
- no slug is the reserved `page` route.

## Items worth closer editorial review

The technical posts have direct search-intent phrases. These more personal or metaphorical translations are necessarily editorial choices and deserve explicit owner confirmation:

- #4 `history-as-a-rolling-wheel`
- #5 `air-conditioning-exploitation-theory`
- #7 `why-we-still-choose-to-live`
- #29 `2024-review-manage-expectations-and-keep-going`
- #30 `winter-walks-to-chengdu-teahouses`
- #31 `2025-review-focus-on-yourself`

## Execution record

The owner approved this map and the migration completed on 2026-08-03:

1. merged site compatibility support in `geoqiao/geoqiao.github.io#43` (`b287db39072dedc7ac872b5853c867cb59f57d99`);
2. saved all 34 original Issue bodies in `rollback-2026-08-03T09-41-34Z.json` before mutation;
3. changed only the approved `slug:` line in 29 Issues and left #6, #9, #14, #16, and #17 unchanged;
4. re-read all 34 live Issues and verified titles, labels, dates, URLs, and all non-slug body bytes against the rollback snapshot;
5. built locally with the production Config and generated 29 old-path compatibility pages;
6. deployed successfully in Actions run `30802834330`, whose build reported `created=29 skipped=0`;
7. verified in production that all 68 sitemap URLs return HTTP 200, all 34 Blog pages have self-canonical URLs, all 29 old paths point to their approved new canonical, and no old path remains in sitemap or Atom;
8. resubmitted `https://geoqiao.me/sitemap.xml` in Google Search Console and requested indexing for `/blog/terminal-codex-workflow-with-pi-and-herdr/`.

GitHub Pages cannot emit per-path HTTP 301 responses. The old paths therefore use static instant meta-refresh compatibility pages with an exact canonical target and remain outside the sitemap.
