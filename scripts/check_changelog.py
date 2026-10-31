#!/usr/bin/env python3
"""List commits that are not yet in CHANGELOG.md.

CHANGELOG.md carries a marker line "Covers history up to `<hash>`". Every commit up to and including that
marker must appear in the file by its short hash; commits after the marker are reported as unreleased, except
commits that change CHANGELOG.md themselves: a commit cannot link its own hash, so it carries its own notes and
is linked when a later marker moves past it.
Exit status is 1 when a covered commit is missing, or, with --strict, when any commit is unreleased.
"""
import argparse,pathlib,re,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
MARKER=re.compile(r'Covers history up to `([0-9a-f]{7,40})`')
def check(text,commits,own_notes=frozenset()):
 """commits: full hashes, oldest first; own_notes: hashes of commits that changed CHANGELOG.md.
 Returns (missing, unreleased); raises ValueError without a usable marker."""
 found=MARKER.search(text)
 if not found:raise ValueError('CHANGELOG.md has no "Covers history up to `<hash>`" line')
 marker=found.group(1);index=next((i for i,h in enumerate(commits) if h.startswith(marker)),None)
 if index is None:raise ValueError('The marker commit '+marker+' is not in this history')
 covered,later=commits[:index+1],commits[index+1:]
 return [h for h in covered if h[:7] not in text],[h for h in later if h not in own_notes]
def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__.split('\n')[0]);parser.add_argument('--strict',action='store_true',help='also fail when commits after the marker are unreleased')
 args=parser.parse_args(argv)
 commits=subprocess.check_output(['git','rev-list','--reverse','HEAD'],cwd=ROOT,text=True).split()
 own=set(subprocess.check_output(['git','log','--format=%H','--','CHANGELOG.md'],cwd=ROOT,text=True).split())
 try:missing,unreleased=check((ROOT/'CHANGELOG.md').read_text(encoding='utf8'),commits,own)
 except ValueError as error:print('error:',error);return 1
 for h in missing:print('missing from CHANGELOG.md:',subprocess.check_output(['git','log','-1','--format=%h %s',h],cwd=ROOT,text=True).strip())
 if unreleased:print(len(unreleased),'commit(s) after the marker are not yet in the release notes (add them, then move the marker)')
 if not missing and not unreleased:print('CHANGELOG.md covers every commit')
 return 1 if missing or (args.strict and unreleased) else 0
if __name__=='__main__':sys.exit(main())
