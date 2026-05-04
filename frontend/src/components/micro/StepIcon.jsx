import { C } from "../../theme";
import Spinner from "./Spinner";

export default function StepIcon({ type, status }) {
  const isGate = type === "gate";
  const isDone = status === "done";
  const isRun = status === "running";

  if (isGate) {
    return (
      <div style={{
        width: 34, height: 34, borderRadius: 9,
        background: isDone ? C.ambBg : "#fff7ed",
        border: `2px solid ${isDone ? C.amb : C.ambBr}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 15, flexShrink: 0, color: C.ambD
      }}>✦</div>
    );
  }
  return (
    <div style={{
      width: 34, height: 34, borderRadius: 9,
      background: isDone ? C.indBg : isRun ? C.indBg : C.subtle,
      border: `2px solid ${isDone ? C.indBr : isRun ? C.ind : C.border}`,
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: isRun ? 12 : 16, flexShrink: 0,
      color: isDone ? C.ind : isRun ? C.ind : C.t4,
      animation: isRun ? "glow 2s ease-in-out infinite" : "none"
    }}>
      {isRun ? <Spinner size={12} /> : (type === "llm" ? "◈" : "⌕")}
    </div>
  );
}
