# CEF 104 验证矩阵

固定源码为 Chromium `104.0.5112.102`、CEF `ee9413170c23`、V8 `74d856b8309d`；两套配置均使用 SDK 12.3。

| 配置 | arm64 编译 | x64 编译 | Universal 四个核心 Mach-O | 最低系统 / SDK | V8 双快照 | 实机运行 |
| --- | --- | --- | --- | --- | --- | --- |
| macOS 11.0 | 已完成 | 已完成 | 已验证 | 11.0 / 12.3 | 已验证 | 待 macOS 11 实机 |
| macOS 12.0 | 已完成 | 已完成 | 已验证 | 12.0 / 12.3 | 已验证 | 待 macOS 12 实机 |

主机工具：Apple Silicon 已完成两套增量构建验收；Intel 工具已在 Rosetta 完成版本、架构、执行和最小编译检查。Intel Mac 上的 `setup`、`doctor` 和至少一套完整 Universal 构建仍待执行，完成前不标记为 Intel 实机全量验证。
