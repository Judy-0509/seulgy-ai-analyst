import { Navigate, useLocation, useNavigate } from "react-router-dom";
import PipelineScreen from "../components/PipelineScreen";

export default function AppPage() {
  const location = useLocation();
  const nav = useNavigate();
  const initTopic = location.state?.startTopic || "";
  const initTopicInfo = location.state?.topicInfo || null;

  if (initTopic) {
    return <PipelineScreen topic={initTopic} topicInfo={initTopicInfo} onBack={() => nav("/")} />;
  }

  return <Navigate to="/" replace />;
}
