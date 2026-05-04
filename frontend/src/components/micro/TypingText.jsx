import { useEffect, useState } from "react";

export default function TypingText({ text, speed = 22, onDone }) {
  const [d, setD] = useState("");
  useEffect(() => {
    setD("");
    let i = 0;
    const t = setInterval(() => {
      if (i < text.length) { setD(text.slice(0, i + 1)); i++; }
      else { clearInterval(t); onDone && onDone(); }
    }, speed);
    return () => clearInterval(t);
  }, [text, speed, onDone]);
  return (
    <span>{d}<span style={{
      opacity: d.length < text.length ? 1 : 0,
      animation: "blink .8s steps(1) infinite"
    }}>|</span></span>
  );
}
