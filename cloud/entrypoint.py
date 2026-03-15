"""Docker entrypoint dispatcher.

Reads the PIPELINE_STEP env var and runs the corresponding step.
Valid values: fetch, classify, extract, all
"""

import os
import sys


def main():
    step = os.environ.get("PIPELINE_STEP", "all")

    if step == "fetch":
        from run_fetch import main as run
    elif step == "classify":
        from run_classify import main as run
    elif step == "extract":
        from run_extract import main as run
    elif step == "all":
        from main import main as run
    else:
        print(f"ERROR: Unknown PIPELINE_STEP: {step}")
        print("Valid values: fetch, classify, extract, all")
        sys.exit(1)

    run()


if __name__ == "__main__":
    main()
