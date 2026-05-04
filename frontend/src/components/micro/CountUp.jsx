import { useEffect, useState } from "react";

export default function CountUp({ to, duration = 1100 }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    const s = Date.now();
    const f = () => {
      const p = Math.min((Date.now() - s) / duration, 1);
      const e = 1 - Math.pow(1 - p, 3);
      setV(Math.round(e * to));
      if (p < 1) requestAnimationFrame(f);
    };
    requestAnimationFrame(f);
  }, [to, duration]);
  return <span>{v}</span>;
}
