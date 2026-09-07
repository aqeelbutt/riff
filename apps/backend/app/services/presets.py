"""Style presets — DATA, not code. One file for both surfaces (Create styles + Remix targets), served at GET /presets.

Each preset is a caption template the engine understands (verified in Phase 0), a default tempo, an optional default
`duration_s`, and for remix targets a default closeness (cover strength). Adding a style = adding a dict here.
Never put a real artist's name in a caption.

Two things the captions do deliberately:

* They name the MIX, not just the instruments. Measured against a commercial deep-house reference, our renders carried
  13.7% of their energy above 8 kHz against the reference's 22.1%, and rolled off at 7.9 kHz against 11.1 kHz — dull
  where the record was airy. Asking for "crisp", "airy", "bright open top end" is the cheapest lever we have on that.
* They set `duration_s` where the genre needs room. Deep house and Balearic are built on long intros, breakdowns and a
  slow rise; at the 150s default they render as a fragment of an arrangement rather than an arrangement.
"""
from __future__ import annotations

CREATE_PRESETS: list[dict] = [
    {"key": "pop", "label": "Pop", "bpm": 118,
     "caption": "upbeat modern pop anthem, driving synth bass, bright electric guitars, punchy drums, catchy singalong chorus, polished radio production"},
    {"key": "hiphop", "label": "Hip-Hop", "bpm": 140,
     "caption": "modern hip-hop, trap-influenced, heavy 808 bass, crisp hi-hats, dark piano motif, confident rap vocal, half-time feel"},
    {"key": "boombap", "label": "Boom-Bap", "bpm": 92, "new": True, "duration_s": 180,
     "caption": "90s boom-bap hip-hop, hard-knocking dusty drum break with heavy swing, punchy kick and a cracking rimshot snare "
                "with real room tone, deep round upright bass line, chopped soul and jazz samples, filtered horn stabs, vinyl "
                "crackle and turntable scratches, confident rap vocal in the pocket, crisp bright hi-hats, head-nod groove, "
                "raw and gritty but wide and open, classic SP-1200 sampler character"},
    {"key": "jazzrap", "label": "Jazz-Rap", "bpm": 88, "new": True, "duration_s": 180,
     "caption": "jazz rap, boom-bap hip-hop groove under a live jazz band, warm Rhodes piano chords, walking upright bass, brushed "
                "drums with swing, muted trumpet and breathy saxophone licks, vinyl crackle, laid-back confident rap vocal, "
                "crisp airy cymbals, deep late-night mood, warm analog room sound"},
    {"key": "raprock", "label": "Rap-Rock", "bpm": 100, "new": True,
     "caption": "rap rock mashup, nu-metal down-tuned distorted guitars, heavy drums, hip-hop rapped verses, huge anthemic sung rock chorus, turntable scratches, stadium energy"},
    {"key": "rock", "label": "Rock", "bpm": 128,
     "caption": "high-energy alternative rock, driving distorted electric guitars, pounding drums, punchy bass, powerful gritty lead vocal, anthemic chorus"},
    {"key": "folk", "label": "Folk", "bpm": 92,
     "caption": "warm acoustic folk-country, fingerpicked acoustic guitar, brushed drums, upright bass, harmonica touches, intimate lead vocal with harmonies"},
    {"key": "rnb", "label": "R&B", "bpm": 96,
     "caption": "smooth contemporary R&B, silky lead vocal with runs, lush chords, deep bass, crisp drums, late-night mood"},
    {"key": "deephouse", "label": "Deep House", "bpm": 124, "duration_s": 270,
     "caption": "deep house, punchy four-on-the-floor kick, deep rolling analog sub bass, warm sidechained pads breathing with the "
                "kick, filtered Rhodes chord stabs, crisp airy shuffled hi-hats and open hats, subtle percussion shakers, long "
                "filtered breakdown that builds back to the groove, wide lush stereo, bright open top end, late-night club "
                "atmosphere, warm analog production with air and space"},
    {"key": "balearic", "label": "Balearic", "bpm": 112, "new": True, "duration_s": 270,
     "caption": "balearic chill-out, warm sunset Ibiza mood, gentle mid-tempo groove with a soft four-on-the-floor kick and "
                "brushed percussion, nylon-string acoustic guitar arpeggios, warm analog pads, congas and bongos, dub delay "
                "throws, mellow saxophone lines, deep round bass, wide spacious reverb, crisp airy hi-hats, bright open top "
                "end, unhurried and emotional, golden-hour coastal drive"},
    {"key": "lofi", "label": "Lo-fi", "bpm": 80,
     "caption": "lo-fi hip-hop, dusty drums, tape warmth, mellow Rhodes and guitar, vinyl crackle, relaxed late-night study mood"},
    {"key": "bollywood", "label": "Bollywood", "bpm": 92, "new": True, "lang": "hi",
     "caption": "romantic Bollywood ballad, soft sitar and strings intro, tabla groove, harmonium, bansuri flute, warm lead vocal with gentle ornamentation, emotional and cinematic"},
    {"key": "punjabi", "label": "Punjabi", "bpm": 100, "new": True, "lang": "pa",
     "caption": "Punjabi pop bhangra, dhol and tumbi, energetic beat, catchy hook, powerful lead vocal, celebratory and danceable"},
    {"key": "sufi", "label": "Sufi", "bpm": 96, "new": True, "lang": "ur",
     "caption": "Pakistani sufi pop, harmonium, dholak and tabla, qawwali-style claps, powerful soulful lead vocal with melismatic runs, building to an ecstatic chorus"},
]

