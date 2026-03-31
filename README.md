# LinkScope

LinkScope 是一个本地 Windows 桌面工具，用于扫描和管理目录联接 (Junction) 与符号链接 (Symlink)。

## 运行方式

任选一种方式启动：

```powershell
python main.py
```

或者直接双击 `run_linkscope.bat`。

如果在 PyCharm 中调试，也可以直接运行 `link_manager/app.py`。

## 功能

- 选择根目录并递归扫描
- 查看目录联接 (Junction)、目录符号链接 (Directory Symlink)、文件符号链接 (File Symlink)
- 按类型、目标盘符筛选，并按关键字搜索
- 查看选中项的链接路径、目标路径、状态和修改时间
- 新建目录联接 (Junction) 或符号链接 (Symlink)
- 删除所选链接且不删除其目标
- 打开链接所在目录、在资源管理器中定位、复制路径

## CI/CD

项目已接入 GitHub Actions：

- CI：向 `main` 分支推送或发起 Pull Request 时，自动执行语法编译检查和 `unittest`
- CD：手动触发工作流或推送 `v*` 标签时，自动打包 Windows 单文件程序并上传构建产物
- Release：推送 `v1.0.0` 这类标签时，会额外创建 GitHub Release 并附带 zip 包

发布示例：

```powershell
git tag v0.1.0
git push origin v0.1.0
```

## 说明

- 创建符号链接 (Symlink) 可能需要管理员权限，或在 Windows 中启用开发者模式。
- 创建目录联接 (Junction) 时，目标文件夹必须已经存在。
