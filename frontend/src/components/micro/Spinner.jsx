import { C } from "../../theme";

export default function Spinner({ size = 14, color = C.ind }) {
  return (
    <span style={{
      display: "inline-block", width: size, height: size,
      border: `2px solid ${color}30`, borderTopColor: color,
      borderRadius: "50%", animation: "spin .7s linear infinite"
    }} />
  );
}
