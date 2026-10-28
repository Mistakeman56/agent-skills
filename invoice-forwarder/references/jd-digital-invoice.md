# 京东数电发票邮件处理

来源：`customer_service@jd.com`，主题「您的京东订单【xxx】电子发票已开具」。
开票方可能是京东自营的各地贸易公司（如"大连京东达扬贸易有限公司"）。

## 特征（与普通附件邮件不同）
- `has_attachments: false` / `attachment_count: 0` —— `agently-cli attachment +download` 用不上
- 正文是 HTML，内含两个直链：
  - PDF：`https://eicore-invoice-26.s3.cn-north-1.jdcloud-oss.com/digital-invoice/digital_<发票号码>.pdf?AWSAccessKeyId=...&Expires=...&Signature=...`
  - XML：`https://eicore-invoice-26.s3.cn-north-1.jdcloud-oss.com/digital-invoice/invoice_xml_<发票号码>.xml?...`
- 链接带签名和有效期（Expires 很长），抓到后尽快下载；国内 OSS 域名，无需代理

## 步骤
1. `agently-cli message +read --id <msg_id>` 拿到完整正文
2. 从正文提取 PDF 直链：正则匹配
   `https://eicore-invoice-26\.s3\.cn-north-1\.jdcloud-oss\.com/digital-invoice/digital_\d+\.pdf[^"'<\s]*`
   （注意 URL 中 `&amp;` 是 HTML 转义，需还原为 `&`）
3. 先 unset 全部代理变量（含 ALL_PROXY/CLASH_PROXY），再
   `curl -sSL -o ~/.hermes/office-docs/digital_<发票号码>.pdf "<url>"`
4. 用 `pdftotext <pdf> -`（无则 pypdf/PyPDF2）提取文本，拿品名/数量/金额/税率/开票日期/购销双方，用于在回复中向assistant描述发票内容
5. 在最终回复中附 `MEDIA:~/.hermes/office-docs/digital_<发票号码>.pdf`

## 实测验证（2026-07-31）
- 订单 3574429017324747，发票号码 26917000000045347377：小米商务双肩包 × 1，¥251.35（13%），开票 2026-07-30
- 下载产物：约 100KB，PDF 1.7，1 页
- pdftotext 输出含：购买方/销售方名称与税号、项目名称、单价数量、金额、税率、价税合计、开票人、订单号

## 已读标记
`agently-cli message +read` 读取后会自动标记已读（本机 v1.0.6 无 `--mark-read` 标志、也无独立 mark-read 子命令）。
验证方法：`agently-cli message +list --dir inbox --is-unread` 应返回空列表。