REMIX_PRESETS: list[dict] = [
    {"key": "deephouse", "label": "Deep House", "bpm": 124, "closeness": 0.45,
     "caption": "deep house remix, punchy four-on-the-floor kick, deep rolling analog sub bass, warm sidechained pads breathing "
                "with the kick, filtered Rhodes chord stabs, crisp airy shuffled hi-hats, long filtered breakdown building back "
                "to the groove, wide lush stereo, bright open top end, late-night club atmosphere, keep the vocals"},
    {"key": "chillhouse", "label": "Chill Deep House", "bpm": 108, "closeness": 0.5, "new": True,
     "caption": "chill downtempo deep house remix, very relaxed and emotional, soft brushed lo-fi drums, warm Rhodes and felt "
                "piano melodies, floating airy pads, subtle string swells, deep round sub bass, spacious reverb, intimate and "
                "dreamy, bright open top end, keep the vocals"},
    {"key": "desihouse", "label": "Desi Deep House", "bpm": 124, "closeness": 0.5, "new": True,
     "caption": "Bollywood deep house remix, four-on-the-floor kick, sidechained warm pads, filtered chord stabs, rolling sub bass, tabla percussion layered over the groove, late-night club atmosphere, keep the original vocals"},
    {"key": "sufihouse", "label": "Sufi House", "bpm": 122, "closeness": 0.5, "new": True,
     "caption": "sufi deep house remix, four-on-the-floor kick, deep sub bass, hypnotic harmonium drone over warm pads, dholak percussion, keep the original vocals, trance-like build"},
    {"key": "afrohouse", "label": "Afro House", "bpm": 124, "closeness": 0.45, "new": True,
     "caption": "afro house remix, amapiano-influenced log drums, warm jazzy chords, shakers and congas, layered backing vocals and call-and-response chants answering the lead, deep sub bass, uplifting and soulful"},
    {"key": "boombap", "label": "Boom-Bap Flip", "bpm": 92, "closeness": 0.4, "new": True,
     "caption": "boom-bap hip-hop flip, hard-knocking dusty drum break with heavy swing, punchy kick and a cracking rimshot snare "
                "with room tone, deep round upright bass, the original chopped and filtered like a soul sample, vinyl crackle, "
                "turntable scratches, crisp bright hi-hats, head-nod groove, wide and open"},
    {"key": "jazzrap", "label": "Jazz-Rap layout", "bpm": 88, "closeness": 0.4, "new": True,
     "caption": "jazz rap remake, boom-bap hip-hop groove with live jazz band, warm Rhodes piano chords, upright bass, brushed drums, muted trumpet and saxophone licks, vinyl crackle, laid-back rapped and sung vocal"},
    {"key": "raprock", "label": "Rap-Rock", "bpm": 100, "closeness": 0.45, "new": True,
     "caption": "rap rock mashup remake, keep the sung chorus and add rapped verses, nu-metal guitars, heavy drums, turntable scratches"},
    {"key": "balearic", "label": "Balearic", "bpm": 112, "closeness": 0.5, "new": True,
     "caption": "balearic chill-out remix, warm sunset Ibiza mood, gentle mid-tempo groove with soft four-on-the-floor kick and "
                "brushed percussion, nylon-string acoustic guitar arpeggios, warm analog pads, congas and bongos, dub delay "
                "throws, mellow saxophone lines, deep round bass, wide spacious reverb, crisp airy hi-hats, bright open top end, "
                "unhurried and emotional, perfect for a long coastal drive at golden hour, keep the vocals"},
    {"key": "balearicnight", "label": "Balearic Night Drive", "bpm": 118, "closeness": 0.45, "new": True,
     "caption": "nocturnal balearic remix, warm analog synth pads, steady hypnotic mid-tempo groove, deep rolling sub bass, "
                "nylon-string guitar figures, soft dub delays and tape echo, muted trumpet, shakers and rimshots, wide "
                "cinematic stereo, bright airy top end, calm and euphoric, built for empty motorway at night, keep the vocals"},
    {"key": "lofi", "label": "Lo-fi", "bpm": 80, "closeness": 0.5,
     "caption": "lo-fi hip-hop remix, dusty drums, tape warmth, mellow Rhodes, vinyl crackle, relaxed late-night mood, keep the vocals"},
    {"key": "synthwave", "label": "Synthwave", "bpm": 110, "closeness": 0.5,
     "caption": "synthwave remix, 80s analog synths, gated reverb drums, neon arpeggios, keep the vocals"},
    {"key": "dnb", "label": "Drum & Bass", "bpm": 174, "closeness": 0.4,
     "caption": "liquid drum and bass remix, fast breakbeats, deep sub bass, lush pads, keep the vocals"},
    {"key": "acoustic", "label": "Acoustic", "bpm": 0, "closeness": 0.6,
     "caption": "stripped-back acoustic version, acoustic guitar, piano, light strings, intimate, keep the vocals"},
    {"key": "orchestral", "label": "Orchestral", "bpm": 0, "closeness": 0.6,
     "caption": "cinematic orchestral version, strings, brass, timpani, epic build, keep the vocals"},
]

