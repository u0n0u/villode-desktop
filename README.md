# Villode Desktop

一个面向 Hyprland 的桌面背景管理器，支持静态图片、循环视频和自定义 HTML/网址。

## 功能

- 静态图片委托 Caelestia 统一渲染，不额外创建 Desktop layer
- 视频自动静音、循环播放，通过 WebKitGTK/GStreamer 解码
- 自定义本地 HTML 或 `http://`、`https://` 页面，远程页面默认禁止文件、剪贴板和本地快捷动作权限
- 图形化设置窗口
- `cover`、`contain`、`stretch` 填充方式
- 修改设置后自动重载
- 可在设置中控制登录 Hyprland 后自动运行
- 视频和 HTML 使用 Hyprland background layer，不遮挡普通窗口
- 默认使用低功耗的 Villode Midnight Glass 静态壁纸
- HTML 桌面仍可在设置中按需选择本地文件或网址
- 内置极简、天气和信息看板页面；天气页可跟随 Caelestia 的位置设置
- 静态、视频和 HTML 的上次来源分别保存，切换类型时会自动恢复

## 安装

```bash
git clone https://github.com/Villode/villode-desktop.git
cd villode-desktop
./install.sh --with-deps
```

安装器会：

- 安装 `~/.local/bin/villode-desktop`
- 安装默认主页到 `~/.local/share/villode-desktop/home/`
- 写入 `~/.config/hypr/conf.d/villode-desktop.conf`
- 默认启用登录 Hyprland 后自动运行
- 绑定 `Super+Shift+D` 开关桌面层

不修改 Hyprland：

```bash
./install.sh --with-deps --no-hyprland
```

只安装，不立即启动：

```bash
./install.sh --with-deps --no-start
```

## 图形设置

```bash
villode-desktop --configure
```

设置保存在：

```text
~/.config/villode-desktop/config.json
```

## 命令行

```bash
villode-desktop --set-static ~/Pictures/wallpaper.jpg
villode-desktop --set-video ~/Videos/wallpaper.mp4 --fit cover
villode-desktop --set-html ~/Projects/my-desktop/index.html
villode-desktop --set-html https://example.com
villode-desktop --status
villode-desktop --enable-autostart
villode-desktop --disable-autostart
villode-desktop --autostart-status

villode-desktop --daemon
villode-desktop --toggle
villode-desktop --reload
villode-desktop --quit
```

## 性能建议

- 日常使用优先选择静态图片模式（无额外 WebKit 图层，最凉）
- 视频建议使用 `1920×1080`、24/30 FPS、H.264；避免 4K / 60 FPS
- HTML 页面复杂度和持续动画会直接影响 CPU/GPU 占用
- **省电（默认开启）**：检测到全屏窗口、锁屏或显示器 DPMS 关闭时，自动暂停视频与 CSS 动画
- **渲染缩放（默认 85%）**：降低 WebKit 缩放可明显降温；设置里可调 100% / 85% / 75% / 60%
- CLI：`villode-desktop --playback-scale 0.75` 或 `--no-power-save`

## 依赖

静态壁纸由 Caelestia Shell 统一显示，因此请先安装 Villode Caelestia；统一安装器会自动按正确顺序部署。

Arch:

```bash
sudo pacman -S --needed python python-gobject gtk3 \
  gtk-layer-shell webkit2gtk-4.1 gstreamer gst-plugins-base \
  gst-plugins-good gst-libav gst-plugins-bad gst-plugins-ugly \
  gst-plugin-va
```

> 视频壁纸依赖 `gst-plugins-good` 中的 `qtdemux` 解析 MP4。若缺此包，WebKit 会黑屏并提示无法播放。

Debian/Ubuntu:

```bash
sudo apt install python3 python3-gi \
  gir1.2-gtk-3.0 gir1.2-gtk-layer-shell-0.1 gir1.2-webkit2-4.1 \
  gstreamer1.0-plugins-base gstreamer1.0-libav \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad
```

## 卸载

```bash
./uninstall.sh
```

同时删除壁纸配置：

```bash
./uninstall.sh --purge
```

## 许可证

本项目源码公开，但不是无限制商业开源授权。个人、学习、研究和非商业使用规则见 [LICENSE](LICENSE)。
