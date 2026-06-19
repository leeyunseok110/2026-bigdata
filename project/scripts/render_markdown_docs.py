from pathlib import Path
import html

import markdown


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DOCUMENTS = [
    ("기획서", "중고차 데이터 분석 및 가격 예측 서비스 기획서"),
    ("보고서", "중고차 데이터 분석 및 가격 예측 서비스 보고서"),
]


def render_document(stem: str, title: str) -> Path:
    source_path = PROJECT_ROOT / f"{stem}.md"
    output_path = PROJECT_ROOT / f"{stem}.html"
    body = markdown.markdown(
        source_path.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code", "toc"],
    )
    document = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="docs/report.css" />
</head>
<body>
{body}
</body>
</html>
"""
    output_path.write_text(document, encoding="utf-8")
    return output_path


def main() -> None:
    for stem, title in DOCUMENTS:
        output_path = render_document(stem, title)
        print(f"updated {output_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
