"""Tests for scripts/check_changelog.py: marker parsing, missing commits, unreleased commits and self-describing commits."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_changelog import check
H=['a'*40,'b'*40,'c'*40]
class ChangelogTests(unittest.TestCase):
    def test_complete_notes_have_nothing_missing_or_unreleased(self):
        self.assertEqual(check('Covers history up to `ccccccc`. aaaaaaa bbbbbbb ccccccc',H),([],[]))
    def test_a_covered_commit_that_is_not_listed_is_reported(self):
        self.assertEqual(check('Covers history up to `ccccccc`. aaaaaaa ccccccc',H),(['b'*40],[]))
    def test_commits_after_the_marker_are_unreleased_not_missing(self):
        self.assertEqual(check('Covers history up to `bbbbbbb`. aaaaaaa bbbbbbb',H),([],['c'*40]))
    def test_a_commit_that_changed_the_notes_carries_its_own_notes(self):
        self.assertEqual(check('Covers history up to `bbbbbbb`. aaaaaaa bbbbbbb',H,{'c'*40}),([],[]))
    def test_a_missing_or_unknown_marker_is_an_error(self):
        with self.assertRaises(ValueError):check('no marker aaaaaaa',H)
        with self.assertRaises(ValueError):check('Covers history up to `ddddddd`.',H)
if __name__=='__main__':unittest.main()
