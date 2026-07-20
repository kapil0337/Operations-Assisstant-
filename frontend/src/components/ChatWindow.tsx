import { useEffect, useRef, useState } from "react";
import { sendMessageSync, ChatResponse } from "../api";
import { Message, MessageBubble, TypingIndicator } from "./MessageBubble";

const STORAGE_KEY = "ops_api_key";

const QUICK_QUESTIONS = [
  { label: "Double charge",     text: "I was double charged for order #1042, please help" },
  { label: "Order status",      text: "What's the status of order #2001?" },
  { label: "Refund policy",     text: "What is your refund policy?" },
  { label: "Damaged item",      text: "My item from order #4090 arrived damaged" },
  { label: "Shipping delay",    text: "Order #5500 is delayed — what can you do?" },
  { label: "Cancel order",      text: "I want to cancel order #2001" },
  { label: "Lost package",      text: "Order #2001 shows shipped but hasn't arrived in 3 weeks" },
  { label: "Payment failed",    text: "My payment for order #4090 failed but I see a charge" },
];

const STATUS_COLORS = {
  ok: "#22c55e",
  checking: "#f59e0b",
  error: "#ef4444",
};

function StatusDot({ status }: { status: "ok" | "checking" | "error" }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: 7,
        height: 7,
        borderRadius: "50%",
        background: STATUS_COLORS[status],
        boxShadow: status === "ok" ? "0 0 0 2px #dcfce7" : undefined,
        flexShrink: 0,
      }}
    />
  );
}

