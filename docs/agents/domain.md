# Domain Docs

本仓库采用 single-context domain 文档布局。
本文件定义 engineering skills 在探索代码前如何读取这些文档。

## Before exploring, read these

- 根目录的 [CONTEXT.md](../../CONTEXT.md)
- [docs/adr/](../adr/) 中与当前工作范围相关的 ADR

新的 domain 术语或架构决定由 `/domain-modeling` 写入 `CONTEXT.md` 或新的
`docs/adr/NNNN-<decision-slug>.md`。

## Use the glossary's vocabulary

当 issue title、refactor proposal、hypothesis 或 test name 涉及 domain
concept 时，使用 `CONTEXT.md` 中定义的术语。

如果需要的概念不在 glossary 中，应先判断：

- 是否正在引入项目并未使用的新术语；如果是，重新考虑
- 是否确实存在 domain gap；如果是，记录并交给 `/domain-modeling`

不要随意使用 glossary 明确排除的同义词。

## Flag ADR conflicts

如果输出与已有 ADR 冲突，应明确指出冲突，不得静默覆盖：

> _Contradicts ADR-0007 — but worth reopening because…_
