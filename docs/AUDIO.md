# Optional audio

Trap Team audio draining/playback exists but has not been verified on the actual
PS3 setup. Without an ALSA device setting, incoming audio is silently drained.

Set `SKYLANDERS_AUDIO_DEVICE=default` (or a specific ALSA device) in
`/etc/skylanders-zero.env`, then restart skylanders-web. Playback uses aplay with
8 kHz, signed 16-bit little-endian mono PCM. The Zero W has no analogue audio jack;
HDMI or suitable I2S/ALSA hardware is needed. The USB data port is occupied by the
console gadget and cannot also host an ordinary USB sound card.
