# LinkScope

LinkScope 是一个本地 Windows 桌面工具，用于扫描和管理目录联接 (Junction) 与符号链接 (Symlink)。

## 运行方式

任选一种方式启动：

```powershell
python main.py
```

或者直接双击 `run_linkscope.bat`。

## 功能

- 选择根目录并递归扫描所有链接
- 查看目录联接 (Junction)、目录符号链接 (Directory Symlink)、文件符号链接 (File Symlink)
- 按类型、链接盘符、目标盘符筛选结果
- 点击列标题排序，支持名称、类型、路径、目标、状态、修改时间
- 新建目录联接 (Junction) 或符号链接 (Symlink)
- 删除所选链接且不删除其目标
- 右键菜单：定位到资源管理器、打开链接/目标路径、复制路径

## 项目结构

```
link_manager/
  __init__.py       # 包初始化
  models.py         # 数据模型（LinkEntry、ScanEvent）
  scanner.py        # 文件系统扫描引擎（后台线程）
  link_ops.py       # 链接操作（创建、删除、打开、定位）
  path_utils.py     # 路径规范化工具函数
  dialogs.py        # 新建链接对话框
  app.py            # 主应用窗口
tests/
  test_models.py    # 数据模型测试
  test_scanner.py   # 扫描器测试
  test_link_ops.py  # 链接操作测试
  test_path_utils.py # 路径工具测试
main.py             # 应用入口
```

## 测试

```powershell
python -m unittest discover -s tests
```

## CI/CD

项目已接入 GitHub Actions：

- CI：向 `main` 分支推送或发起 Pull Request 时，自动执行语法编译检查和 `unittest`
- CD：手动触发工作流或推送 `v*` 标签时，自动打包 Windows 单文件程序并上传构建产物
- Release：推送 `v1.0.0` 这类标签时，会额外创建 GitHub Release，附带 zip 包并写入仓库内维护的发布说明

发布示例：

```powershell
git tag v0.1.0
git push origin v0.1.0
```

## 发布与下载

- 首个正式版本按 `v0.1.0` 发布
- 推送 `v*` 标签后，GitHub Actions 会自动构建 `LinkScope.exe` 并生成 `LinkScope-<tag>-windows-x64.zip`
- Release 页面会包含可直接下载的 Windows 压缩包，以及运行要求和已知限制说明
- 打包产物为单文件 `exe`，目标用户无需预装 Python

## 说明

- 无第三方运行时依赖，仅使用 Python 标准库
- 创建符号链接 (Symlink) 可能需要管理员权限，或在 Windows 中启用开发者模式
- 创建目录联接 (Junction) 时，目标文件夹必须已经存在
- 需要 Python 3.10+
