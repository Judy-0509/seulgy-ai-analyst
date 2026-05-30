import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Wordmark from "../components/Wordmark";
import "./NewsPage.css";

const DAY_OPTIONS = [
  { value: 1, label: "오늘" },
  { value: 3, label: "3일" },
  { value: 7, label: "1주일" },
  { value: 30, label: "1개월" },
];

const TIER3_INSTITUTIONS = [
  { name: 'Counterpoint Research', type: 'research' },
  { name: 'Canalys',               type: 'research' },
  { name: 'TrendForce PR',         type: 'research' },
  { name: 'Digitimes',             type: 'trade' },
  { name: 'The Elec',              type: 'trade' },
  { name: 'Reuters Tech',          type: 'wire' },
  { name: 'SCMP Tech',             type: 'wire' },
  { name: 'Nikkei Asia Tech',      type: 'wire' },
];

const AREA_GROUPS = [
  {
    label: "Application",
    items: [
      ["smartphone", "Smartphone"],
      ["tablet", "Tablet"],
      ["pc", "PC"],
      ["automotive", "Automotive"],
      ["humanoid", "Humanoid"],
    ],
  },
  {
    label: "Technology",
    items: [
      ["semiconductor", "Semiconductor"],
      ["memory", "Memory"],
      ["foundry", "Foundry"],
      ["hbm", "HBM"],
    ],
  },
];

const SORT_OPTIONS = [
  ["importance", "중요도"],
  ["recent", "최신순"],
  ["cluster", "묶음순"],
  ["tier", "출처 등급"],
];

function makeParams(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach(item => query.append(key, item));
    } else if (value !== undefined && value !== null && value !== "") {
      query.set(key, value);
    }
  });
  return query.toString();
}

async function getJson(path, params = {}) {
  const query = makeParams(params);
  const res = await fetch(`${path}${query ? `?${query}` : ""}`);
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return res.json();
}

