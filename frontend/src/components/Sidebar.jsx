import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDomain } from "../contexts/DomainContext";

const DOMAINS = [
  { id: "smartphone", label: "Smartphone" },
  { id: "humanoid", label: "Humanoid" },
];

function HamburgerIcon() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4.5, flexShrink: 0 }}>
      {[0, 1, 2].map(i => (
        <div
          key={i}
          style={{
            width: 20,
            height: 2.25,
            background: "rgba(255,255,255,.88)",
            borderRadius: 99,
          }}
        />
      ))}
    </div>
  );
}

export default function Sidebar() {
  const { domain, switchDomain } = useDomain();
  const [open, setOpen] = useState(false);
  const nav = useNavigate();

  return (
    <div
      style={{
        position: "fixed",
        top: 16,
        left: 16,
        zIndex: 200,
        width: open ? 196 : 42,
        height: open ? 164 : 42,
        pointerEvents: "none",
      }}
    >
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          zIndex: 2,
          width: 42,
          height: 42,
          borderRadius: 0,
          border: "none",
          background: "transparent",
          boxShadow: "none",
          backdropFilter: "none",
          WebkitBackdropFilter: "none",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          pointerEvents: "auto",
        }}
        title="Menu"
      >
        <HamburgerIcon />
      </button>

      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: 196,
          minHeight: 156,
          overflow: "hidden",
          transform: open ? "translateX(0)" : "translateX(-218px)",
          opacity: open ? 1 : 0,
          visibility: open ? "visible" : "hidden",
          transition: "transform .28s cubic-bezier(.22,1,.36,1), opacity .18s ease, visibility .18s",
          background: "rgba(22,22,24,.34)",
          backdropFilter: "blur(30px) saturate(180%)",
          WebkitBackdropFilter: "blur(30px) saturate(180%)",
          border: "none",
          borderRadius: 18,
          boxShadow: "0 24px 70px rgba(0,0,0,.24)",
          pointerEvents: open ? "auto" : "none",
        }}
      >
        <div style={{ padding: "54px 8px 10px", whiteSpace: "nowrap" }}>
          {DOMAINS.map(d => {
            const active = domain.id === d.id;
            return (
              <button
                key={d.id}
                onClick={() => {
                  switchDomain(d.id);
                  nav("/");
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  width: "100%",
                  height: 42,
                  background: active ? "rgba(255,255,255,.13)" : "transparent",
                  border: "none",
                  borderRadius: 12,
                  cursor: "pointer",
                  padding: "0 12px",
                  textAlign: "left",
                  color: active ? "#fff" : "rgba(255,255,255,.68)",
                  fontSize: 13,
                  fontWeight: active ? 700 : 500,
                  letterSpacing: 0,
                  transition: "background .15s, color .15s",
                }}
              >
                <span>{d.label}</span>
                {active && (
                  <span style={{ width: 6, height: 6, borderRadius: 99, background: "#fff", opacity: .9 }} />
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
