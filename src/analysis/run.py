"""`make analysis`, part 1: run every analysis step in order. Never reads the hidden truth file."""
STEPS = []  # filled in as P2 steps land: (name, callable)


def main() -> None:
    for name, step in STEPS:
        print(f"analysis: {name}")
        step()


if __name__ == "__main__":
    main()
