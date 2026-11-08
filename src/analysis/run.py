"""`make analysis`, part 1: run every analysis step in order. Never reads the hidden truth file."""
from src.analysis import clean, code_text

STEPS = [  # (name, callable), in order
    ("ANL-01 clean", clean.main),
    ("ANL-02 code statement text", code_text.main),
]


def main() -> None:
    for name, step in STEPS:
        print(f"analysis: {name}")
        step([])


if __name__ == "__main__":
    main()
