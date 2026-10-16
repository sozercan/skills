# Writing for speech

Narration is heard once, at a fixed pace. Write for the ear.

## Structure

- One idea per sentence, one scene or paragraph per clip. A listener cannot re-read.
- Say what is about to appear before it appears, then what it showed. "Now the deploy runs. It finished in nine seconds and all three checks passed."
- Introduce a term the first time it is spoken. Do not rely on a glossary on screen.
- Open with the problem the viewer has and close with a concrete next step.
- Keep each clip comfortably under the generation cap: about 100 words is safe at the default; the hard ceiling is `max_frames / 12.5` seconds.

## Numbers and names

- Write numbers as they are said: "twenty-three", "about twenty-three cents", "version one point four". Long decimals, currency with many digits, hashes, and IDs are unreliable.
- Show exact values on screen and speak an honest approximation. Compute percentages from the original unrounded values, not from the rounded spoken ones.
- Say whether a longer duration is slower or faster; do not leave the direction to the viewer.
- Spell out acronyms the first time or write how they are said ("kube-control", "gee-visor") only if the default pronunciation is wrong, and re-check the clip afterwards.
- Avoid URLs, paths, and code in speech. Say "the link on screen" and show it.

## Pacing

- Commas and full stops create pauses; ellipses and dashes are inconsistent.
- Short sentences land better than nested clauses.
- Do not try to speed a clip up in post. Shorten the text instead.

## After generating

Compare the transcript with the script for the numbers and the last sentence of every clip. Those are where problems hide.
