"use client";

import { Compass, NotePencil } from "@phosphor-icons/react";
import { PROGRAMS } from "@/lib/programs";

// Left reference rail: wordmark, a new conversation action, and the program
// legend so an advisor can see the catalog the navigator covers. Presentational
// only; state lives in Chat.
export default function Rail({ onNewChat }: { onNewChat: () => void }) {
  return (
    <aside className="hidden w-[300px] shrink-0 flex-col border-r border-line bg-surface/50 lg:flex">
      <div className="flex items-center gap-2.5 px-6 pb-6 pt-7">
        <div className="flex size-8 items-center justify-center rounded-lg bg-accent text-white">
          <Compass size={18} weight="fill" />
        </div>
        <div className="leading-tight">
          <p className="text-[0.95rem] font-semibold tracking-tight text-ink">
            Navigator
          </p>
          <p className="font-mono text-[0.66rem] uppercase tracking-[0.14em] text-faint">
            NRCS Programs
          </p>
        </div>
      </div>

      <div className="px-4">
        <button
          onClick={onNewChat}
          className="flex w-full items-center gap-2.5 rounded-xl border border-line px-3.5 py-2.5 text-left text-[0.88rem] font-medium text-ink transition-all hover:border-accent/40 hover:bg-accent-soft/50 active:scale-[0.99]"
        >
          <NotePencil size={17} weight="bold" className="text-accent" />
          New conversation
        </button>
      </div>

      <div className="mt-8 px-6">
        <p className="font-mono text-[0.66rem] uppercase tracking-[0.16em] text-faint">
          Programs covered
        </p>
        <ul className="mt-4 space-y-5">
          {PROGRAMS.map((p) => (
            <li key={p.code}>
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-[0.78rem] font-semibold text-accent-ink">
                  {p.code}
                </span>
                <span className="text-[0.8rem] text-muted">{p.name}</span>
              </div>
              <p className="mt-1 text-[0.78rem] leading-relaxed text-faint">
                {p.blurb}
              </p>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-auto px-6 pb-6 pt-8">
        <p className="text-[0.72rem] leading-relaxed text-faint">
          CRP is administered by the FSA and is out of scope. The navigator
          redirects those questions to your local FSA office.
        </p>
      </div>
    </aside>
  );
}
