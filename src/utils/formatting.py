def format_data_gap_message(gap_dimension: str, recommendation: str) -> str:
    return (
        f"**데이터 갭 감지**: `{gap_dimension}`에 대한 정량적 데이터를 확보하지 못했습니다.\n\n"
        f"**권고사항**: {recommendation}\n\n"
        "유료 데이터 없이 진행하시겠습니까? (분석은 계속되나 해당 차원의 수치가 누락될 수 있습니다)"
    )