function formatAge(value) {
  if (!value) return "";
  const diff = Date.now() - new Date(value).getTime();
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return "방금 전";
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

function sortArticles(articles, sortBy) {
  const list = [...articles];
  if (sortBy === "recent") {
    return list.sort((a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0));
  }
  if (sortBy === "cluster") {
    return list.sort((a, b) => (b.cluster_size || 1) - (a.cluster_size || 1));
  }
  if (sortBy === "tier") {
    return list.sort((a, b) => (b.source_tier || 1) - (a.source_tier || 1));
  }
  return list.sort((a, b) => (b.importance || 0) - (a.importance || 0));
}

function toggleSetValue(setter, value) {
  setter(prev => {
    const next = new Set(prev);
    next.has(value) ? next.delete(value) : next.add(value);
    return next;
  });
}

function VendorRow({ vendor, selected, expanded, onToggle, onExpand, depth = 0 }) {
  const hasChildren = vendor.children?.length > 0;
  const active = selected.has(vendor.id);

  return (
    <>
      <div className={`news-filter-row news-filter-row--depth-${depth} ${active ? "is-active" : ""}`}>
        <button type="button" className="news-filter-main" onClick={() => onToggle(vendor.id)}>
          <span>{vendor.label}</span>
          <span>{vendor.count}</span>
        </button>
        {hasChildren && (
          <button type="button" className="news-filter-expand" onClick={() => onExpand(vendor.id)}>
            {expanded.has(vendor.id) ? "⌃" : "⌄"}
          </button>
        )}
      </div>
      {hasChildren && expanded.has(vendor.id) && vendor.children.map(child => (
        <VendorRow
          key={child.id}
          vendor={child}
          selected={selected}
          expanded={expanded}
          onToggle={onToggle}
          onExpand={onExpand}
          depth={depth + 1}
        />
      ))}
    </>
  );
}

function ArticleCard({ article, onVendorClick, onIssueClick }) {
  const summary = article.summary_ko || article.summary_en || article.description;
  const importance = Number(article.importance || 0);

  return (
    <article className="news-card">
      <div className="news-card__meta">
        <span className={`news-card__dot ${importance >= 7 ? "high" : importance >= 4 ? "mid" : ""}`} />
        <span>{article.source_name || "Unknown"}</span>
        {article.source_tier === 3 && <span className="news-card__badge">Research</span>}
        {article.cluster_size > 1 && <span className="news-card__badge">+{article.cluster_size - 1}</span>}
        <span>{formatAge(article.published_at)}</span>
        <span>{article.language === "ko" ? "KO" : "EN"}</span>
      </div>
      <a className="news-card__title" href={article.url} target="_blank" rel="noreferrer">
        {article.title}
      </a>
      {summary && <p className="news-card__summary">{summary}</p>}
      <div className="news-card__tags">
        {(article.vendor_tags || []).map(tag => (
          <button type="button" key={tag} className="news-chip news-chip--vendor" onClick={() => onVendorClick(tag)}>
            {tag}
          </button>
        ))}
        {(article.issue_tags || []).map(tag => (
          <button type="button" key={tag} className="news-chip" onClick={() => onIssueClick(tag)}>
            {tag}
          </button>
        ))}
      </div>
    </article>
  );
}

export default function NewsPage() {
  const nav = useNavigate();
  const [articles, setArticles] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [issues, setIssues] = useState([]);
  const [meta, setMeta] = useState(null);
  const [selectedVendors, setSelectedVendors] = useState(new Set());
  const [selectedIssues, setSelectedIssues] = useState(new Set());
  const [selectedAreas, setSelectedAreas] = useState(new Set());
  const [expandedVendors, setExpandedVendors] = useState(new Set(["CN Brands"]));
  const [days, setDays] = useState(7);
  const [lang, setLang] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState("importance");
  const [tier3Only, setTier3Only] = useState(false);
  const [excludedInstitutions, setExcludedInstitutions] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function toggleExcluded(name) {
    setExcludedInstitutions(prev => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }

  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 250);
    return () => clearTimeout(timer);
  }, [search]);

  const fetchNews = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = {
        days,
        limit: 500,
        vendor: [...selectedVendors],
        issue: [...selectedIssues],
        area: [...selectedAreas],
        tier3_only: tier3Only,
        search: query,
        lang,
      };
      const [newsData, vendorData, issueData] = await Promise.all([
        getJson("/api/news", params),
        getJson("/api/news/vendors", { days }),
        getJson("/api/news/issues", { days }),
      ]);
      setArticles(newsData.articles || []);
      setVendors(vendorData || []);
      setIssues(issueData || []);
    } catch {
      setError("News 데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [days, lang, query, selectedAreas, selectedIssues, selectedVendors, tier3Only]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchNews();
  }, [fetchNews]);

  useEffect(() => {
    getJson("/api/news/meta").then(setMeta).catch(() => {});
  }, []);

  const displayedArticles = useMemo(() => {
    let filtered = articles;
    if (tier3Only && excludedInstitutions.size > 0) {
      filtered = filtered.filter(a => !excludedInstitutions.has(a.source_name));
    }
    return sortArticles(filtered, sortBy);
  }, [articles, sortBy, tier3Only, excludedInstitutions]);
  const hasFilters = selectedVendors.size || selectedIssues.size || selectedAreas.size || query || lang || tier3Only;

  function clearFilters() {
    setSelectedVendors(new Set());
    setSelectedIssues(new Set());
    setSelectedAreas(new Set());
    setSearch("");
    setQuery("");
    setLang("");
    setTier3Only(false);
  }

  return (
    <div className="news-page">
      <header className="news-topbar">
        <div className="news-topbar__left">
          <button type="button" className="news-brand" onClick={() => nav("/")} aria-label="Home">
            <Wordmark size={20} />
            <div>
              <h1>News</h1>
              <p>마켓 인텔리전스 뉴스 스트림</p>
            </div>
          </button>
        </div>
        <nav className="news-nav">
          <button type="button" onClick={() => nav("/")}>홈</button>
          <button type="button" onClick={() => nav("/archive")}>아카이브</button>
          <button type="button" onClick={() => nav("/db")}>DB</button>
        </nav>
      </header>

      <main className="news-layout">
        <aside className="news-sidebar">
          <section className="news-panel">
            <label className="news-search">
              <span>검색</span>
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="keyword, source, topic" />
            </label>
          </section>

          <section className="news-panel">
            <div className="news-panel__label">기간</div>
            <div className="news-segment">
              {DAY_OPTIONS.map(opt => (
                <button key={opt.value} type="button" className={days === opt.value ? "is-active" : ""} onClick={() => setDays(opt.value)}>
                  {opt.label}
                </button>
              ))}
            </div>
          </section>

          <section className="news-panel">
            <div className="news-panel__label">언어</div>
            <div className="news-segment">
              {[["", "전체"], ["en", "EN"], ["ko", "한국어"]].map(([value, label]) => (
                <button key={value || "all"} type="button" className={lang === value ? "is-active" : ""} onClick={() => setLang(value)}>
                  {label}
                </button>
              ))}
            </div>
          </section>

          <section className="news-panel">
            <div className="news-panel__label">Area</div>
            {AREA_GROUPS.map(group => (
              <div className="news-area" key={group.label}>
                <strong>{group.label}</strong>
                <div className="news-chip-list">
                  {group.items.map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      className={`news-filter-chip ${selectedAreas.has(id) ? "is-active" : ""}`}
                      onClick={() => toggleSetValue(setSelectedAreas, id)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </section>

          <section className="news-panel">
            <div className="news-panel__label">조사기관</div>
            <button type="button" className={`news-wide-toggle ${tier3Only ? "is-active" : ""}`} onClick={() => setTier3Only(v => !v)}>
              조사기관만 보기
            </button>
            {tier3Only && (
              <div className="news-tier3-list">
                <div className="news-tier3-group">
                  <span className="news-tier3-group-label">리서치</span>
                  <div className="news-tier3-tags">
                    {TIER3_INSTITUTIONS.filter(i => i.type === 'research').map(i => (
                      <button
                        key={i.name}
                        type="button"
                        className={`news-tier3-tag ${excludedInstitutions.has(i.name) ? "is-excluded" : ""}`}
                        onClick={() => toggleExcluded(i.name)}
                        title={excludedInstitutions.has(i.name) ? '클릭하여 포함' : '클릭하여 제외'}
                      >{i.name}</button>
                    ))}
                  </div>
                </div>
                <div className="news-tier3-group">
                  <span className="news-tier3-group-label">주요 미디어</span>
                  <div className="news-tier3-tags">
                    {TIER3_INSTITUTIONS.filter(i => i.type === 'wire').map(i => (
                      <button
                        key={i.name}
                        type="button"
                        className={`news-tier3-tag ${excludedInstitutions.has(i.name) ? "is-excluded" : ""}`}
                        onClick={() => toggleExcluded(i.name)}
                        title={excludedInstitutions.has(i.name) ? '클릭하여 포함' : '클릭하여 제외'}
                      >{i.name}</button>
                    ))}
                  </div>
                </div>
                <div className="news-tier3-group">
                  <span className="news-tier3-group-label">업계 전문지</span>
                  <div className="news-tier3-tags">
                    {TIER3_INSTITUTIONS.filter(i => i.type === 'trade').map(i => (
                      <button
                        key={i.name}
                        type="button"
                        className={`news-tier3-tag ${excludedInstitutions.has(i.name) ? "is-excluded" : ""}`}
                        onClick={() => toggleExcluded(i.name)}
                        title={excludedInstitutions.has(i.name) ? '클릭하여 포함' : '클릭하여 제외'}
                      >{i.name}</button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </section>

          <section className="news-panel">
            <div className="news-panel__label">조사기관/Vendor</div>
            {vendors.length === 0 ? <p className="news-empty-small">벤더 태그 없음</p> : vendors.map(vendor => (
              <VendorRow
                key={vendor.id}
                vendor={vendor}
                selected={selectedVendors}
                expanded={expandedVendors}
                onToggle={id => toggleSetValue(setSelectedVendors, id)}
                onExpand={id => toggleSetValue(setExpandedVendors, id)}
              />
            ))}
          </section>

          <section className="news-panel">
            <div className="news-panel__label">이슈</div>
            {issues.length === 0 ? <p className="news-empty-small">이슈 태그 없음</p> : issues.map(issue => (
              <button
                key={issue.id}
                type="button"
                className={`news-filter-row news-filter-main ${selectedIssues.has(issue.id) ? "is-active" : ""}`}
                onClick={() => toggleSetValue(setSelectedIssues, issue.id)}
              >
                <span>{issue.label}</span>
                <span>{issue.count}</span>
              </button>
            ))}
          </section>
        </aside>

        <section className="news-content">
          <div className="news-toolbar">
            <div>
              <p className="news-kicker">MI News</p>
              <h2>{loading ? "불러오는 중" : `${displayedArticles.length}개 기사`}</h2>
              {meta?.last_collected_at && (
                <p className="news-meta">
                  마지막 수집 {new Date(meta.last_collected_at).toLocaleString("ko-KR", { hour12: false })}
                </p>
              )}
            </div>
            <div className="news-toolbar__actions">
              {hasFilters ? <button type="button" onClick={clearFilters}>필터 초기화</button> : null}
              <div className="news-segment news-segment--sort">
                {SORT_OPTIONS.map(([value, label]) => (
                  <button key={value} type="button" className={sortBy === value ? "is-active" : ""} onClick={() => setSortBy(value)}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {error && <div className="news-state news-state--error">{error}</div>}
          {!error && loading && displayedArticles.length === 0 && <div className="news-state">News 데이터를 불러오고 있습니다.</div>}
          {!error && !loading && displayedArticles.length === 0 && <div className="news-state">현재 필터에 맞는 기사가 없습니다.</div>}
          <div className="news-feed">
            {displayedArticles.map(article => (
              <ArticleCard
                key={article.id}
                article={article}
                onVendorClick={tag => toggleSetValue(setSelectedVendors, tag)}
                onIssueClick={tag => toggleSetValue(setSelectedIssues, tag)}
              />
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
