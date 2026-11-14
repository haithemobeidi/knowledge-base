---
stack: [ffmpeg, video, screen-recording, support, privacy, windows]
kind: howto
last_verified: 2026-11-13
---

# Cut a screen recording down to the steps that matter: find the activity with scene detection, check each cut, then trim and join

**One-liner:** a 150-second, 139 MB reproduction video was mostly waiting (an inbox until the email arrived, other windows). ffmpeg's scene detection lists every moment the screen changes, so the idle stretches show up as gaps; contact sheets at the edges confirm each cut, and `trim` + `concat` keeps only the steps. Result: 75 s, 1.4 MB, every step of the bug kept, original untouched. The same pass is a privacy check: a support recording shows other customers' email subjects, photos in a file picker and login codes, so look at what is left on screen.

*A Zendesk bug report, 2026-11-13, ffmpeg 9.0.1 (gyan.dev full build) on Windows 11.*

## 1. Find when the screen changes

```bash
ffmpeg -hide_banner -i in.mp4 -vf "select='gt(scene,0.02)',showinfo" -fps_mode vfr -f null - 2>&1 \
  | grep -o "pts_time:[0-9.]*"
```

Each line is a moment the picture changed. Keep the threshold low (0.02): a screen recording changes very little from frame to frame, often just a cursor or a typed character, and the 0.3 to 0.4 usually suggested is tuned for camera footage. Long gaps between timestamps are the idle stretches. ffmpeg 9 rejects `-vsync`; use `-fps_mode`.

## 2. Look before you cut

Pull one frame either side of each planned cut and tile them:

```bash
ffmpeg -ss 26 -i in.mp4 -frames:v 1 cut_026.png       # repeat per edge, or:
ffmpeg -i in.mp4 -vf "fps=1/2,scale=380:-1,tile=6x5" sheet_%02d.png   # one frame every 2 s, 60 s per sheet
```

Read the frames by tile order. Don't label them with `drawtext` on a stock Windows build: with no fontconfig set up it crashes ([[screen-recordings-lie-about-luminance]]). Check that every step of the reproduction is inside a kept segment: the click, the page that loads, the error text.

## 3. Trim, join, encode

```bash
SEGS="0:26 31.2:36.4 43.45:57.8 96.5:102 121.5:133.2 139.6:149.75"
FC=""; N=0
for s in $SEGS; do a=${s%:*}; b=${s#*:}
  FC="$FC[0:v]trim=start=$a:end=$b,setpts=PTS-STARTPTS[v$N];"; N=$((N+1)); done
for i in $(seq 0 $((N-1))); do FC="$FC[v$i]"; done
FC="${FC}concat=n=$N:v=1:a=0,fps=15,tpad=stop_mode=clone:stop_duration=2[out]"
ffmpeg -i in.mp4 -filter_complex "$FC" -map "[out]" -an \
  -c:v libx264 -preset slow -crf 28 -pix_fmt yuv420p -movflags +faststart out.mp4
```

- `fps=15` is plenty for UI; `tpad` holds the last frame for 2 s so the error stays on screen.
- `-an` drops the audio. Check it is silent first: `ffmpeg -i in.mp4 -vn -af volumedetect -f null -` printed `max_volume: -91.0 dB` here, so nothing was lost. If there is narration, trim the audio with `atrim` and `asetpts` alongside the video instead.
- CRF 28 on mostly static screens is sharp enough to read text. Most of the saving is the re-encode, not the cut: the recorder wrote about 7.4 Mbit/s and the output is about 0.15 Mbit/s at the same 1904×908, while cutting only halved the length.
- Write to a new file. Keep the original for anyone who needs the full context.

## 4. Check the result

Make a contact sheet of `out.mp4` and confirm the steps are in order and readable, and `ffprobe` the duration. Then look at it as the person you will send it to: other customers' data that was on screen (inbox subjects, names, photos in a file picker) and secrets typed during sign-in (one-time codes) should be cut or blurred. Here the cut removed all of it except one already-expired login code being typed, which was called out to the person sharing it.
