/**
 * Embeds PPTist (running separately, e.g. http://localhost:5173) in an iframe and syncs
 * slide JSON both ways. Requires eduguardBridge.ts installed in PPTist.
 *
 *   <PptistEditor src="http://localhost:5173" slides={slides} title="Bài 1"
 *                 onChange={setSlides} />
 */
import React, { useEffect, useImperativeHandle, useRef, forwardRef } from 'react';

export interface PptistEditorHandle {
  goto: (index: number) => void;
  reload: () => void;
}

interface Props {
  src: string;
  slides: unknown[];
  title?: string;
  onChange?: (slides: any[]) => void;
  className?: string;
}

export const PptistEditor = forwardRef<PptistEditorHandle, Props>(
  ({ src, slides, title, onChange, className }, ref) => {
    const frame = useRef<HTMLIFrameElement>(null);
    const ready = useRef(false);
    const lastSent = useRef<string>('');
    const origin = new URL(src).origin;

    const send = (msg: unknown) => frame.current?.contentWindow?.postMessage(msg, origin);
    const load = () => {
      const payload = JSON.stringify(slides);
      lastSent.current = payload;
      send({ type: 'eduguard:load', slides, title });
    };

    useImperativeHandle(ref, () => ({
      goto: (index) => send({ type: 'eduguard:goto', index }),
      reload: load,
    }));

    useEffect(() => {
      const onMsg = (e: MessageEvent) => {
        if (e.origin !== origin) return;
        if (e.data?.type === 'eduguard:ready') { ready.current = true; load(); }
        if (e.data?.type === 'eduguard:change') {
          lastSent.current = JSON.stringify(e.data.slides);
          onChange?.(e.data.slides);
        }
      };
      window.addEventListener('message', onMsg);
      return () => window.removeEventListener('message', onMsg);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [origin, onChange]);

    // push external changes (e.g. after /slides/voice added audio) without echo loops
    useEffect(() => {
      if (ready.current && JSON.stringify(slides) !== lastSent.current) load();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [slides, title]);

    return (
      <iframe
        ref={frame}
        src={src}
        title="Slide editor"
        className={className ?? 'w-full h-full border-0 rounded-lg bg-white'}
        allow="autoplay; fullscreen; clipboard-read; clipboard-write"
      />
    );
  }
);
PptistEditor.displayName = 'PptistEditor';
