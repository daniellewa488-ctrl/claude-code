# Project Rules — Demo Website Generator

## Image Generation Rule (ALWAYS APPLY)

For every generated demo website, images must be realistic, spacious, correctly cropped, professionally displayed, and visually unique. Use fixed aspect-ratio wrappers, object-fit: cover, object-position: center, large enough image heights, and generous grid spacing. Never stretch, squeeze, overcrowd, repeat, or place tiny images. Every image must be based on the company website/email data and must visually match a different service, section, or business story.

---

### Full Image Generation Standard

**Core rules — never violate these:**
- Never create squeezed, stretched, distorted, repetitive, badly cropped, tiny, overcrowded, or unattractive images
- Never place images too close together
- Never use the same style of image repeatedly across the same website
- Never use generic images that do not match the specific business
- Never let images sit small inside their blocks or leave empty space inside containers

**Step 1 — Understand the business first:**
Before generating any image, read: company name, industry, location, main services, target customers, visual style, website crawl text, and email details. Images must be based on real business data, not random assumptions.

**Step 2 — Image plan by section:**

| Section | Aspect Ratio | Min Height Desktop | Purpose |
|---|---|---|---|
| Hero | 16:9 | 520px | Wide, premium, strong first impression |
| About | 4:3 | 420px | Real work environment, professional and trustworthy |
| Service cards | 4:3 | 280px | One unique image per service, matches that specific service |
| Gallery/projects | 4:3 | 320px | Separate completed projects, different types and angles |
| CTA background | 16:9 | — | Only if it improves the page; add overlay if text sits on top |

**Step 3 — CSS image wrappers (always use this structure):**
```css
.image-wrapper {
  width: 100%; height: 100%; overflow: hidden;
  border-radius: 24px; background: #f3f3f3; position: relative;
}
.image-wrapper.hero   { aspect-ratio: 16/9; min-height: 520px; }
.image-wrapper.about  { aspect-ratio: 4/3;  min-height: 420px; }
.image-wrapper.service{ aspect-ratio: 4/3;  min-height: 280px; }
.image-wrapper.gallery{ aspect-ratio: 4/3;  min-height: 320px; }
.image-wrapper img {
  width: 100%; height: 100%; min-width: 100%; min-height: 100%;
  object-fit: cover; object-position: center; display: block;
}
.project-card { overflow: hidden; border-radius: 24px; }
.project-card .image-wrapper { width: 100%; height: 320px; overflow: hidden; }
.project-card .image-wrapper img { width: 100%; height: 100%; object-fit: cover; object-position: center; display: block; }
@media (max-width: 768px) { .project-card .image-wrapper { height: 260px; } }
```

**Step 4 — Layout spacing rules:**
- Section padding: 96px desktop / 72px tablet / 56px mobile
- Grid gap: min 32px desktop / 24px tablet / 20px mobile
- Max 3 service cards per row on desktop
- Gallery: max 3 columns desktop, 2 tablet, 1 mobile
- Service card inner padding: 24px–32px

**Step 5 — Service-specific image matching:**
Every service image must match the exact service title. A visitor must understand the service from the image alone without reading the text. For landscaping: Gartengestaltung shows garden layout/planting; Terrassenbau shows terrace/paving; Rasenneuanlage shows turf being laid; Baumfällung shows safe tree work; Heckenschnitt shows hedge trimming; Gartenpflege shows maintenance.

**Step 6 — No repetitive images:**
Every image must be unique in scene, angle, subject, service focus, background, and composition. Before placing an image, compare it against all other images on the site. Reject if it shows the same scene, angle, or composition as any other image.

**Step 7 — Human image quality rule:**
Reject any AI-generated human image if the face, hands, fingers, body, posture, skin, eyes, or tools look distorted, blurry, fake, or unnatural. Prefer wide or medium shots where the work scene matters more than the face. If in doubt, replace with a clean non-human result/project image. A clean project image with no people is always better than a bad AI-generated human image.

**Step 8 — Avoid fake credibility:**
Do not invent statistics, project counts, awards, or years of experience unless found in crawled website data or the email. Use soft phrases instead: "Langjährige Erfahrung", "Viele erfolgreich abgeschlossene Projekte", "Persönliche Beratung", "Zuverlässige Ausführung".

**Step 9 — Prompt format for each generated image:**
```
Realistic professional website photography for [industry]. Scene: [specific scene matching this section and service]. Location/context: [region/environment]. Composition: spacious, clean, well-balanced, main subject clearly visible, no crowding, no distortion, natural perspective. Lighting: natural daylight, premium commercial look. Style: modern business website, realistic, high quality, sharp but natural. Avoid: text, watermark, logo, distorted objects, unrealistic AI look, overcrowded composition, squeezed framing, duplicate composition.
```

**Step 10 — Final quality check before completing any website:**
- No image is squeezed, stretched, or repetitive
- No image leaves blank space inside its block
- Every image fills the full container edge to edge
- Every project card has consistent image height
- Hero image is large, premium, and not lazy-loaded
- Service images match their exact service titles
- Gallery images look like separate real projects
- Human images look realistic, or are replaced with project images
- All images match the business data
- The full website looks modern, spacious, clean, and professional
