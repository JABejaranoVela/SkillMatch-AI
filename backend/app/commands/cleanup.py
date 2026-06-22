import argparse
import json

from app.db.session import SessionLocal
from app.services.maintenance.cleanup import cleanup_temporary_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clean expired authentication and email operational data."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show matching row counts without modifying the database.",
    )
    parser.add_argument("--session-retention-days", type=_positive_int)
    parser.add_argument("--token-retention-days", type=_positive_int)
    parser.add_argument("--outbox-retention-days", type=_positive_int)
    parser.add_argument(
        "--resume-processing-timeout-minutes",
        type=_positive_int,
        default=60,
        help=(
            "Mark resumes stuck in processing older than this timeout as failed. "
            "No files are deleted."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    with SessionLocal() as db:
        result = cleanup_temporary_data(
            db,
            dry_run=args.dry_run,
            session_retention_days=args.session_retention_days,
            token_retention_days=args.token_retention_days,
            outbox_retention_days=args.outbox_retention_days,
            resume_processing_timeout_minutes=args.resume_processing_timeout_minutes,
        )
    print(json.dumps(result.to_dict(), sort_keys=True))


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("retention days must be at least 1")
    return parsed


if __name__ == "__main__":
    main()
