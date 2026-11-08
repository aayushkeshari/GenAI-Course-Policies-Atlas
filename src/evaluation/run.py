"""`make analysis`, part 2: score the analysis against the truth (ANL-03, ANL-04)."""
STEPS = []  # filled in as P2 steps land: (name, callable)


def main() -> None:
    for name, step in STEPS:
        print(f"evaluation: {name}")
        step()


if __name__ == "__main__":
    main()
