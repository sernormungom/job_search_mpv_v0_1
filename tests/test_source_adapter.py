import uuid

from job_search_mvp import source_adapter
from job_search_mvp.paths import OUTPUTS_DIR


def test_local_folder_collection_deduplicates_by_normalized_source_url():
    work_dir = OUTPUTS_DIR / "pytest_work" / "source_adapter" / uuid.uuid4().hex
    incoming = work_dir / "incoming"
    out_dir = work_dir / "collected"
    incoming.mkdir(parents=True, exist_ok=True)
    incoming.joinpath("first.txt").write_text(
        "Source URL: https://example.com/jobs/123?utm_source=newsletter\n\n"
        "Senior Embedded Developer\nC++ and AUTOSAR role in Gothenburg.\n",
        encoding="utf-8",
    )
    incoming.joinpath("second.txt").write_text(
        "Source URL: https://example.com/jobs/123\n\n"
        "Senior Embedded Developer\nSame posting copied again.\n",
        encoding="utf-8",
    )

    config = {
        "sources": [
            {
                "id": "copied",
                "type": "local_folder",
                "enabled": True,
                "path": "incoming",
                "file_glob": "*.txt",
            }
        ]
    }

    rows = source_adapter.collect_jobs(config, work_dir, out_dir)

    assert [row["status"] for row in rows] == ["collected", "duplicate"]
    assert rows[0]["job_id"] == rows[1]["job_id"]
    assert rows[1]["duplicate_of"] == f"{rows[0]['job_id']}.txt"
    output_file = out_dir / f"{rows[0]['job_id']}.txt"
    assert output_file.exists()
    assert "Collected From: copied" in output_file.read_text(encoding="utf-8")
