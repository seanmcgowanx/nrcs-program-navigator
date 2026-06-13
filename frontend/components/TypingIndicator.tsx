"use client";

import { motion } from "framer-motion";
import { Plant } from "@phosphor-icons/react";

// Shown while the agent works through its tool loop (the backend reply is not
// streamed, so this stands in for the wait). Three dots breathing in sequence.
export default function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="flex items-start gap-3"
    >
      <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
        <Plant size={16} weight="fill" />
      </div>
      <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-md border border-line bg-surface px-4 py-3.5">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="block size-1.5 rounded-full bg-faint"
            animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }}
            transition={{
              duration: 1.1,
              repeat: Infinity,
              ease: "easeInOut",
              delay: i * 0.18,
            }}
          />
        ))}
      </div>
    </motion.div>
  );
}
