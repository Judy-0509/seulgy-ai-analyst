# {도메인} 소스 조사 — {조사 토픽}

- **도메인**: smartphone / humanoid / automotive / space_datacenter
- **조사일**: YYYY-MM-DD
- **조사자**: (사람 / Claude 모델)
- **트리거**: 어떤 질문/필요로 시작했는지

---

## 1. 현재 아카이브 상태

| 소스 | 레이어 | 기사 수 | 비고 |
|---|---|---|---|
| ... | A | 100건 | active |
| ... | D | 1건 | thin |

### 진단
- 강점:
- 약점 (Gap):

---

## 2. Gap 식별 근거

- 어떤 종류 데이터/관점이 부족한가?
- 메이저 패스 Crit 2 교차 부족 패턴이 있는가?

---

## 3. 후보 소스 조사

### Tier-1 (높은 인용 빈도)
| 소스 | 발행 형태 | 인용 빈도 근거 | 보유 여부 |
|---|---|---|---|
| ... | ... | "according to ..." 검색 결과 | ❌ / ✅ |

### Tier-2 (보조)
| 소스 | 형태 | 비고 |
|---|---|---|

---

## 4. robots.txt 검토

| 사이트 | User-agent: * | 차단 경로 | 대상 경로 허용 | sitemap |
|---|---|---|---|---|
| ... | ... | ... | ✅ / ❌ | URL |

전체 robots.txt 원문은 `<details>` 블록으로 첨부 권장.

---

## 5. sitemap 구조 / URL 패턴

- sitemap URL:
- 총 URL 수:
- 키워드 필터 후 hit:
- URL 슬러그 패턴:

---

## 6. 결정

| 후보 | 결정 | 이유 |
|---|---|---|
| ... | 선정 | 가장 자주 인용 + sitemap 안정 + 무료 공개 |
| ... | 보류 | paywall, 메타데이터 빈약 |
| ... | 제외 | robots.txt 차단 |

---

## 7. 빌더 구현 메모

- 빌더 파일: `scripts/build_xxx_archive.py`
- 산출 파일: `data/archives/xxx.json`
- 첫 빌드 결과: N건
- 등록 위치:
  - [ ] `scripts/build_all_archives.py`
  - [ ] `src/server.py` ARCHIVE_REGISTRY
  - [ ] `scripts/suggest_<domain>_topics.py` (registry / label / taxonomy / filter)
  - [ ] `CLAUDE.md`

---

## 8. 후속 작업

- 검증 항목:
- 다음 조사 후보:
