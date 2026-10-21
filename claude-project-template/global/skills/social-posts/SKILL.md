---
name: social-posts
description: Make social posts (Instagram Reels, TikTok, and their captions, hashtags and covers) for one of Haithem's apps — "make social posts for this app", "cut a reel", "what do I write for the post", "hashtags?", "thumbnail?". Reads the project to find the real pitch, researches each platform's CURRENT rules, cuts vertical videos from real screen recordings with the bundled builder, writes captions in his voice, runs an ethics check, and hands over a posting checklist. Use whenever he wants promo content for a project; not for store listings (Play/App Store screenshots have their own rules).
---

# Social posts

You are making promo content for an app Haithem built. The deliverable is a folder he can post from: one video per platform, a cover, a caption per platform, and the music licence, plus a short checklist of what to tap. He decides; you research, recommend with sources, build and verify.

**His default:** "go with recs based on data." Lead with ONE recommendation backed by sources (label official vs third-party), give the trade-off in a line, and let him accept in one word. When the choice is visual (a layout, a cover), render the options as stills, don't describe them.

## 1. Find the real pitch (read the project, don't invent)

- Read the project's CLAUDE.md, README, landing copy and store listing. Pull out: the one pain the app solves, in the user's own words; the 4–6 features that show it best; the platforms it ships on; what it costs (free/paid/trial, stated plainly).
- **Every claim in a post must be true of the SHIPPED app today.** Grep the code for anything load-bearing ("syncs with Steam", "works offline"). A feature that is built but unreleased does not go in a post.
- The hook is the pain as a question the viewer already asks themselves ("Ever come back to a game after three weeks with no idea what you were doing?"). It opens the video AND the caption.

## 2. Research the platforms' CURRENT rules

Platforms change their rules every few months. Before building, send a Sonnet research subagent (never search inline) with today's date, official sources first, a claim / source / date / verbatim quote per finding, and older-than-a-year sources flagged. Then verify the load-bearing claims yourself (fetch the source, read the quote).

**The baseline, verified 2026-09-27, Instagram rows extended 2026-10-19** (re-check anything older than ~3 months):

| Rule | Source | Strength |
|---|---|---|
| Instagram: **max 5 hashtags** per post/Reel, in the caption ("Starting today, Instagram will allow up to 5 hashtags in a reel or post", 2025-12-18); a first-comment placement has no official backing | @creators on Threads; Social Media Today quoting it | official |
| Instagram: "using fewer (up to 5) more targeted hashtags, rather than many generic ones, can improve both your content's performance" — hashtags "can play a role in discovery"; shares and watch-through rank Reels more | same announcement; Instagram's "Ranking Explained" | official |
| Meta Reels safe zone: "leaving at least **14% of the top, 35% of the bottom, and 6% on each side**... free from text, logos" → on 1080×1920: top 269, bottom 672, sides 65 px | facebook.com/business/ads-guide (Instagram Reels) | official (ads guide, used as the organic proxy) |
| TikTok: "Introduce your content proposition in the **first 3 seconds**"; "Prioritize your hook in the first 6 seconds" | TikTok for Business creative best practices | official |
| TikTok publishes no fixed safe-zone table; practical clear area ≈ top 130, bottom 480, right 140, left 60 px | third-party, conflicting | weak |
| Format: 1080×1920, 9:16, H.264 + AAC, 30 fps. A 16:9 video posts as a Reel but letterboxed | Meta + TikTok specs | official |
| Length: no official target on either. Reels 45–60 s did best in a 2026 study of 6M Reels; TikTok "faster" is third-party advice | third-party | medium / weak |
| Instagram profile grid crops covers to **3:4** (since Jan 2025, Mosseri); TikTok's grid crop is disputed (1:1 vs 3:4) → keep cover text in the centre square | third-party reporting an official announcement | medium |
| Instagram: accounts that "primarily post unoriginal content in photos or carousel posts" are no longer recommended (extended from Reels, May 2026); third-party material must be "materially" added to, e.g. "unique text on the content itself that provides more context than just describing what's happening" → a news/aggregator post needs its own angle | Instagram announcement quoted by MediaPost, 2026-05-01 | official (via press) |
| Instagram feed images: **3:4 (1080×1440)** shows uncropped: "if you upload a 3:4 image, it'll now appear just exactly as you shot it"; 4:5 still works but the 3:4 grid crops it; some schedulers still force 4:5. The web uploader starts on a square crop → pick **Original** (re-confirmed on instagram.com 2026-10-20) | Mosseri on Threads, via RouteNote 2025-05-29 | official (via press) |
| Carousels: a skipped carousel may get "a second chance", re-shown from **slide 2** → slide 2 must stand on its own; carousels lead feed engagement (~0.55% vs Reels ~0.50% vs single images ~0.35%) | Mosseri via Social Media Today 2024-10-17; Socialinsider Q1 2026 | official + study |
| Top ranking signals: "watch time, likes and sends"; sends weigh most for reaching non-followers. Posts that "explicitly ask for engagement through shares, comments, tags" are not recommended | Mosseri via Social Media Today 2025-01-22; Instagram via SMT 2024-06-05 | official (via press) |
| Never use an image model for a post about a real game or product: invented art, the "AI info" label, and stale facts. Official art in HTML templates instead | `news-graphics-from-research-and-official-art-not-an-image-model.md` | lesson |
| Links in captions are never clickable; a Reel link sticker needs 10k followers → "Link in bio" | long-standing | high |
| Instagram throttles videos detected as reposted from TikTok (watermark / audio / hash signals) → post each file natively on each app | Instagram 2026 originality detection, third-party | medium |
| Baked-in licensed music is not what TikTok's Commercial Music Library restricts (that governs the in-app sound picker), but BOTH apps fingerprint audio, and stock tracks registered for Content ID can be flagged → keep the licence certificate | TikTok CML page (official) + Pixabay's blog | official + vendor |

## 3. Gather real assets

- **Real screen recordings of the real app, never re-rendered UI.** A project may already have takes (Playmoir: its social kit already holds the config, `docs/marketing/social-agent/video/config.js`, wired to the takes in `docs/store/play/video/clips/`; work there, and keep the kit's copy of the builder in step with this one). If not, record the device/app: one take per feature, scripted, 8–15 s each, demo data that looks lived-in, no personal data on screen.
- **Music:** a licensed track (Pixabay, YouTube Audio Library). Download the **licence certificate** with it. Pixabay: signed in, the track page → the arrow beside "Free download" → "Download certificate" (a .txt). He signs in himself; never enter his password.
- Fonts: the app's own font files (the scene page takes paths).

## 4. Build the cuts

The builder lives beside this file: `build-vertical.mjs` + `scene-vertical.html` + `example-config.js`.

1. Copy `example-config.js` into the project (e.g. `docs/social/config.js`), fill it: brand word/accent/fonts, `clipsDir`, `music`, `hook`, `scenes` (a title card, one scene per feature: kicker + a 3–6 word title + one concrete sub line, an end card), `cuts` (Reels = full set; TikTok = hook + the three strongest scenes + end card, ~30 s). Gitignore the clips/music/out folders.
2. **Review first:** `node <skill>/build-vertical.mjs <config.js> reels --review` renders one still per scene with the safe zones drawn (red = Instagram covers, dashed = TikTok's clear area). Show him the stills.
3. Build: `node <skill>/build-vertical.mjs <config.js> reels --cover`, then `... tiktok`. Layout is "full bleed": the recording fills the frame (scaled + centre-cropped), the caption sits on a solid scrim in the safe top band, the hook card opens, the brand card closes, music fades in/out at −14 LUFS.
4. **Verify objectively, never by eye** (his eyes judge the look): `ffprobe` each file (1080×1920, 30 fps, h264 + aac, the expected length), and check a caption layer PNG is not empty (alpha extrema not (0,0), text pixels present in the copy box) — an exception in the scene page renders a silent, fully transparent layer.
5. Gather the deliverables into one folder named for what they are: `INSTAGRAM-reel.mp4`, `TIKTOK.mp4`, `COVER-both.png`, `music-license.txt`. Open it for him.

## 5. Write the captions

- First line = the hook question. Then two or three short lines: what the app does, told as what the viewer gets. Then platforms. Then "Link in bio."
- **5 hashtags max, at the end of the caption.** Specific over broad (#backlog beats #gaming for a small account). Label hashtag picks as judgement: nothing official ranks them.
- His copy rules: **no em-dashes** (they read as AI writing); plain words; no hype adjectives; no "revolutionary"; the product name as he spells it.
- Offer two options at most (e.g. A: the question hook, B: a search-friendly first line), recommend one, and say why in a line.

## 6. Ethics check (his standing law, applied to marketing)

Marketing is persuasion; his rule is persuasion only in the user's own interest ("help them, never hook them"). Before handing over, check every post:

- **No fake urgency or scarcity** ("only today", "last chance", countdowns) unless literally true.
- **No invented numbers, reviews, testimonials or user counts.** A stat needs a source he can point to.
- **No claims the shipped app doesn't back** (step 1). No "AI-powered" as a headline if the AI is optional — say optional.
- **Be plain about money:** if it's paid, the post doesn't imply free.
- **No engagement bait** ("comment YES to get the link", "tag 3 friends").
- **Privacy:** no real user data, names or accounts in the footage; demo data only.
- Anything gray → run `/dark-pattern` on it rather than deciding here.

## 7. Hand over (posting checklist)

1. Post each file **natively** on its own app (never re-upload a TikTok download to Instagram).
2. **Instagram on desktop web:** after picking the file, tap the crop icon (two corner arrows, bottom-left of the preview) → **Original**; the web uploader defaults to a square and cuts the top and bottom. Every video posted there becomes a Reel, even though the button says "Create new post". From the phone app, upload as a Reel.
3. Cover: "Edit cover" → "Add from camera roll" → the cover PNG.
4. Paste the caption; link in bio set.
5. If the audio gets flagged or muted: dispute with the licence certificate.
6. If he asks, set the post up in his **already signed-in** browser (upload, crop, caption, cover) and stop: **never press Post, Share or Schedule, never reply or DM, never type a password** (ruling 2026-10-20). He reviews and presses Share.

## After

If a post surfaced something new (a crop trap, a rule change), fix this skill in the Knowledge Base and bump the "verified" date in step 2. Scheduling, auto-posting and analytics are a separate decision: research existing tools and the official posting APIs first, don't build one on reflex.
