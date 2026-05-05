// Design tokens — extracted from Spark App.html
export const C = {
  bg:       "#f7f6f3",
  card:     "#ffffff",
  subtle:   "#f0eff0",
  subtle2:  "#e8e7e4",
  t1: "#0f172a", t2: "#1e293b", t3: "#64748b", t4: "#94a3b8",
  border: "#e2e0db", borderM: "#cac8c2",
  // indigo — AI / primary
  ind:  "#4f46e5", indD: "#3730a3", indBg: "#eef2ff", indBr: "#c7d2fe",
  // amber — GATE / human
  amb:  "#f59e0b", ambD: "#b45309", ambBg: "#fefce8", ambBr: "#fde68a",
  mono: '"SF Mono", ui-monospace, monospace',
};

export const SRC_COLORS = ["#4f46e5","#7c6af7","#a5b4fc","#f59e0b","#64748b"];

// Smartphone sources → shades of green
// Humanoid sources   → shades of red
export const SRC_COLOR_MAP = {
  // Smartphone (8 distinct greens)
  "Counterpoint Research": "#166534",
  "TrendForce":            "#15803d",
  "Omdia":                 "#16a34a",
  "IDC":                   "#22c55e",
  "Reuters":               "#4ade80",
  "Yole":                  "#86efac",
  "Gartner":               "#bbf7d0",
  "Morgan Stanley":        "#dcfce7",
  // Humanoid (11 distinct reds)
  "The Robot Report":        "#7f1d1d",
  "IEEE Spectrum":           "#991b1b",
  "TechCrunch Robotics":     "#b91c1c",
  "MIT Technology Review":   "#dc2626",
  "Robotics & Automation News": "#ef4444",
  "The Verge":               "#f87171",
  "arXiv (cs.RO)":           "#fca5a5",
  "NVIDIA":                  "#fecaca",
  "Boston Dynamics":         "#fee2e2",
  "Figure AI":               "#fda4af",
  "Unitree Robotics":        "#fb7185",
};

export const TAG_COLORS = {
  "위성통신": { bg:"#eef2ff", c:"#3730a3" },
  "M&A":     { bg:"#fefce8", c:"#b45309" },
  "반도체":   { bg:"#f1f5f9", c:"#334155" },
  "규제":     { bg:"#fefce8", c:"#b45309" },
  "서비스":   { bg:"#eef2ff", c:"#4338ca" },
  "경쟁":     { bg:"#f1f5f9", c:"#334155" },
  "유럽":     { bg:"#eef2ff", c:"#3730a3" },
  "부품":     { bg:"#fefce8", c:"#92400e" },
};
