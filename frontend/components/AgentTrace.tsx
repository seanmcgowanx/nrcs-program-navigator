"use client";

import { motion, AnimatePresence } from "framer-motion";
import { CircleNotch, Check } from "@phosphor-icons/react";
import type { TraceStep } from "@/lib/types";

/**
 * The list of tools the agent ran in a turn. Each step shows a present tense
 * label and, once the tool returns, a one line summary of what came back. A
 * step without a summary is still running, so it shows a spinner.
 *
 * Used live while the turn streams (the steps animate in) and, collapsed, under
 * a finished answer via the disclosure in Message.tsx.
 */
export default function AgentTrace({ steps }: { steps: TraceStep[] }) {
  return (
    <ul className="flex flex-col gap-2">
      <AnimatePresence initial={false}>
        {steps.map((step) => {
          const running = step.summary === undefined;
          return (
            <motion.li
              key={step.id}
              layout
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-2.5 text-[0.85rem]"
            >
              <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center text-accent">
                {running ? (
                  <CircleNotch size={14} weight="bold" className="animate-spin" />
                ) : (
                  <Check size={14} weight="bold" />
                )}
              </span>
              <span className="min-w-0">
                <span
                  className={
                    running ? "font-medium text-ink" : "font-medium text-muted"
                  }
                >
                  {step.label}
                </span>
                {step.summary && (
                  <span className="text-faint"> &middot; {step.summary}</span>
                )}
              </span>
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ul>
  );
}
