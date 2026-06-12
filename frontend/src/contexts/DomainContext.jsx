/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState } from "react";

const DOMAINS = [
  { id: "smartphone", label: "Smartphone", icon: "📱" },
  { id: "humanoid",   label: "Humanoid",   icon: "🤖" },
  { id: "automotive", label: "Automotive", icon: "🚗" },
  { id: "smartglass", label: "SmartGlass", icon: "🥽" },
  { id: "tablet",     label: "Tablet",     icon: "📲" },
  { id: "macro",      label: "Macro",      icon: "📊" },
];

const DomainContext = createContext(null);

export function DomainProvider({ children }) {
  const [domainId, setDomainId] = useState(
    () => localStorage.getItem("canopy_domain") || "smartphone"
  );

  const domain = DOMAINS.find(d => d.id === domainId) || DOMAINS[0];

  const switchDomain = (id) => {
    localStorage.setItem("canopy_domain", id);
    setDomainId(id);
  };

  return (
    <DomainContext.Provider value={{ domain, domains: DOMAINS, switchDomain }}>
      {children}
    </DomainContext.Provider>
  );
}

export const useDomain = () => useContext(DomainContext);
