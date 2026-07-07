"""Lexical signals used by the scoring brain. Plain data, no logic."""
from __future__ import annotations

# Openers that tend to start a strong, self-contained hook.
HOOK_WORDS = frozenset({
    "how", "why", "what", "when", "the", "this", "here", "you", "your", "never",
    "always", "stop", "don't", "if", "imagine", "listen", "watch", "look",
    "secret", "truth", "nobody", "everyone", "most", "biggest", "best", "worst",
    "first", "last", "before", "after", "let", "let's", "remember", "warning",
})

# Words carrying emotional / attention intensity.
EMOTION_WORDS = frozenset({
    "amazing", "incredible", "insane", "crazy", "shocking", "unbelievable",
    "wild", "love", "hate", "scared", "afraid", "angry", "happy", "sad",
    "hilarious", "funny", "wow", "omg", "epic", "brutal", "perfect", "worst",
    "best", "terrible", "awful", "beautiful", "dangerous", "surprising",
    "mind-blowing", "wtf", "damn", "actually", "literally", "honestly",
    "seriously", "insanely", "absolutely", "completely", "totally",
})

# Curiosity / value markers.
VALUE_WORDS = frozenset({
    "because", "reason", "means", "result", "learned", "lesson", "trick",
    "tip", "hack", "mistake", "problem", "solution", "answer", "proof",
    "example", "story", "moment", "point", "key", "important", "matters",
})

STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "is",
    "are", "was", "were", "be", "been", "it", "its", "this", "that", "these",
    "those", "i", "you", "he", "she", "we", "they", "them", "his", "her",
    "our", "your", "my", "me", "us", "him", "at", "by", "with", "as", "so",
    "if", "then", "than", "from", "up", "out", "about", "into", "over", "just",
    "do", "does", "did", "have", "has", "had", "will", "would", "can", "could",
    "should", "not", "no", "yes", "get", "got", "like", "one", "all", "some",
    "what", "when", "why", "how", "who", "there", "here", "very", "really",
    "gonna", "wanna", "yeah", "okay", "ok", "um", "uh",
})
