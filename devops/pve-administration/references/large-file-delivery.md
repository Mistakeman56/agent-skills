# 把大文件交给用户（聊天发不了时）

## 先算渠道上限，再答应"发给我"

用户说"发我微信里"时，先看文件大小和渠道能装多少，别先动手：

| 渠道 | 单文件上限 |
|---|---|
| 微信/IM 聊天 | 约 100 MB（部分桌面版放宽，机器人通道更严） |
| Agent 邮箱附件 | 20 MB（`agently-cli auth status` 的 `max_attachment_size_bytes`） |
| 局域网 HTTP（Caddy 静态目录） | 无实际上限，速度走内网千兆 |
| NAS 共享 / SSH 推送 | 无实际上限 |

超过上限时**直接说清楚发不了并给替代路径**，不要分卷——把 631 MB 切成 7 个包让对方下载再合并，比原路下载更麻烦，且中间错一个包全废。

两个可用替代：

- **PC 就在内网** → 走 Caddy 静态根，内网直连最快：`https://<内网IP>:<端口>/path/file`（证书是签给域名的，需点"继续前往"）；域名走 NAT 回环则受**上行带宽**限制。
- **目标就是长期存放** → 直接推到 NAS，见下。

判断真实需求再选：做启动 U 盘 → 文件最终必须落到 PC，浏览器下载才是正路；只想手机上留一份 → 手机也做不了盘，没意义。

## 推到绿联 NAS（UGOS）：用 SSH 管道，不用 scp

**症状**：`ssh` 跑 `ls`/`touch`/`mv` 全部正常（目录 `drwxrwxrwx`），但 `scp` 报 `dest open /path/file: No such file or directory`——连写到确定可写的家目录也失败。

**这是 SFTP 子系统被限制，不是权限问题。** 判据：ssh 里 `touch` 能建文件而 scp 报不存在，就是 SFTP 被限。

**可用的传输方式**（不经过 SFTP）：

```bash
export SSHPASS='...'
time sh -c 'cat /path/big.iso | sshpass -e ssh -o StrictHostKeyChecking=no USER@NAS "cat > /tmp/big.iso"'
# 631 MB 在千兆内网约 7 秒（≈750 Mbps）
timeout 40 sshpass -e ssh USER@NAS 'stat -c "%s" /tmp/big.iso'
```

传完**必须两端对比字节数**，再在目标端跑一次 `sha256sum` 对照源值；字节数对上不等于内容对。

## 中文路径：scp 会毁掉，ssh 不会

`scp local USER@NAS:"/home/u/资源库/系统镜像/"` 会把 UTF-8 路径转成八进制转义，远端解析失败（即使该目录存在且可写）。而 **ssh 命令行传中文正常**（`ssh NAS 'ls -ld "/home/u/资源库"'` 能跑）。

所以固定两步：**先传到 ASCII 路径，再在远端 shell 里 `mv` 到中文目录**。

```bash
sshpass -e ssh USER@NAS 'mv -f /tmp/big.iso "/home/u/资源库/系统镜像/big.iso"'
```

## 推之前先看空间

```bash
sshpass -e ssh USER@NAS 'df -h /home | tail -2'
```

顺手把"这个卷只剩 151G / 已用 96%"告诉用户——他往往不知道快满了，而事后写不进去更难查。同样顺手 `ls` 一下目标目录，可能已经有同名或相关的镜像，省得重复下载。
