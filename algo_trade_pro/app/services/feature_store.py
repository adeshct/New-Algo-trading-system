import pandas as pd
import os
from threading import Lock
from typing import Any, List, Optional, Dict

class FeatureStore:
    """
    Utility for logging and loading trading signal features and labels,
    e.g. for meta-labeling CPR ML training.
    Features and labels are stored as serialized lists and columns.

    Usage:
        FeatureStore.append("cpr_meta_signals", feature_dict, label=1)
        FeatureStore.load_all("cpr_meta_signals")
        FeatureStore.update_label("cpr_meta_signals", features, label)
    """
    # You can switch to Parquet for faster, larger-scale ops
    BASEDIR = "./feature_store/"
    SUFFIX = ".csv"
    _lock = Lock()

    @classmethod
    def _file_path(cls, name: str) -> str:
        os.makedirs(cls.BASEDIR, exist_ok=True)
        return os.path.join(cls.BASEDIR, f"{name}{cls.SUFFIX}")

    @classmethod
    def append(cls, name: str, feat: Dict[str, Any], label: Optional[int] = None):
        """
        Appends a new feature observation (with optional label) to the store.
        Fields must all be JSON/pickle serializable.
        """
        entry = feat.copy()
        if label is not None:
            entry["label"] = label
        with cls._lock:
            file_path = cls._file_path(name)
            df = pd.DataFrame([entry])
            header = not os.path.isfile(file_path)
            df.to_csv(file_path, mode="a", header=header, index=False)

    @classmethod
    def load_all(cls, name: str) -> List[Dict[str, Any]]:
        """
        Loads all rows from the feature store for this dataset.
        """
        file_path = cls._file_path(name)
        if not os.path.isfile(file_path):
            return []
        df = pd.read_csv(file_path)
        # Convert stringified lists back to Python list objects for "features", if necessary
        import ast
        if "features" in df.columns:
            df["features"] = df["features"].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)
        return df.to_dict("records")

    @classmethod
    def update_label(cls, name: str, features: List[float], new_label: int, tol: float = 1e-8):
        """
        Finds the row (by features -- exact or nearly-equal match) and sets its label.
        """
        file_path = cls._file_path(name)
        if not os.path.isfile(file_path):
            return
        # Use ast.literal_eval to parse feature lists from str
        df = pd.read_csv(file_path)
        import ast
        if "features" in df.columns:
            df["features"] = df["features"].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)
            # Find the first row with features nearly equal
            idx = -1
            for i, row in enumerate(df["features"]):
                # Compare feature lists elementwise with tolerance
                try:
                    if len(row) == len(features) and all(abs(a - b) < tol for a, b in zip(row, features)):
                        idx = i
                        break
                except Exception:
                    continue
            if idx >= 0:
                df.at[idx, "label"] = new_label
                with cls._lock:
                    df.to_csv(file_path, index=False)

    @classmethod
    def sync_to_parquet(cls, name: str):
        """
        (Optional) Sync CSV to Parquet for faster loading if needed.
        """
        file_path = cls._file_path(name)
        pq_path = file_path.replace(".csv", ".parquet")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            df.to_parquet(pq_path, index=False)

    @classmethod
    def clear_store(cls, name: str):
        """
        Utility: Wipe a feature store (for dev/backtest reset).
        """
        file_path = cls._file_path(name)
        if os.path.exists(file_path):
            os.remove(file_path)
