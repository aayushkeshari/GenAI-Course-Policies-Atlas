"""`make analysis`, part 2: score the analysis against the truth (ANL-03, ANL-04)."""
from src.evaluation import coder_eval, hand_sample

STEPS = [  # (name, callable), in order
    ("ANL-03 held-out coder evaluation", coder_eval.main),
    ("ANL-04 hand-coding sample / kappa", hand_sample.main),
]


def main() -> None:
    for name, step in STEPS:
        print(f"evaluation: {name}")
        step([])


if __name__ == "__main__":
    main()
