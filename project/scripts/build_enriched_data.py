from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.external_data import (  # noqa: E402
    ENRICHED_CARS_PATH,
    EPA_SUMMARY_PATH,
    NHTSA_SUMMARY_PATH,
    enrich_used_cars,
)


def main() -> None:
    enriched = enrich_used_cars(rebuild_external=True)
    epa_matches = int(enriched["external_epa_matched"].sum())
    nhtsa_matches = int(enriched["external_nhtsa_matched"].sum())

    print(f"Saved: {EPA_SUMMARY_PATH}")
    print(f"Saved: {NHTSA_SUMMARY_PATH}")
    print(f"Saved: {ENRICHED_CARS_PATH}")
    print(f"Rows: {len(enriched):,}")
    print(f"EPA matched rows: {epa_matches:,} ({epa_matches / len(enriched):.1%})")
    print(f"NHTSA matched rows: {nhtsa_matches:,} ({nhtsa_matches / len(enriched):.1%})")


if __name__ == "__main__":
    main()
