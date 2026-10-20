"""Prompt locally for OPS credentials; keep them only in this process."""
from getpass import getpass
import os
from pathlib import Path
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    __package__='scripts'

from .build_references import parser, run


def main():
    args=parser().parse_args()
    args.original_method='ops'
    previous={key:os.environ.get(key) for key in ('EPO_OPS_KEY','EPO_OPS_SECRET')}
    try:
        for key,label in (('EPO_OPS_KEY','OPS Consumer Key'),('EPO_OPS_SECRET','OPS Consumer Secret')):
            if not os.environ.get(key):
                os.environ[key]=getpass(label+' (hidden, this run only): ')
        return run(args)
    finally:
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value


if __name__=='__main__':
    try:
        sys.exit(main())
    except (ValueError,OSError) as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(2)
