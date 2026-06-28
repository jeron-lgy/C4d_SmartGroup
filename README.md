# Smart Group Select for Cinema 4D 2025.2

[English Version](README.en.md)

Smart Group Select 是一个 Cinema 4D 2025.2 插件，用来把 Null 对象作为智能组根节点。启用后，选择组内子物体会自动跳转到对应的 Null，方便直接对整组移动、旋转和缩放。

插件还包含视图边界框、轴心置底/落地工具，以及 Octane 灯光 Pass Mask 辅助功能。

## 安装

1. 在 Release 页面下载 `SmartGroup_v1.0.0.zip`。
2. 解压压缩包。
3. 将整个 `SmartGroupNull` 文件夹复制到 Cinema 4D 的 plugins 目录。
4. 重启 Cinema 4D 2025.2。

Windows 常见插件目录：

```text
C:\Users\<you>\AppData\Roaming\Maxon\Maxon Cinema 4D 2025_*\plugins
```

## 命令

- `Mark Group`
  给选中的 Null 添加智能组标记。
- `Unmark`
  移除选中对象上的智能组标记。
- `Master Toggle`
  启用或停用所有智能组功能。
- `Toggle Group`
  切换当前智能组的启用状态。
- `Axis Bottom`
  将所选智能组的轴心移动到世界坐标底部中心，同时保持子物体位置不变。
- `Axis Ground`
  先将轴心移动到世界坐标底部中心，再把整组移动到世界 Y=0 地面。
- `Light Mask`
  给选中对象设置 Octane Object Tag 的 Light Pass Mask。

## 说明

插件文件夹名是 `SmartGroupNull`，安装时请保持这个文件夹名不变。
