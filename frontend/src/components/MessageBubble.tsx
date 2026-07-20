export interface Message {
  role: "user" | "assistant" | "system";
  text: string;
  escalated?: boolean;
  awaitingConfirmation?: boolean;
  toolCalls?: string[];
}

const TOOL_META: Record<string, { icon: string; color: string; bg: string }> = {
  knowledge_search:  { icon: "📚", color: "#7c3aed", bg: "#ede9fe" },
  lookup_order:      { icon: "📦", color: "#0369a1", bg: "#e0f2fe" },
  take_action:       { icon: "⚡", color: "#b45309", bg: "#fef3c7" },
  escalate_to_human: { icon: "🚨", color: "#b91c1c", bg: "#fee2e2" },
};

function ToolChip({ name }: { name: string }) {
  const meta = TOOL_META[name] ?? { icon: "🔧", color: "#475569", bg: "#f1f5f9" };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 8px",
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: "0.02em",
        color: meta.color,
        background: meta.bg,
        marginRight: 4,
        marginBottom: 2,
        border: `1px solid ${meta.color}22`,
      }}
    >
      {meta.icon} {name.replace(/_/g, " ")}
    </span>
  );
}

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end", margin: "12px 0 4px" }}>
        <div
          style={{
            maxWidth: "72%",
            padding: "10px 15px",
            borderRadius: "18px 18px 4px 18px",
            background: "linear-gradient(135deg, #4f46e5, #6366f1)",
            color: "white",
            fontSize: 14,
            lineHeight: 1.55,
            boxShadow: "0 2px 8px rgba(79,70,229,0.25)",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {message.text}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 10, margin: "12px 0 4px" }}>
      {/* Bot avatar */}
      <div
        style={{
          flexShrink: 0,
          width: 34,
          height: 34,
          borderRadius: "50%",
          background: "linear-gradient(135deg, #0f172a, #334155)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 16,
          boxShadow: "0 1px 4px rgba(0,0,0,0.15)",
          marginTop: 2,
        }}
      >
        🤖
      </div>

      <div style={{ maxWidth: "72%", minWidth: 60 }}>
        {/* Tool call chips */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 2 }}>
            {message.toolCalls.map((t, i) => (
              <ToolChip key={i} name={t} />
            ))}
          </div>
        )}

        {/* Message bubble */}
        <div
          style={{
            padding: "10px 15px",
            borderRadius: "4px 18px 18px 18px",
            background: "white",
            color: "#0f172a",
            fontSize: 14,
            lineHeight: 1.6,
            boxShadow: "0 1px 3px rgba(0,0,0,0.08), 0 1px 8px rgba(0,0,0,0.04)",
            border: "1px solid #f1f5f9",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {message.text}
        </div>

        {/* Status badges */}
        <div style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
          {message.escalated && (
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#b91c1c",
                background: "#fee2e2",
                border: "1px solid #fecaca",
                borderRadius: 999,
                padding: "2px 8px",
                display: "inline-flex",
                alignItems: "center",
                gap: 3,
              }}
            >
              🚨 Escalated to human
            </span>
          )}
          {message.awaitingConfirmation && (
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#b45309",
                background: "#fef3c7",
                border: "1px solid #fde68a",
                borderRadius: 999,
                padding: "2px 8px",
                display: "inline-flex",
                alignItems: "center",
                gap: 3,
              }}
            >
              ⏸ Awaiting your confirmation
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export function TypingIndicator() {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 10, margin: "12px 0 4px" }}>
      <div
        style={{
          flexShrink: 0,
          width: 34,
          height: 34,
          borderRadius: "50%",
          background: "linear-gradient(135deg, #0f172a, #334155)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 16,
        }}
      >
        🤖
      </div>
      <div
        style={{
          padding: "12px 18px",
          borderRadius: "4px 18px 18px 18px",
          background: "white",
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
          border: "1px solid #f1f5f9",
          display: "flex",
          alignItems: "center",
          gap: 5,
        }}
      >
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "#94a3b8",
              animation: `typing-bounce 1.2s ease-in-out ${i * 0.18}s infinite`,
            }}
          />
        ))}
      </div>
    </div>
  );
}
