# Villode Desktop

一个运行在 Hyprland background layer 中的桌面背景管理器，支持静态图片、循环视频和自定义 HTML/网址。

## 功能

- 静态图片由 GTK 原生绘制，不启动 WebKit，空闲功耗最低
- 视频自动静音、循环播放，通过 WebKitGTK/GStreamer 解码
- 自定义本地 HTML 或 `http://`、`https://` 页面
- 图形化设置窗口
- `cover`、`contain`、`stretch` 填充方式
- 修改设置后自动重载
- 可在设置中控制登录 Hyprland 后自动运行
- Hyprland background layer，不遮挡普通窗口
- 随附 Villode 自有的玻璃风格 HTML 首页

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

- 日常使用优先选择静态图片模式
- 视频建议使用 `1920×1080`、24/30 FPS、H.264
- HTML 页面复杂度和持续动画会直接影响 CPU/GPU 占用
- 页面隐藏时，内置视频模式会自动暂停播放

## 依赖

Arch:

```bash
sudo pacman -S --needed python python-gobject python-cairo gtk3 \
  gtk-layer-shell webkit2gtk-4.1 gstreamer gst-libav gst-plugins-bad \
  gst-plugins-ugly gst-plugin-va
```

Debian/Ubuntu:

```bash
sudo apt install python3 python3-gi python3-cairo \
  gir1.2-gtk-3.0 gir1.2-gtk-layer-shell-0.1 gir1.2-webkit2-4.1 \
  gstreamer1.0-libav gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad
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
