import argparse
from .server import app


def main():
    parser = argparse.ArgumentParser(
        description=""
    )
    parser.parse_args()
    app.run()


if __name__ == "__main__":
    main()
