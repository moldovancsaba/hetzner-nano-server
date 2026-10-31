#!/usr/bin/env python3
"""Prove that edited Python files differ from git HEAD only in comments and docstrings.

Usage: python3 scripts/check_comment_only.py [file ...]   (default: every changed tracked .py file)
Module, class and function docstrings are stripped before the syntax trees are compared, so adding or rewording a
docstring or comment passes and any change to executable code fails. Exit status is 1 when a file differs.
"""
import ast,os,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
def strip(tree):
 for node in ast.walk(tree):
  if isinstance(node,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
   body=node.body
   if body and isinstance(body[0],ast.Expr) and isinstance(getattr(body[0],'value',None),ast.Constant) and isinstance(body[0].value.value,str):
    node.body=body[1:] or [ast.Pass()]
 return tree
def dump(source):return ast.dump(strip(ast.parse(source)))
def main(files):
 files=files or [f for f in subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).split() if f.endswith('.py')]
 differ=0
 for name in files:
  new=(ROOT/name).read_text(encoding='utf8')
  try:old=subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT,text=True)
  except subprocess.CalledProcessError:print('new   ',name);continue
  same=dump(old)==dump(new);differ+=0 if same else 1;print('same  ' if same else 'DIFFER',name)
 return 1 if differ else 0
if __name__=='__main__':sys.exit(main(sys.argv[1:]))
