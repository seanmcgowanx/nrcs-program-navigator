"use client";

import { motion } from "framer-motion";
import {
  Plant,
  ArrowClockwise,
  Warning,
  NotePencil,
  CaretRight,
  CircleNotch,
} from "@phosphor-icons/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "@/lib/types";
import AgentTrace from "./AgentTrace";

const spring = { type: "spring", stiffness: 120, damping: 18 } as const;

export default function Message({
  message,
  onRetry,
  onFreshStart,
  stuck,
  streaming,
}: {
  message: ChatMessage;
  onRetry?: () => void;
  onFreshStart?: () => void;
  stuck?: boolean;
  // True while this assistant turn is still streaming: the trace shows expanded
  // and a caret marks the answer as in progress.
  streaming?: boolean;
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
          {stuck && onFreshStart && (
            <p className="mt-1.5 text-[0.82rem] leading-relaxed text-danger/80">
              This conversation may be stuck. Starting fresh usually fixes it.
            </p>
          )}
          {(onRetry || onFreshStart) && (
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5">
              {/* When stuck, retrying the same session keeps failing, so the
                  fresh start is the primary action and comes first. */}
              {stuck && onFreshStart && (
                <button
                  onClick={onFreshStart}
                  className="inline-flex items-center gap-1.5 text-[0.82rem] font-semibold text-danger transition-transform active:scale-[0.97]"
                >
                  <NotePencil size={14} weight="bold" />
                  Start new conversation
                </button>
              )}
              {onRetry && (
                <button
                  onClick={onRetry}
                  className="inline-flex items-center gap-1.5 text-[0.82rem] font-medium text-danger transition-transform active:scale-[0.97]"
                >
                  <ArrowClockwise size={14} weight="bold" />
                  Try again
                </button>
              )}
              {!stuck && onFreshStart && (
                <button
                  onClick={onFreshStart}
                  className="inline-flex items-center gap-1.5 text-[0.82rem] font-medium text-danger transition-transform active:scale-[0.97]"
                >
                  <NotePencil size={14} weight="bold" />
                  Start new conversation
                </button>
              )}
            </div>
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
        {message.steps && message.steps.length > 0 && (
          streaming ? (
            // Live turn: trace stays expanded so the work is visible as it runs.
            // No answer text yet -- it arrives as a complete message when ready.
            <div>
              <AgentTrace steps={message.steps} />
              {/* Once every tool has returned, the model is composing the answer,
                  which can take a while. Keep a live indicator so the wait never
                  looks like a stall. */}
              {message.steps.every((s) => s.summary !== undefined) && (
                <div className="mt-2 flex items-center gap-2 text-[0.85rem] text-muted">
                  <CircleNotch
                    size={14}
                    weight="bold"
                    className="animate-spin text-accent"
                  />
                  Writing answer&hellip;
                </div>
              )}
            </div>
          ) : (
            // Finished turn: collapse the work under a disclosure, kept for history.
            <details className="trace-disclosure group mb-3">
              <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[0.8rem] font-medium text-muted transition-colors hover:text-ink">
                <CaretRight
                  size={12}
                  weight="bold"
                  className="transition-transform group-open:rotate-90"
                />
                Used {message.steps.length} tool{message.steps.length === 1 ? "" : "s"}
              </summary>
              <div className="mt-2.5 border-l border-line pl-3">
                <AgentTrace steps={message.steps} />
              </div>
            </details>
          )
        )}
        {message.content && (
          <div className="prose-reply">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </motion.div>
  );
}
