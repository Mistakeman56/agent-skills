# Delivering large files to the user's devices

## The channel limit decides the plan, not the file size

WeChat's per-file cap through the bot is on the order of 100 MB. A 631 MB Debian netinst ISO is six times over it — do not offer to split it into volumes. Seven 90 MB parts the user must fetch individually, concatenate and re-verify is strictly worse than one link, and one bad part destroys the image.

Order of preference:

1. **NAS drop** — the user browses it from any machine and copies straight to the target device. This is usually what they want when the file is destined for a USB stick, because the file has to land on a computer anyway.
2. **LAN URL** — fastest transfer, but only if the URL is genuinely reachable. An authenticated reverse-proxy path that 302s to a login page reads to the user as "the link doesn't open"; check it with a real request before sending it.
3. **Public URL** — limited by upload bandwidth (~42 Mbps here, so roughly 2 minutes for 631 MB).
4. Splitting into volumes — last resort. State why it's bad before doing it.

## NAS landing spot

- Host: UGOS NAS `192.0.2.10`, SSH user `user`.
- System-image library: `/home/user/资源库/系统镜像/` — world-writable and already holding other ISOs, so check for an existing copy before transferring.
- **Check the volume first.** That pool runs near 96% full; run `df -h /home` before assuming there is room.

## The transfer technique that works

`scp` fails against this NAS for two independent reasons:

1. **The SFTP subsystem refuses writes.** `scp file user@host:/home/user/x.iso` returns `dest open ... No such file or directory` even though the directory exists and a plain `touch` over the same SSH connection succeeds.
2. **`scp` mangles non-ASCII paths.** A UTF-8 Chinese directory name goes out as octal escapes and the remote side cannot resolve it.

Both disappear with an SSH pipe, which bypasses SFTP and hands the path to a shell:

```bash
export SSHPASS='...'
cat /path/localfile.iso | sshpass -e ssh -o StrictHostKeyChecking=no user@192.0.2.10 \
  'cat > /home/user/debian-netinst.iso'
```

Stage to an ASCII path, then `mv` into the Chinese directory over SSH — the command line passes UTF-8 correctly even though `scp` does not:

```bash
sshpass -e ssh user@192.0.2.10 \
  'mv -f /home/user/debian-netinst.iso "/home/user/资源库/系统镜像/"'
```

631 MB over gigabit LAN takes about 7 seconds (~754 Mbps). A transfer still running past a minute is a channel problem, not a slow disk.

## Always verify both ends

```bash
stat -c "%s bytes" /remote/path
sha256sum /remote/path
```

Byte count first (catches truncation), then the hash against the published value (catches corruption). Report both numbers alongside the path — "sent it" is not evidence.
