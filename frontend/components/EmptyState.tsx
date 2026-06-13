"use client";

import { motion } from "framer-motion";
import { ArrowUpRight } from "@phosphor-icons/react";
import { EXAMPLE_PROMPTS } from "@/lib/programs";

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07, delayChildren: 0.05 } },
};
const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 110, damping: 18 } },
};

export default function EmptyState({
  onPick,
}: {
  onPick: (text: string) => void;
}) {
  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="mx-auto flex h-full max-w-2xl flex-col justify-center py-12"
    >
      <motion.p
        variants={item}
        className="font-mono text-xs uppercase tracking-[0.18em] text-accent"
      >
        Where to start
      </motion.p>
      <motion.h1
        variants={item}
        className="mt-3 text-3xl font-semibold tracking-tight text-ink md:text-4xl"
      >
        Describe a client&apos;s operation.
      </motion.h1>
      <motion.p
        variants={item}
        className="mt-3 max-w-[58ch] text-[0.98rem] leading-relaxed text-muted"
      >
        Give the operation type, acreage, county, and what they want to improve.
        The navigator returns programs they may qualify for, estimated payment
        ranges, applicable practice codes, and current deadlines.
      </motion.p>

      <div className="mt-8 grid gap-3 sm:grid-cols-2">
        {EXAMPLE_PROMPTS.map((prompt) => (
          <motion.button
            key={prompt}
            variants={item}
            onClick={() => onPick(prompt)}
            className="group flex items-start gap-3 rounded-xl border border-line bg-surface/70 p-4 text-left transition-all hover:border-accent/40 hover:bg-surface active:scale-[0.99]"
          >
            <span className="flex-1 text-[0.88rem] leading-relaxed text-muted transition-colors group-hover:text-ink">
              {prompt}
            </span>
            <ArrowUpRight
              size={16}
              weight="bold"
              className="mt-0.5 shrink-0 text-faint transition-colors group-hover:text-accent"
            />
          </motion.button>
        ))}
      </div>
    </motion.div>
  );
}
