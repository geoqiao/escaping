---
slug: run-windows-apps-on-mac-with-vmware
description: "总有一些 app 只有 Windows 版本，最近对象就碰到这样一个问题，不得已只能安装一个虚拟机了。"
created_date: "2023-09-24"
---

总有一些 app 只有 Windows 版本，最近对象就碰到这样一个问题，不得已只能安装一个虚拟机了。

## 结论

1. 我最终选择了 VMware
2. 现在体验最好的虚拟机还是 PD，如果有钱可以无脑选择 PD
3. VMware 也很强，丝滑感跟 PD 还有差距，但是胜在个人使用免费，且功能够用。

## 为什么选择 VMware？

1. PD 太贵，破解太麻烦，macOS 每出一个大版本基本都要重新购买一次
2. VMware 已经支持 M 系列芯片
3. VMware 个人版本免费
4. VMware tech preview 版本已经支持 macOS 与虚拟机之间互相拖拽文件、复制粘贴

## 安装教程

安装教程很简单，但是相比 PD 麻烦一点。这里推荐这个[教程](https://youtu.be/vtck5BVjVHM?si=nsNpgXIZAT-QihfH)，基本讲的很详细，需要注意的是，如果有拖拽文件、复制粘贴的需求，需要下载 tech preview 版本。其余操作都一样。

需要关注以下几个点，大家在安装的时候可以注意一下，会节省很多时间：

1. 下载 VMware 的时候需要关闭 clashx pro 的增强模式。否则会导致安装后 VMware 的网络功能失效。其他代理工具没试过，暂不知道是否 surge 等会不会出现同样的问题。
2. 使用 Google 搜索 VMware tech preview 官网下载。因为关闭增强模式后终端没有代理，Homebrew 等工具无法下载。
3. 视频中提到的：镜像安装开始的时候一定要 Enter 跳过；无网络链接那一步使用快捷键调出命令行；虚拟机安装完成后安装 VMware tools 为虚拟机安装驱动。

## 相关链接

VMware tech preview 下载：[Download VMware Fusion Public Tech Preview 2023](https://customerconnect.vmware.com/downloads/get-download?downloadGroup=FUS-TP2023)

VMware 正式版下载：[下载 VMware Fusion | VMware | CN](https://www.vmware.com/cn/products/fusion/fusion-evaluation.html)

安装教程：[YouTube](https://youtu.be/vtck5BVjVHM?si=nsNpgXIZAT-QihfH)
