"""Print the browser review manifest field catalog."""

import argparse

from _common import print_json

from kara_previwer.proposals import CATALOG

if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    print_json(CATALOG)
