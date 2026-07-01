import os

from dotenv import load_dotenv

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_script_dir)
load_dotenv(os.path.join(_root_dir, ".env"))

def main():
    while True:
        print("Hello I am running")
        input()

if __name__ == '__main__':
    main()