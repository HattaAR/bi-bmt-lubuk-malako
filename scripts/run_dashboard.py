"""Run the real dashboard; use --dev when editing Python sources."""
import argparse
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def command_args(*,port=8501,development=False):
    if type(port) is not int or not 1<=port<=65535:raise ValueError('Port must be between 1 and 65535.')
    return ['streamlit','run',str(ROOT/'app.py'),'--server.port',str(port),
            '--server.fileWatcherType','auto' if development else 'none',
            '--server.runOnSave','true' if development else 'false']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8501)
    parser.add_argument('--dev',action='store_true',help='Watch source changes and rerun after edits.')
    args=parser.parse_args()
    # Streamlit resolves project configuration and static assets from cwd.
    os.chdir(ROOT)
    from streamlit.web import cli
    print('Development mode: source watching enabled.' if args.dev else
          'Runtime mode: source watching disabled; restart after editing code.')
    sys.argv=command_args(port=args.port,development=args.dev)
    cli.main()


if __name__=='__main__':main()
