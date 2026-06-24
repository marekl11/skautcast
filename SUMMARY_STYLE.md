# SkautCast — summary writing style

Every episode summary (`data/summaries/<hash>.md`) is written for the **ear**, not
the eye, using the classic "tell them what you'll tell them → tell them → tell them
what you told them" structure.

## Structure (3 parts)

1. **Úvod / přehled (overview)** — 1–3 sentences naming the topic and signposting what
   the episode will cover. ("V tomto díle se podíváme na… Řekneme si…")
2. **Hlavní část (body)** — the content, broken into clearly signposted points
   ("Začněme…", "Druhým tématem je…", "Dále…", "A nakonec…").
3. **Shrnutí / závěr (recap)** — 1–3 sentences recapping the key takeaways
   ("Shrňme si to: …"), optionally a closing call to action.

## Guidelines for easy listening

- **Add a little "how" and "why," not just "what."** When the source explains a
  mechanism or reasoning, include a sentence on it — the listener should come away
  understanding *how* something will work or *why* a decision was made, not just the
  headline. Prefer depth on the meaty points over listing every minor item.
- **Name sources and say where to find them.** When the article points to a document,
  material, tool, form, or event, name it specifically and add where to find it when the
  source says so (e.g. "ve Spisovně na Křižovatce", "ve skautISu", "na zpravodajství") —
  don't leave it as a vague "a material". (Each episode also carries a link to the
  original article in its show notes, and the article's image as episode artwork.)
- **Short sentences, one idea each.** Avoid long nested clauses; split them.
- **Signpost constantly** so the listener can follow without re-reading: *za prvé /
  za druhé*, *nejdřív / potom*, *důležité je*, *jinými slovy*, *na závěr*.
- **Expand abbreviations and jargon** on first use (Náčelnictvo, Výkonná rada,
  „systém skautIS", revizní komise). Never read bare acronyms.
- **Numbers and dates in natural spoken Czech** ("patnáct procent", "do roku 2035").
- **Active voice, warm/conversational tone**, keep the source's address (ty/vy).
- **Repeat the key noun** instead of an ambiguous pronoun when it aids clarity.
- **One topic per episode**, ~1.5–3 minutes spoken (roughly 1000–1800 characters).
- First line is always `# <Episode title>` (becomes the AntennaPod episode name).

The Gemini voice (Charon) is additionally prompted (config `GEMINI_STYLE`) for a calm
but expressive, non-monotone delivery with emphasis on key words and short pauses.
