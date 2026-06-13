"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { Compass, NotePencil } from "@phosphor-icons/react";
import Rail from "./Rail";
import Message from "./Message";
import Composer from "./Composer";
import EmptyState from "./EmptyState";
import TypingIndicator from "./TypingIndicator";
import { sendChat } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

const SESSION_KEY = "nrcs-navigator-session";

function newSessionId(): string {
  return crypto.randomUUID();
}

export default function Chat() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);

  const lastUserText = useRef<string>("");
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

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

  const run = useCallback(
    async (text: string) => {
      if (!sessionId) return;
      lastUserText.current = text;
      setSending(true);
      abortRef.current = new AbortController();
      try {
        const reply = await sendChat(sessionId, text, abortRef.current.signal);
        setMessages((m) => [
          ...m,
          { id: newSessionId(), role: "assistant", content: reply },
        ]);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setMessages((m) => [
          ...m,
          {
            id: newSessionId(),
            role: "error",
            content: (err as Error).message,
          },
        ]);
      } finally {
        setSending(false);
      }
    },
    [sessionId],
  );

  const send = useCallback(
    (text: string) => {
      setMessages((m) => [
        ...m,
        { id: newSessionId(), role: "user", content: text },
      ]);
      void run(text);
    },
    [run],
  );

  const retry = useCallback(() => {
    setMessages((m) => m.filter((msg) => msg.role !== "error"));
    void run(lastUserText.current);
  }, [run]);

  const newChat = useCallback(() => {
    abortRef.current?.abort();
    const id = newSessionId();
    localStorage.setItem(SESSION_KEY, id);
    setSessionId(id);
    setMessages([]);
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
                  {messages.map((msg) => (
                    <Message
                      key={msg.id}
                      message={msg}
                      onRetry={
                        msg.role === "error" && errorIsTrailing
                          ? retry
                          : undefined
                      }
                    />
                  ))}
                </AnimatePresence>
                <AnimatePresence>{sending && <TypingIndicator />}</AnimatePresence>
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