export function ChatWindow() {
  const [apiKey, setApiKey]         = useState<string>(() => localStorage.getItem(STORAGE_KEY) ?? "dev-key-change-me");
  const [keyDraft, setKeyDraft]     = useState(apiKey);
  const [showKeyPanel, setShowKeyPanel] = useState(false);
  const [messages, setMessages]     = useState<Message[]>([
    {
      role: "assistant",
      text: "Hi! I'm your Operations Assistant.\n\nI can help with order lookups, refund requests, shipping questions, and more. Try one of the quick questions on the left, or describe your issue.",
    },
  ]);
  const [input, setInput]           = useState("");
  const [sessionId, setSessionId]   = useState<string | null>(null);
  const [sending, setSending]       = useState(false);
  const [sysStatus, setSysStatus]   = useState<{ db: "ok"|"error"|"checking"; redis: "ok"|"error"|"checking"; llm: "ok"|"error"|"checking" }>({ db: "checking", redis: "checking", llm: "checking" });
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLInputElement>(null);

  // Scroll to bottom whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // Poll /health on mount
  useEffect(() => {
    fetch("http://localhost:8000/health")
      .then((r) => r.json())
      .then((d) => setSysStatus({
        db:    d.database === "ok" ? "ok" : "error",
        redis: d.redis === "ok"    ? "ok" : "error",
        llm:   d.llm_configured    ? "ok" : "error",
      }))
      .catch(() => setSysStatus({ db: "error", redis: "error", llm: "error" }));
  }, []);

  function saveKey() {
    setApiKey(keyDraft);
    localStorage.setItem(STORAGE_KEY, keyDraft);
    setShowKeyPanel(false);
  }

  async function handleSend(overrideText?: string) {
    const text = (overrideText ?? input).trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    setMessages((prev) => [...prev, { role: "user", text }]);

    try {
      const res: ChatResponse = await sendMessageSync(text, sessionId, apiKey);
      setSessionId(res.session_id);

      if (res.blocked) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", text: `⚠️ Request blocked: ${res.block_reason}` },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            text: res.reply,
            escalated: res.escalated,
            awaitingConfirmation: res.awaiting_confirmation,
            toolCalls: res.tool_calls,
          },
        ]);
      }
    } catch (err) {
      const msg = (err as Error).message;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: `❌ Error: ${msg}` },
      ]);
    } finally {
      setSending(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  const lastMsg = messages[messages.length - 1];
  const awaitingConfirmation = !sending && lastMsg?.role === "assistant" && lastMsg?.awaitingConfirmation;

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "'Inter', system-ui, sans-serif", background: "#f8fafc", overflow: "hidden" }}>

      {/* ── Sidebar ─────────────────────────────────────────────── */}
      <aside
        style={{
          width: 270,
          flexShrink: 0,
          background: "#0f172a",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Sidebar header */}
        <div style={{ padding: "20px 18px 14px", borderBottom: "1px solid #1e293b" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: "linear-gradient(135deg, #4f46e5, #818cf8)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 18,
                flexShrink: 0,
              }}
            >
              🤖
            </div>
            <div>
              <div style={{ color: "white", fontWeight: 700, fontSize: 14, lineHeight: 1.2 }}>Ops Assistant</div>
              <div style={{ color: "#64748b", fontSize: 11, marginTop: 1 }}>Powered by NVIDIA NIM</div>
            </div>
          </div>
        </div>

        {/* System status */}
        <div style={{ padding: "14px 18px", borderBottom: "1px solid #1e293b" }}>
          <div style={{ color: "#64748b", fontSize: 11, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: 10 }}>
            System Status
          </div>
          {[
            { label: "Database",    key: "db" as const },
            { label: "Redis Queue", key: "redis" as const },
            { label: "LLM (NIM)",   key: "llm" as const },
          ].map(({ label, key }) => (
            <div key={key} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 7 }}>
              <StatusDot status={sysStatus[key]} />
              <span style={{ color: "#94a3b8", fontSize: 12, flex: 1 }}>{label}</span>
              <span style={{ color: sysStatus[key] === "ok" ? "#22c55e" : sysStatus[key] === "error" ? "#ef4444" : "#f59e0b", fontSize: 11, fontWeight: 600 }}>
                {sysStatus[key] === "checking" ? "…" : sysStatus[key].toUpperCase()}
              </span>
            </div>
          ))}
        </div>

        {/* Quick questions */}
        <div style={{ padding: "14px 18px", flex: 1, overflow: "auto" }}>
          <div style={{ color: "#64748b", fontSize: 11, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: 10 }}>
            Quick Questions
          </div>
          {QUICK_QUESTIONS.map(({ label, text }) => (
            <button
              key={label}
              onClick={() => handleSend(text)}
              disabled={sending}
              style={{
                width: "100%",
                textAlign: "left",
                padding: "8px 10px",
                marginBottom: 4,
                borderRadius: 8,
                border: "1px solid #1e293b",
                background: "transparent",
                color: "#94a3b8",
                fontSize: 12,
                cursor: sending ? "default" : "pointer",
                transition: "all 0.15s",
                display: "flex",
                alignItems: "center",
                gap: 7,
              }}
              onMouseEnter={(e) => { if (!sending) { (e.currentTarget as HTMLButtonElement).style.background = "#1e293b"; (e.currentTarget as HTMLButtonElement).style.color = "#e2e8f0"; } }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; (e.currentTarget as HTMLButtonElement).style.color = "#94a3b8"; }}
            >
              <span style={{ color: "#4f46e5", fontSize: 10 }}>›</span>
              {label}
            </button>
          ))}
        </div>

        {/* Session + API key */}
        <div style={{ padding: "12px 18px", borderTop: "1px solid #1e293b" }}>
          {sessionId && (
            <div style={{ color: "#475569", fontSize: 10, marginBottom: 8, fontFamily: "monospace", wordBreak: "break-all" }}>
              Session {sessionId.slice(0, 20)}…
            </div>
          )}
          <button
            onClick={() => { setShowKeyPanel(!showKeyPanel); setKeyDraft(apiKey); }}
            style={{
              width: "100%",
              padding: "7px 10px",
              borderRadius: 8,
              border: "1px solid #1e293b",
              background: "transparent",
              color: "#64748b",
              fontSize: 12,
              cursor: "pointer",
              textAlign: "left",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            🔑 <span>{apiKey ? "API key set" : "Set API key"}</span>
          </button>
          {showKeyPanel && (
            <div style={{ marginTop: 8, background: "#1e293b", borderRadius: 8, padding: 10 }}>
              <input
                value={keyDraft}
                onChange={(e) => setKeyDraft(e.target.value)}
                placeholder="Enter API key"
                style={{
                  width: "100%",
                  padding: "6px 8px",
                  borderRadius: 6,
                  border: "1px solid #334155",
                  background: "#0f172a",
                  color: "#e2e8f0",
                  fontSize: 12,
                  boxSizing: "border-box",
                  outline: "none",
                }}
              />
              <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                <button
                  onClick={saveKey}
                  style={{ flex: 1, padding: "5px 0", borderRadius: 6, border: "none", background: "#4f46e5", color: "white", fontSize: 11, cursor: "pointer", fontWeight: 600 }}
                >
                  Save
                </button>
                <button
                  onClick={() => setShowKeyPanel(false)}
                  style={{ flex: 1, padding: "5px 0", borderRadius: 6, border: "1px solid #334155", background: "transparent", color: "#64748b", fontSize: 11, cursor: "pointer" }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* ── Main chat area ────────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>

        {/* Top bar */}
        <header
          style={{
            padding: "0 24px",
            height: 60,
            background: "white",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
            boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
          }}
        >
          <div>
            <span style={{ fontWeight: 700, fontSize: 16, color: "#0f172a" }}>Operations Assistant</span>
            <span
              style={{
                marginLeft: 10,
                fontSize: 11,
                fontWeight: 600,
                color: "#16a34a",
                background: "#dcfce7",
                border: "1px solid #bbf7d0",
                borderRadius: 999,
                padding: "2px 8px",
              }}
            >
              ● LIVE
            </span>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <span style={{ color: "#94a3b8", fontSize: 12 }}>LangGraph · NVIDIA NIM · Postgres</span>
            <button
              onClick={() => {
                setMessages([{ role: "assistant", text: "Hi! I'm your Operations Assistant.\n\nI can help with order lookups, refund requests, shipping questions, and more. Try one of the quick questions on the left, or describe your issue." }]);
                setSessionId(null);
              }}
              style={{
                padding: "5px 12px",
                borderRadius: 8,
                border: "1px solid #e2e8f0",
                background: "white",
                color: "#64748b",
                fontSize: 12,
                cursor: "pointer",
                fontWeight: 500,
              }}
            >
              New session
            </button>
          </div>
        </header>

        {/* Message list */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "20px 24px",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {messages.map((m, i) => (
            <MessageBubble key={i} message={m} />
          ))}
          {sending && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>

        {/* Confirmation banner */}
        {awaitingConfirmation && (
          <div
            style={{
              margin: "0 24px 8px",
              padding: "12px 16px",
              borderRadius: 12,
              background: "#fffbeb",
              border: "1px solid #fde68a",
              display: "flex",
              alignItems: "center",
              gap: 12,
              boxShadow: "0 1px 4px rgba(251,191,36,0.2)",
            }}
          >
            <span style={{ fontSize: 20 }}>⚠️</span>
            <span style={{ flex: 1, fontSize: 13, color: "#92400e", fontWeight: 500 }}>
              An action requires your approval before it executes
            </span>
            <button
              onClick={() => handleSend("yes")}
              disabled={sending}
              style={{
                padding: "7px 18px",
                borderRadius: 8,
                border: "none",
                background: "#16a34a",
                color: "white",
                fontWeight: 600,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              ✓ Confirm
            </button>
            <button
              onClick={() => handleSend("no")}
              disabled={sending}
              style={{
                padding: "7px 18px",
                borderRadius: 8,
                border: "1px solid #fde68a",
                background: "white",
                color: "#92400e",
                fontWeight: 600,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              ✗ Cancel
            </button>
          </div>
        )}

        {/* Input bar */}
        <div
          style={{
            padding: "12px 24px 16px",
            background: "white",
            borderTop: "1px solid #e2e8f0",
            flexShrink: 0,
          }}
        >
          <div
            style={{
              display: "flex",
              gap: 10,
              alignItems: "center",
              background: "#f8fafc",
              border: "1.5px solid #e2e8f0",
              borderRadius: 14,
              padding: "4px 4px 4px 16px",
              transition: "border-color 0.15s",
            }}
            onFocus={() => {}}
          >
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
              placeholder="e.g. I was double-charged for order #1042…"
              disabled={sending}
              style={{
                flex: 1,
                border: "none",
                background: "transparent",
                fontSize: 14,
                color: "#0f172a",
                outline: "none",
                padding: "8px 0",
                caretColor: "#4f46e5",
              }}
            />
            <button
              onClick={() => handleSend()}
              disabled={sending || !input.trim()}
              style={{
                padding: "9px 20px",
                borderRadius: 10,
                border: "none",
                background: sending || !input.trim() ? "#e2e8f0" : "linear-gradient(135deg, #4f46e5, #6366f1)",
                color: sending || !input.trim() ? "#94a3b8" : "white",
                fontWeight: 600,
                fontSize: 13,
                cursor: sending || !input.trim() ? "default" : "pointer",
                transition: "all 0.15s",
                whiteSpace: "nowrap",
              }}
            >
              {sending ? "Thinking…" : "Send ›"}
            </button>
          </div>
          <div style={{ marginTop: 6, display: "flex", justifyContent: "center" }}>
            <span style={{ fontSize: 11, color: "#94a3b8" }}>
              Orders · Refunds · Shipping · Escalation — all tool calls visible above each reply
            </span>
          </div>
        </div>
      </div>

      {/* Global CSS for typing animation */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        * { box-sizing: border-box; }
        body { margin: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
        @keyframes typing-bounce {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
          30%            { transform: translateY(-5px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
