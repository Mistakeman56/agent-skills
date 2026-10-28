# N5095 Mini PC (Homelab Streaming Box)

**Device**: N5095 fanless mini PC (魔改版), Ubuntu 24.04.
**SSH**: `cym/user@192.0.2.10`, port 22. Hostname: `cym-n5095`.
**GPU**: Intel JasperLake UHD Graphics, i915 driver, VAAPI hardware decode (H.264/VP8/JPEG).

## eDP Phantom Display (Hardware Mod Issue)

This N5095 exposes a phantom eDP virtual display that steals focus from HDMI.

**Fix (in OS):**
```bash
xrandr --output eDP-1 --off
```

**Persistent fix:**
```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/disable-edp.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Disable eDP
Exec=xrandr --output eDP-1 --off
X-GNOME-Autostart-enabled=true
EOF
```

## Ubuntu Installation on HDMI-Only Output

GRUB parameter `video=HDMI-A-1:e` does NOT work. **Use `nomodeset`**:
1. At GRUB menu, press `e` to edit
2. On the `linux` line, add `nomodeset` at the end
3. Press `F10` to boot
4. After installation, disable eDP via xrandr autostart

## Ethernet DHCP Issue

N5095 gets link but DHCP fails after reboot:
```bash
sudo nmcli device disconnect enp1s0
sudo nmcli device connect enp1s0
# If still fails:
sudo dhclient enp1s0
```

## PipeWire / PulseAudio HDMI Audio Output

When HDMI audio goes to analog instead of HDMI→TV→speakers:
```bash
pactl list sinks short
pactl get-default-sink
# Switch to HDMI:
pactl set-card-profile alsa_card.pci-0000_00_1f.3 output:hdmi-stereo+input:analog-stereo
```

**Pitfall:** `pactl` may not be installed on fresh Ubuntu. Install with `sudo apt install -y pulseaudio-utils`.
