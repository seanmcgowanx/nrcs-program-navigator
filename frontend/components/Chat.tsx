"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { Compass, NotePencil } from "@phosphor-icons/react";
import Rail from "./Rail";
import Message from "./Message";
import Composer from "./Composer";
import EmptyState from "./EmptyState";
import TypingIndicator from "./TypingIndicator";
import { streamChat } from "@/lib/api";
import type { ChatMessage, TraceStep } from "@/lib/types";

const SESSION_KEY = "nrcs-navigator-session";

function newSessionId(): string {
  return crypto.randomUUID();
}

export default function Chat() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  // Consecutive failed turns on the current session. After a couple, retrying
  // the same session is unlikely to help (it may be wedged), so we steer the
  // user toward starting fresh.
  const [consecutiveErrors, setConsecutiveErrors] = useState(0);
  // The tools running in the in-flight turn, shown live. Clears when the turn
  // lands in `messages`. The answer itself is not shown until it is complete.
  const [activeSteps, setActiveSteps] = useState<TraceStep[]>([]);

  const lastUserText = useRef<string>("");
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  // Mirror the streamed state in refs so the commit at the end reads the final
  // values without waiting for a re-render.
  const stepsRef = useRef<TraceStep[]>([]);
  const replyRef = useRef("");

  // Restore (or mint) the session id from localStorage on the client only, so a
  // page refresh continues the same conversation thread on the backend.
  useEffect(() => {
    let id = localStorage.getItem(SESSION_KEY);
    if (!id) {
      id = newSessionId();
      localStorage.setItem(SESSION_KEY, id);
    }
    setSessionId(id);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // Takes an explicit session id rather than reading it from state, so a fresh
  // start can mint a new id and resend in the same tick without waiting for the
  // async setSessionId to land.
  const run = useCallback(async (text: string, sid: string) => {
    lastUserText.current = text;
    setSending(true);
    setActiveSteps([]);
    stepsRef.current = [];
    replyRef.current = "";
    abortRef.current = new AbortController();
    try {
      await streamChat(
        sid,
        text,
        {
          onStepStart: (id, label) => {
            stepsRef.current = [...stepsRef.current, { id, label }];
            setActiveSteps(stepsRef.current);
          },
          onStepEnd: (id, summary) => {
            stepsRef.current = stepsRef.current.map((s) =>
              s.id === id ? { ...s, summary } : s,
            );
            setActiveSteps(stepsRef.current);
          },
          onFinal: (reply) => {
            replyRef.current = reply;
          },
        },
        abortRef.current.signal,
      );
      // Capture before the finally clears the refs: setMessages' updater runs on
      // the next render, after finally has already reset replyRef/stepsRef.
      const finalReply = replyRef.current;
      const finalSteps = stepsRef.current;
      setMessages((m) => [
        ...m,
        {
          id: newSessionId(),
          role: "assistant",
          content: finalReply,
          steps: finalSteps.length ? finalSteps : undefined,
        },
      ]);
      setConsecutiveErrors(0);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setConsecutiveErrors((n) => n + 1);
      setMessages((m) => [
        ...m,
        {
          id: newSessionId(),
          role: "error",
          content: (err as Error).message,
        },
      ]);
    } finally {
      setActiveSteps([]);
      stepsRef.current = [];
      replyRef.current = "";
      setSending(false);
    }
  }, []);

  const send = useCallback(
    (text: string) => {
      if (!sessionId) return;
      setMessages((m) => [
        ...m,
        { id: newSessionId(), role: "user", content: text },
      ]);
      void run(text, sessionId);
    },
    [run, sessionId],
  );

  const retry = useCallback(() => {
    if (!sessionId) return;
    setMessages((m) => m.filter((msg) => msg.role !== "error"));
    void run(lastUserText.current, sessionId);
  }, [run, sessionId]);

  // Escape hatch from a wedged conversation: mint a fresh session, drop the
  // broken thread, and resend the failed message so the user still gets an
  // answer without retyping.
  const startFreshAndResend = useCallback(
    (text: string) => {
      abortRef.current?.abort();
      const id = newSessionId();
      localStorage.setItem(SESSION_KEY, id);
      setSessionId(id);
      setConsecutiveErrors(0);
      setMessages([{ id: newSessionId(), role: "user", content: text }]);
      void run(text, id);
    },
    [run],
  );

  const newChat = useCallback(() => {
    abortRef.current?.abort();
    const id = newSessionId();
    localStorage.setItem(SESSION_KEY, id);
    setSessionId(id);
    setMessages([]);
    setConsecutiveErrors(0);
    setSending(false);
  }, []);

  const isEmpty = messages.length === 0;
  // The retry button belongs only to a trailing error (no later messages).
  const errorIsTrailing =
    messages.length > 0 && messages[messages.length - 1].role === "error";

  return (
    <div className="flex h-[100dvh] overflow-hidden">
      <Rail onNewChat={newChat} />

      <main className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar (rail is hidden under lg). */}
        <header className="flex items-center justify-between border-b border-line px-4 py-3 lg:hidden">
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-lg bg-accent text-white">
              <Compass size={16} weight="fill" />
            </div>
            <span className="text-[0.95rem] font-semibold tracking-tight">
              Navigator
            </span>
          </div>
          <button
            onClick={newChat}
            aria-label="New conversation"
            className="flex size-9 items-center justify-center rounded-lg border border-line text-accent transition-transform active:scale-[0.94]"
          >
            <NotePencil size={17} weight="bold" />
          </button>
        </header>

        <div className="thread-scroll min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 md:px-6">
            {isEmpty ? (
              <EmptyState onPick={send} />
            ) : (
              <div className="flex flex-col gap-5 py-8">
                <AnimatePresence initial={false}>
                  {messages.map((msg) => {
                    const isTrailingError =
                      msg.role === "error" && errorIsTrailing;
                    return (
                      <Message
                        key={msg.id}
                        message={msg}
                        onRetry={isTrailingError ? retry : undefined}
                        onFreshStart={
                          isTrailingError
                            ? () => startFreshAndResend(lastUserText.current)
                            : undefined
                        }
                        stuck={isTrailingError && consecutiveErrors >= 2}
                      />
                    );
                  })}
                </AnimatePresence>
                <AnimatePresence>
                  {sending &&
                    (activeSteps.length > 0 ? (
                      <Message
                        key="live-turn"
                        message={{
                          id: "live-turn",
                          role: "assistant",
                          content: "",
                          steps: activeSteps,
                        }}
                        streaming
                      />
                    ) : (
                      <TypingIndicator key="typing" />
                    ))}
                </AnimatePresence>
                <div ref={bottomRef} />
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-line bg-canvas/80 px-4 py-4 backdrop-blur md:px-6">
          <div className="mx-auto w-full max-w-3xl">
            <Composer onSend={send} disabled={sending || !sessionId} />
            <p className="mt-2 px-1 text-center text-[0.72rem] text-faint">
              Verify program details and deadlines against the official NRCS
              source before advising a client.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
