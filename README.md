# CEF 104 macOS Universal 构建

本仓库用一个入口构建 CEF 104 Universal Framework，正式支持最低 macOS 11.0 和 12.0，默认构建 12.0。两套配置均固定使用 SDK 12.3，并合并 arm64 与 x86_64 产物。

![构建流程](docs/images/build-flow.svg)

## 环境要求

- Apple Silicon 或 Intel Mac
- 已安装并接受许可的 Xcode / Command Line Tools
- Python 3.8+、Git 和 Git LFS
- 可访问本项目及其私有子仓的 GitHub 账号

Xcode/CLT 不在仓库内。固定的 SDK、Clang、GN 和 depot runtime 由 Git LFS 下载。

## 首次初始化

```bash
git lfs install
git clone --recurse-submodules https://github.com/zyhustgithub/cef-sandbox-104.git
cd cef-sandbox-104
./cef-build setup
./cef-build doctor
```

## 构建

```bash
# 默认：最低 macOS 12.0
./cef-build build

# 最低 macOS 11.0
./cef-build build macos11

# 显式选择 12.0 或并发数
./cef-build build macos12 --jobs 8
```

最终产物分别位于：

- `out/macos11/Chromium Embedded Framework.framework`
- `out/macos12/Chromium Embedded Framework.framework`

每个输出旁的 `build-manifest.json` 记录源码提交、工具版本、GN 参数、架构、最低系统版本和 SHA256。

环境、LFS、工具架构或源码版本异常时先运行 `./cef-build doctor`。构建机制与清理命令见 [构建说明](docs/build-guide.md)，已验证范围见 [验证矩阵](docs/verification-matrix.md)。
