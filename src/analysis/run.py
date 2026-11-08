"""`make analysis`, part 1: run every analysis step in order. Never reads the hidden truth file."""
from src.analysis import clean, code_text, descriptives, inference

STEPS = [  # (name, callable), in order
    ("ANL-01 clean", clean.main),
    ("ANL-02 code statement text", code_text.main),
    ("ANL-05/11/12 descriptives with cluster-bootstrap CIs", descriptives.main),
    ("ANL-06/07/14 association and clustered ordinal regression", inference.main),
]


def main() -> None:
    for name, step in STEPS:
        print(f"analysis: {name}")
        step([])


if __name__ == "__main__":
    main()
