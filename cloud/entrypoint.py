"""Docker entrypoint dispatcher.

Reads the PIPELINE_STEP env var and runs the corresponding step.
Valid values: fetch, classify, extract, backfill, all
"""

import os
import sys


def main():
    step = os.environ.get("PIPELINE_STEP", "all")

    if step == "fetch":
        from run_fetch import main as run
    elif step == "classify":
        from run_classify import main as run
    elif step == "classify_batch":
        from run_classify_batch import main as run
    elif step == "extract":
        from run_extract import main as run
    elif step == "backfill":
        from run_backfill import main as run
    elif step == "qa":
        from run_qa import main as run
    elif step == "backup":
        from run_backup import main as run
    elif step == "all":
        from main import main as run
    else:
        print(f"ERROR: Unknown PIPELINE_STEP: {step}")
        print("Valid values: fetch, classify, classify_batch, extract, backfill, qa, all")
        sys.exit(1)

    run()


if __name__ == "__main__":
    main()
