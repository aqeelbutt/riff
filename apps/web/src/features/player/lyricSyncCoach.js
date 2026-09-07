/** The lyric-sync walkthrough. One definition, shown on both the song page and the upload page, so the two
 *  can't teach the feature differently. Anchors are `data-coach` ids that must exist on whichever page runs it. */

export const LYRIC_SYNC_COACH = "lyric-sync";

/**
 * `unit` is what this page calls a piece of audio — "take" on a song, "version" on an upload.
 * `hasApprox` points the last step at the real approximate note when one is on screen; without it the step
 * still runs (it's the thing people most often misread) but anchors to the lyrics panel instead.
 */
export function lyricSyncSteps({ unit = "take", hasApprox = false } = {}) {
  const units = `${unit}s`;
  return [
    {
      anchor: "sync-button", prefer: "below", eyebrow: "LYRIC SYNC",
      title: `Time the words to this ${unit}`,
      body: [`Riff listens to the exact render you're playing and lines your lyrics up against what it heard. It runs on your Mac and takes about a minute.`],
    },
    {
      anchor: "versions", prefer: "right", eyebrow: "LYRIC SYNC",
      title: `Every ${unit} gets its own timing`,
      body: [
        `Two ${units} of the same lyric sing it differently, and a reimagined one differs again — so timings belong to the audio, not to the song.`,
        `Sync the ${units} you actually care about. The rest stay untouched.`,
      ],
    },
    {
      anchor: "lyrics", prefer: "left", eyebrow: "LYRIC SYNC",
      title: "The words follow the music",
      body: ["The line that's sounding is lit and scrolls itself into view. Click any line to send the player straight to it."],
    },
    {
      anchor: hasApprox ? "lyric-approx" : "lyrics", prefer: "left", eyebrow: "LYRIC SYNC",
      title: "When the timing is a good guess",
      body: [
        "You write Urdu, Hindi, Punjabi and Bengali lyrics in Roman script because it sings better — but the transcription comes back in the native script, so the words can't be matched line to line.",
        "When that happens Riff spreads the lines evenly across what it heard and says so above them. The words are right; the positions are approximate.",
      ],
    },
  ];
}
