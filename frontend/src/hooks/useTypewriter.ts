import { useState, useEffect, useRef, useCallback } from 'react';

interface UseTypewriterOptions {
  text: string;
  speed?: number; // ms per word
  enabled?: boolean;
}

/**
 * Typewriter hook: reveals text word-by-word with configurable speed.
 * Returns { displayedText, isTyping, skipToEnd }.
 * Call skipToEnd() to instantly reveal full text.
 */
export function useTypewriter({ text, speed = 15, enabled = true }: UseTypewriterOptions) {
  const [displayedText, setDisplayedText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const words = useRef<string[]>([]);
  const indexRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const skippedRef = useRef(false);

  const skipToEnd = useCallback(() => {
    skippedRef.current = true;
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setDisplayedText(text);
    setIsTyping(false);
  }, [text]);

  useEffect(() => {
    if (!enabled || !text) {
      setDisplayedText(text);
      setIsTyping(false);
      return;
    }

    // Reset
    skippedRef.current = false;
    words.current = text.split(/(\s+)/); // keep whitespace tokens
    indexRef.current = 0;
    setDisplayedText('');
    setIsTyping(true);

    timerRef.current = setInterval(() => {
      if (skippedRef.current) return;

      indexRef.current += 1;
      const chunk = words.current.slice(0, indexRef.current).join('');
      setDisplayedText(chunk);

      if (indexRef.current >= words.current.length) {
        if (timerRef.current) clearInterval(timerRef.current);
        timerRef.current = null;
        setIsTyping(false);
      }
    }, speed);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [text, speed, enabled]);

  return { displayedText, isTyping, skipToEnd };
}
