"""Convert the pinned Hungarian vocabulary-trimmed model with a verified tokenizer mapping.
Use an isolated environment; no trust_remote_code or model-provided Python executes.
"""
import hashlib,json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[3]
converter=pathlib.Path('/tmp/hetzner-hu-llama')
model=ROOT/'private/hungarian-evaluation/qwen35-trimmed'
original=json.loads((ROOT/'private/hungarian-evaluation/qwen35-original-tokenizer.json').read_text())
trimmed=json.loads((model/'tokenizer.json').read_text())
for field in ['pre_tokenizer','normalizer','decoder','post_processor']:
 assert original[field]==trimmed[field],f'Tokenizer pipeline changed: {field}'
assert max(list(trimmed['model']['vocab'].values())+[x['id'] for x in trimmed['added_tokens']])+1==16384
assert subprocess.check_output(['git','-C',str(converter),'rev-parse','HEAD'],text=True).strip()=='5d7793d6fcce4eb4b11ab5be856dfa4e4c8fde9b'
# Converter's fingerprint hashes output token IDs, so vocabulary reindexing changes
# it even though the verified Qwen3.5 pre-tokenization pipeline is identical.
p=converter/'conversion/base.py';s=p.read_text();needle='        if res is None:\n'
patch='        if chkhsh == "2f8827421645eb436790192528ce3f02739b146fca570f814c1326416c5f4e12":\n            res = "qwen35"  # Verified identical pre-tokenizer, Hungarian vocabulary reindexed.\n'
if patch not in s:
 assert s.count(needle)==1;s=s.replace(needle,patch+needle);p.write_text(s)
out=ROOT/'private/hungarian-evaluation/qwen35-hu-q8.gguf'
subprocess.run([sys.executable,str(converter/'convert_hf_to_gguf.py'),str(model),'--outtype','q8_0','--outfile',str(out)],check=True)
audit={'model':'alphaedge-ai/Qwen3.5-0.8B-hun-16384','revision':'4cb74afbb6a731b51e8a18f6bd04e21d9bb712bc','converter_revision':'5d7793d6fcce4eb4b11ab5be856dfa4e4c8fde9b','verified_pipeline_fields':['pre_tokenizer','normalizer','decoder','post_processor'],'trimmed_tokenizer_sha256':hashlib.sha256((model/'tokenizer.json').read_bytes()).hexdigest(),'converter_patch_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'gguf_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'gguf_bytes':out.stat().st_size,'license':'Apache-2.0 upstream; source metadata retained','initial_conversion_issue':'Vocabulary-reindexed tokenizer fingerprint unrecognized; validated identical pipeline before adding exact fingerprint.'}
pathlib.Path(__file__).with_name('conversion.json').write_text(json.dumps(audit,indent=2)+'\n')
