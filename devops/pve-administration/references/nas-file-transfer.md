# 往 NAS 传大文件（绿联 UGOS / DXP4800）

场景：把 ISO、系统镜像、备份从 CT <ID> 送到内网 NAS（或反向取回）。
NAS：`user@192.0.2.10`，SSH 默认 22，家目录 `/home/user`，用户自己的镜像目录形如 `/home/user/资源库/系统镜像/`。

## 用 SSH 管道，不要用 scp

`scp` 在这台 UGOS NAS 上必定失败：

```
scp: dest open "/home/user/x.iso": No such file or directory
```

两个互相独立的原因，任一都足以让 scp 挂掉，而报文都长成「目录不存在」的样子：

- **SFTP 通道被拒**：普通 SSH 命令能正常 `touch`、`df`、`ls`，但走 sftp 的 scp 一律 `dest open` 失败。
- **中文路径**：scp 把 UTF-8 转成八进制转义（`\350\265\204...`）再交给远端解析，必然 No such file；
  而同一条路径写在 ssh 命令行里完全正常。

**看到 `dest open ... No such file` 先别改路径、别查权限**，用 `ssh host 'touch /路径/.t && rm -f /路径/.t'`
验证一次：能写就是通道问题。

可靠做法（内网千兆实测 631 MB / 7 秒 ≈ 754 Mbps）：

```sh
cat /path/to/file.iso | ssh user@192.0.2.10 'cat > /home/user/tmp.iso'
ssh user@192.0.2.10 'mv -f /home/user/tmp.iso "/home/user/资源库/系统镜像/"'
```

先落英文临时名，再用**远端** `mv` 进中文目录——中文只出现在 ssh 命令行里，不过 scp 的路径转义。
目录名里的空格/中文一律双引号包住。

## 传完必须做两件核对

```sh
ssh host 'stat -c "%s bytes" "/目标路径/file.iso"'   # 字节数必须与源文件完全一致
ssh host 'sha256sum "/目标路径/file.iso"'            # 与源文件 SHA256 逐字比对
```

只比 `ls -lh` 的 `631M` 不够，四舍五入会掩盖截断。交付镜像类文件时把 SHA256 一并发给用户。

## 传前先看空间

`df -h /home`。这台 NAS 长期在 96% 上下（3.6T 只剩 150G 量级），塞大文件前先把这个数字报给用户，
别等写不进去才发现。

## 从 CT <ID> 下载大 ISO 时怎么选源

CT <ID> 出网被路由器 TPROXY 接管、出口在境外（`curl -s https://ip.sb` 确认），国内镜像站表现极不稳定：
实测清华 404 / 153 B、中科大 403、阿里云 0 B、`cdimage.debian.org` 404——**全部不可用**。

先探活再下，用 curl 自带的统计字段（**本机没有 `bc`，别写算式**）：

```sh
curl -sL --max-time 12 -o /dev/null -w '%{http_code} %{speed_download} %{size_download}\n' <url>
```

实测 `mirrors.cloud.tencent.com` 可用（约 39 Mbps，631 MB 两分钟）。腾讯云的 `debian-cd` 只同步到
12.7.0，Debian 13 目录 404；netinst 装完 `apt update` 即到最新，不必为版本号再找源。

## 交付大文件给用户的路径选择

按「用户最终要拿它干什么」定，不要默认走微信：

- 微信单文件上限量级 100 MB，几百 MB 的镜像根本发不进去，**分卷切开只是把麻烦转给用户**（还得合并 + 核对）。
- `https://example.com:18443/...` 走公网域名在内网访问会绕 NAT 回环、受上行带宽限制，而且
  **落在 `/var/www/nav` 下的文件不是公开链接**（该站点前有 forward_auth，curl 得到 302 → `/login`）；
  内网用 IP 访问还会撞证书域名不匹配，`http://` 直连 18443 直接 400。
- **最省事的是直接放进 NAS 用户目录**，用户从 UGOS 桌面 / SMB 映射取，局域网内秒开，且装机场景本来就要落在那台机器上。
