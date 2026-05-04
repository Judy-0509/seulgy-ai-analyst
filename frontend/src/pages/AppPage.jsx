import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import HomeScreen from "../components/HomeScreen";
import PipelineScreen from "../components/PipelineScreen";

export default function AppPage() {
  const location = useLocation();
  const nav = useNavigate();
  const initTopic = location.state?.startTopic || "";
  const [screen, setScreen] = useState(initTopic ? "pipeline" : "home");
  const [topic, setTopic] = useState(initTopic);

  const handleStart = (t) => {
    setTopic(t);
    setScreen("pipeline");
  };

  if (screen === "pipeline") {
    return <PipelineScreen topic={topic} onBack={() => nav("/")} />;
  }

  return <HomeScreen onStart={handleStart} />;
}
