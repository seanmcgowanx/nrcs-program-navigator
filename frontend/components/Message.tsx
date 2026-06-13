"use client";

import { motion } from "framer-motion";
import { Plant, ArrowClockwise, Warning } from "@phosphor-icons/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "@/lib/types";

const spring = { type: "spring", stiffness: 120, damping: 18 } as const;

export default function Message({
  message,
  onRetry,
}: {
  message: ChatMessage;
  onRetry?: () => void;
}) {
  if (message.role === "user") {
    return (
      <motion.div
        layout
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={spring}
        className="flex justify-end"
      >
        <div className="max-w-[78%] rounded-2xl rounded-br-md bg-accent px-4 py-3 text-[0.95rem] leading-relaxed text-white shadow-[0_6px_16px_-8px_rgba(47,107,79,0.5)]">
          {message.content}
        </div>
      </motion.div>
    );
  }

  if (message.role === "error") {
    return (
      <motion.div
        layout
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={spring}
        className="flex items-start gap-3"
      >
        <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-danger-soft text-danger">
          <Warning size={16} weight="bold" />
        </div>
        <div className="max-w-[78%] rounded-2xl rounded-tl-md border border-danger/20 bg-danger-soft px-4 py-3">
          <p className="text-[0.9rem] leading-relaxed text-danger">
            {message.content}
          </p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-2 inline-flex items-center gap-1.5 text-[0.82rem] font-medium text-danger transition-transform active:scale-[0.97]"
            >
              <ArrowClockwise size={14} weight="bold" />
              Try again
            </button>
          )}
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={spring}
      className="flex items-start gap-3"
    >
      <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
        <Plant size={16} weight="fill" />
      </div>
      <div className="min-w-0 max-w-[82%] rounded-2xl rounded-tl-md border border-line bg-surface px-4 py-3 shadow-[0_8px_24px_-18px_rgba(31,29,26,0.35)]">
        <div className="prose-reply">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>
      </div>
    </motion.div>
  );
}
