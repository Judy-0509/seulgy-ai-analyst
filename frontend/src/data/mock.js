// Pipeline step definitions — content data filled in as each step completes
export const PIPELINE_STEPS = [
  {
    id: "A", step: 1, label: "영문 검색 쿼리 생성", type: "llm", status: "pending",
    description: "LLM이 주제를 분석해 Tier-1 기관 아카이브에 최적화된 영문 검색 쿼리를 생성합니다.",
  },
  {
    id: "B", step: 2, label: "아카이브 사전 검색", type: "search", status: "pending",
    description: "Omdia, Counterpoint, TrendForce, IDC 아카이브에서 관련 리포트 인덱스를 확인합니다.",
  },
  {
    id: "C", step: 3, label: "목차 + 섹션별 검색어 생성", type: "llm", status: "pending",
    description: "수집된 인덱스를 기반으로 보고서 목차를 구성하고 섹션별 심층 검색어를 생성합니다.",
  },
  {
    id: "GATE1", step: 4, label: "GATE 1 — 목차 검토", type: "gate", status: "pending",
    description: "생성된 목차와 섹션별 검색어를 사용자가 검토하고 확정하는 단계입니다.",
  },
  {
    id: "D", step: 5, label: "섹션별 본격 검색 실행", type: "search", status: "pending",
    description: "확정된 목차별 검색어로 Tier-1 아카이브 전체를 심층 검색합니다.",
  },
  {
    id: "GATE2", step: 6, label: "GATE 2 — 검색결과 검토", type: "gate", status: "pending",
    description: "목차별 수집 자료를 확인하고 추가 검색 여부를 결정하는 단계입니다.",
  },
  {
    id: "EF", step: 7, label: "본문 fetch + 목차별 분석", type: "llm", status: "pending",
    description: "각 목차별로 수집 자료를 fetch하고 LLM이 심층 분석 내용을 작성합니다.",
  },
  {
    id: "G", step: 8, label: "Executive Summary + 시사점 도출", type: "llm", status: "pending",
    description: "전체 분석을 종합하여 Executive Summary와 핵심 시사점을 작성합니다.",
  },
];
