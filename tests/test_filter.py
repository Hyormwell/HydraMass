import pandas as pd
from pathlib import Path
from hydra_reposter.workers.filter import validate_csv


def test_validate_csv(tmp_path: Path):
    data = {
        "username": ["alice", " ", "bob", "alice", "", None],
        "extra": [1, 2, 3, 4, 5, 6],
    }
    csv_file = tmp_path / "targets.csv"
    pd.DataFrame(data).to_csv(csv_file, index=False)

    validate_csv(csv_file)

    df = pd.read_csv(csv_file)
    # остаются уникальные и непустые
    assert set(df["username"]) == {"alice", "bob"}