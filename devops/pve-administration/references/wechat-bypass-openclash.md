# 微信在 OpenClash 下转圈的排查与修复

## 现象
- 微信消息一直转圈发不出去
- 切到流量秒发
- 时好时坏,非持续性

## 根因
OpenClash 的 fake-IP 模式或 DNS 劫持导致微信的长连接被干扰。微信对 DNS 解析和连接稳定性很敏感，fake-IP 返回的 `198.18.x.x` 可能导致微信连接超时。

## 修复方案

### 方案1: 添加直连规则（推荐，最快）

在 OpenClash 配置文件 `/etc/openclash/config/ddrodog.yaml` 的 rules 段最前面插入：

```yaml
rules:
    - DOMAIN-SUFFIX,weixin.qq.com,DIRECT
    - DOMAIN-SUFFIX,wechat.com,DIRECT
    - DOMAIN-SUFFIX,wx.qq.com,DIRECT
    - DOMAIN-SUFFIX,wx.tencent.com,DIRECT
    - DOMAIN-SUFFIX,tencent.com,DIRECT
    - DOMAIN-SUFFIX,qpic.cn,DIRECT
    - DOMAIN-SUFFIX,qlogo.cn,DIRECT
```

修改后重启 OpenClash: `/etc/init.d/openclash restart`

### 查看当前规则
```bash
ssh root@192.0.2.10 "grep -n 'DOMAIN-SUFFIX,weixin\|wechat\|wx.qq\|tencent\.com\|qpic\|qlogo' /etc/openclash/config/ddrodog.yaml"
```

### 删除直连规则（如果加错了导致其他问题）
```bash
sed -i 'LINE_NUMBERSd' /etc/openclash/config/ddrodog.yaml
# 或者删除一段连续行
sed -i '94,119d' /etc/openclash/config/ddrodog.yaml
```

### 方案2: 关闭 fake-IP 模式
OpenClash 设置 → 模式 → 切到 Redir-Host（兼容模式）。但 fake-IP 防 DNS 污染能力最强，切换需谨慎。

### 方案3: 手机端临时解决
- 开关 WiFi（关 WiFi 再开）
- 开飞行模式再关（重新获取 IP）
- 以上两种能暂时缓解但不治本

## ⚠️ 重要经验教训

### 直连规则不能无脑加！
用户自测后发现加了大量直连规则（微信+淘宝+京东+B站+小红书+拼多多+米家+抖音等20+条）后，**网络反而更卡了**。根因分析：

1. **规则插入位置错误** — 用户家 Clash 配置中 `ChinaMax` 规则集已经包含了国内大厂域名。手动再插一份直连规则产生了重复匹配，增加了匹配开销。
2. **ChinaMax 已经覆盖** — 检查 `ChinaMax` 规则集内容就发现 it 已包含 `tencent.com`, `taobao.com`, `jd.com` 等。额外再插是冗余。
3. **OpenClash 规则顺序敏感** — 不同的规则位置意味着不同的匹配路径，插入不当可能打乱原有的最优匹配顺序。

**正确做法：** 只需加**微信专属问题域名**（因为微信转圈是具体故障案例，可能涉及到 fake-IP 场景下某些域名未被 ChinaMax 覆盖），不要批量加所有国内大厂。

### 恢复原始配置的方法
```bash
# 删除插入的所有自定义直连规则（假设第94-119行）
sed -i '94,119d' /etc/openclash/config/ddrodog.yaml
/etc/init.d/openclash restart
```