# Reimagine directions — Claude reads the song, then arranges it this way. `keep_tempo` marks directions that stay at the
# original tempo (required when the user's own vocal is placed back on top, so it lines up).
REIMAGINE_DIRECTIONS: list[dict] = [
    {"key": "ballad", "label": "Emotional ballad", "bpm": 76, "new": True,
     "caption": "emotional pop ballad, intimate felt piano and close acoustic guitar, warm string section and low cello swelling under the pre-chorus, soft brushed drums entering on the second verse, choir pads on the final chorus, tender then soaring lead vocal, cinematic dynamics, wide natural reverb"},
    {"key": "anthem", "label": "Cinematic anthem", "bpm": 122, "new": True,
     "caption": "cinematic anthem, lone harmonium drone and soft tabla opening, lush orchestral strings and flute swelling into the pre-chorus, big rolling floor toms building to a euphoric chorus with stacked harmonies, powerful passionate lead vocal, dramatic lifts, epic and hopeful"},
    {"key": "acoustic", "label": "Acoustic & strings", "bpm": 88, "new": True,
     "caption": "stripped acoustic arrangement, fingerpicked nylon guitar, upright bass, light percussion, string quartet answering the vocal, intimate close-miked lead vocal with a single harmony, warm room sound, honest and unhurried"},
    {"key": "sufipop", "label": "Sufi-pop", "bpm": 96, "new": True,
     "caption": "modern sufi-pop, harmonium and dholak groove, sarangi and bansuri answering the vocal, qawwali-style hand claps and backing chants rising into an ecstatic chorus, soulful lead vocal with melismatic runs, spiritual and building"},
    {"key": "popanthem", "label": "Modern pop", "bpm": 104, "new": True,
     "caption": "polished modern pop production, warm synth bass and bright piano chords, crisp programmed drums with real cymbals, layered synth pads, a big singalong chorus with doubled vocals, confident radio-ready lead vocal, glossy and uplifting"},
    {"key": "lofisoul", "label": "Lo-fi soul", "bpm": 82, "new": True,
     "caption": "lo-fi soul arrangement, dusty drum break with swing, warm Rhodes and muted trumpet, upright bass, vinyl crackle and tape warmth, relaxed intimate lead vocal, late-night and reflective"},
]

MOODS = ["Euphoric", "Nostalgic", "Dark", "Chill", "Anthemic", "Romantic", "Emotional", "Dreamy", "Late night"]
LANGUAGES = [("en", "English"), ("hi", "Hindi"), ("ur", "Urdu"), ("pa", "Punjabi"), ("bn", "Bengali"), ("es", "Spanish"), ("fr", "French"), ("ar", "Arabic")]


def all_presets() -> dict:
    return {"create": CREATE_PRESETS, "remix": REMIX_PRESETS, "reimagine": REIMAGINE_DIRECTIONS, "moods": MOODS, "languages": [{"code": c, "label": l} for c, l in LANGUAGES]}
