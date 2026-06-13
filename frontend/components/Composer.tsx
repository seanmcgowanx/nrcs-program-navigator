"use client";

import { useRef, useState, useEffect, type FormEvent } from "react";
import { PaperPlaneTilt } from "@phosphor-icons/react";

export default function Composer({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void;
  disabled: boolean;
}) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Grow the textarea with its content up to a ceiling, then scroll.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [value]);

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
  }

  return (
    <form
      onSubmit={submit}
      className="flex items-end gap-2 rounded-2xl border border-line-strong bg-surface p-2 shadow-[0_12px_32px_-20px_rgba(31,29,26,0.4)] transition-colors focus-within:border-accent/60"
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        rows={1}
        placeholder="Describe a client's operation, location, and goals..."
        className="max-h-[180px] flex-1 resize-none bg-transparent px-3 py-2 text-[0.95rem] leading-relaxed text-ink outline-none placeholder:text-faint"
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        aria-label="Send message"
        className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent text-white transition-all hover:bg-accent-ink active:scale-[0.94] disabled:cursor-not-allowed disabled:bg-line-strong disabled:text-faint"
      >
        <PaperPlaneTilt size={18} weight="fill" />
      </button>
    </form>
  );
}
