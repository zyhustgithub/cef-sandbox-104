# Chrome / CEF 104 架构文档

Chrome 是浏览器产品；Chromium 是其开源基础；CEF 在 Chromium 上提供供应用嵌入浏览器的接口。CEF 复用 Chromium 的页面引擎、进程模型、网络与图形设施，不是通过控制已安装的 Chrome 来工作。

本文以本工作区 **Chromium 104.0.5112.102 / CEF 104** 为准，不代表新版 CEF 的运行时行为。用户指定路径中的 `chromemium` 按现有目录名 `chromium` 处理。

| 文档 | 内容 |
|---|---|
| [Chrome 模块架构](Chrome模块架构.md) | 产品层、Content、Blink/V8、网络、图形及进程通信 |
| [CEF 模块架构](CEF模块架构.md) | API、包装层、运行时、宿主集成及调用链 |
| [Chrome 与 CEF 依赖关系](Chrome与CEF依赖关系.md) | 源码、构建、二进制、部署依赖和排查入口 |
| [CEF 104 自定义补丁说明](CEF104自定义补丁说明.md) | 本工作区已有补丁说明 |

图中模块箭头 `A → B` 表示 A 使用或依赖 B；进程图、时序图中的箭头表示通信或调用。它们是核心关系示意，不是完整 GN 目标依赖图；目录、构建目标、动态库和进程并非一一对应。

版本依据：[Chromium VERSION](../src/chrome/VERSION)、[CEF 兼容版本](../src/cef/CHROMIUM_BUILD_COMPATIBILITY.txt) 和 [工作区固定配置](../../config/build-profiles.json)。配置中的提交号是构建基线，不等同于未提交的本地修改。
