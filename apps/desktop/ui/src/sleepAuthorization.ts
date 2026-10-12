/** Match explicit dismissal evidence against a confirmed user utterance, not model text. */
export type SleepTurnInput = {
  turn: number;
  binding: string;
  source: 'voice' | 'typed';
  text: string;
};

export function normalizeSleepWords(value: string): string {
  return value.normalize('NFKC').toLocaleLowerCase().replace(/[’'‘ʼ]/gu, '').replace(/[^\p{L}\p{N}]+/gu, ' ').trim().replace(/\s+/g, ' ');
}

/** A general speech-content check, independent of the user's requested action. */
export function hasSubstantiveUserWords(value: string): boolean {
  const words = normalizeSleepWords(value).split(' ').filter(Boolean);
  return words.length > 0 && words.join('').length >= 5 && words.some(w => w.length >= 3);
}

/**
 * Check the model's supporting quote against the words actually transcribed.
 * The model can include filler or paraphrase a *few* words, but an unrelated
 * assertion, wake word, or single shared word is not corroboration.
 * Intent remains the model's responsibility; this is a same-input check.
 */
export function isVerifiedSleepEvidence(
  evidence: string, input: SleepTurnInput | null, currentTurn: number,
  expectedBinding: string, wakePhrase: string,
): boolean {
  if (!input || currentTurn <= 0 || input.turn !== currentTurn ||
      !expectedBinding || input.binding !== expectedBinding ||
      !['voice', 'typed'].includes(input.source)) return false;
  const quoted = normalizeSleepWords(evidence);
  const spoken = normalizeSleepWords(input.text);
  const wake = new Set(normalizeSleepWords(wakePhrase).split(' ').filter(Boolean));
  if (!quoted || !hasSubstantiveUserWords(spoken) || quoted.length > 160) return false;
  const a = quoted.split(' ').filter(w => w && !wake.has(w));
  const b = spoken.split(' ').filter(w => w && !wake.has(w));
  if (!a.length || !b.length) return false;
  // Disagreeing polarity is too dangerous to infer away: a negated command
  // must never be corroborated by an affirmative quote or vice versa.
  const negatives = new Set(['not', 'no', 'never', 'dont', 'cannot', 'cant']);
  const negation = (ws: string[]) => ws.some(w => negatives.has(w));
  if (negation(a) !== negation(b)) return false;
  const exactPhrase = (hay: string[], needle: string[]) =>
    hay.join(' ').includes(needle.join(' ')) &&
    (` ${hay.join(' ')} `).includes(` ${needle.join(' ')} `);
  if (exactPhrase(b, a)) return true;
  // Single-word quotations must match exactly (no fuzzy one-word approval).
  if (a.length === 1 || b.length === 1) return false;
  // Find a contiguous two-word quote shared by the transcript. Permit extra
  // wording in the model's quote, but require at least half of its non-wake
  // tokens and the majority of the actual user's non-wake words to agree.
  let common = 0;
  for (const word of a) if (b.includes(word)) common += 1;
  if (common < 2 || common / a.length < 0.5 || common / b.length < 0.6) return false;
  for (let i=0;i<a.length-1;i++) {
    if (a[i] === a[i+1]) continue;
    for (let j=0;j<b.length-1;j++) {
      if (a[i] === b[j] && a[i+1] === b[j+1]) return true;
    }
  }
  return false;
}
