"""Support running vastai as a module: python -m vastai"""

from vast import main

if __name__ == "__main__":
    main()  # type: ignore[no-untyped-call]
