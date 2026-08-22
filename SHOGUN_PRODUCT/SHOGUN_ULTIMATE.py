#!/usr/bin/env python3
import pathlib, os, sys, subprocess, argparse, json, time, base64
from collections import Counter
HOME=pathlib.Path.home()
POSSIBLE=["SHOGUN","AEGIS","EMPIRE","Empire","deep_recon","shogun","aegis","AEGIS_CORE","KATANA","BEACON","TOOLS","tools","bin"]
ROOTS=[HOME/d for d in POSSIBLE if (HOME/d).exists()]
if not ROOTS: ROOTS=[HOME]
EXCLUDE=["llama.cpp","whisper.cpp",".git","__pycache__","site-packages","venv",".venv","node_modules",".cargo",".ollama"]
def ok(p):
 s=str(p).lower()
 if any(x in s for x in EXCLUDE): return False
 try:
  sz=p.stat().st_size
  if sz==0 or sz>12*1024*1024: return False
 except: return False
 return True
def discover():
 files=[]
 for root in ROOTS:
  for p in root.rglob("*"):
   if not p.is_file(): continue
   if not ok(p): continue
   name=p.name.lower()
   if p.suffix in [".py",".sh",".bash",""] or any(k in name for k in ["shogun","aegis","empire","katana","beacon","recon","close","core"]):
    files.append(p)
 uniq={}
 for p in files:
  try: uniq[str(p.resolve())]=p
  except: uniq[str(p)]=p
 return sorted(uniq.values())
def catreg(files):
 reg={}
 for p in files:
  name=p.stem.lower() or p.name.lower()
  lname=p.name.lower()
  cat="other"
  for c in ["katana","beacon","aegis","empire","recon","osint","autonomy","close_the_loop","shogun_core","deep_recon"]:
   if c in lname or c in name: cat=c; break
  key=name
  i=1
  while key in reg: key=f"{name}_{i}"; i+=1
  rel=str(p.relative_to(HOME)) if HOME in p.parents else str(p)
  reg[key]={"key":key,"path":str(p),"rel":rel,"name":p.name,"cat":cat,"type":"py" if p.suffix==".py" else "sh" if p.suffix==".sh" else "bin"}
 return reg
def runcap(reg,key,extra=None):
 extra=extra or []
 if key not in reg:
  m=[k for k in reg if key in k or key in reg[k]["name"].lower()]
  if not m: print(f"[!] No {key}"); return 1
  key=m[0]
 meta=reg[key]
 p=pathlib.Path(meta["path"])
 if meta["type"]=="py": cmd=[sys.executable,str(p)]+extra
 elif meta["type"]=="sh": cmd=["bash",str(p)]+extra
 else:
  try:
   head=p.read_text()[:200]
   if "python" in head: cmd=[sys.executable,str(p)]+extra
   elif "bash" in head or "sh" in head: cmd=["bash",str(p)]+extra
   else: os.chmod(p,0o755); cmd=[str(p)]+extra
  except: os.chmod(p,0o755); cmd=[str(p)]+extra
 print(f"[+] {meta['rel']} [{meta['cat']}]")
 return subprocess.call(cmd)
def runcat(reg,cat,t=None,e=None):
 e=e or []
 if t: e=[t]+e
 caps=[k for k,v in reg.items() if v["cat"]==cat or cat in k or cat in v["name"].lower()]
 print(f"[+] {cat}: {len(caps)}")
 for k in caps: runcap(reg,k,e)
def main():
 ap=argparse.ArgumentParser(description="SHOGUN ULTIMATE")
 ap.add_argument("--list",action="store_true")
 ap.add_argument("--run",help="run key")
 ap.add_argument("--cat",help="category")
 ap.add_argument("--recon",help="target")
 ap.add_argument("--osint",help="target")
 ap.add_argument("--autonomy",help="target")
 ap.add_argument("--chain",nargs="*")
 ap.add_argument("--close-loop",action="store_true")
 ap.add_argument("--build-fat",nargs="?",const=str(HOME/"SHOGUN_ULTIMATE_FAT.py"))
 ap.add_argument("--discover",action="store_true")
 args,unk=ap.parse_known_args()
 files=discover()
 reg=catreg(files)
 if args.discover or len(sys.argv)==1:
  print(f"[+] Found {len(files)} files in {ROOTS}")
  print(Counter(v["cat"] for v in reg.values()))
  print(f"Total {len(reg)}")
  if len(sys.argv)==1: ap.print_help()
  return
 if args.list:
  [print(f"{k:35} [{v['cat']:15}] {v['rel']}") for k,v in sorted(reg.items())]
  print(f"\nTotal {len(reg)}"); return
 if args.run: sys.exit(runcap(reg,args.run,unk))
 if args.cat: runcat(reg,args.cat,unk[0] if unk else None, unk[1:] if len(unk)>1 else []); return
 if args.recon: runcat(reg,"recon",args.recon,unk); return
 if args.osint: runcat(reg,"osint",args.osint,unk); return
 if args.autonomy:
  chain=args.chain or ["recon","osint","katana","beacon"]
  print(f"[AEGIS] Target={args.autonomy} Chain={chain}")
  for s in chain: runcat(reg,s,args.autonomy)
  return
 if args.close_loop:
  ctl=[k for k,v in reg.items() if "close_the_loop" in v["name"].lower()]
  if ctl:
   for k in ctl: runcap(reg,k,[])
  return
 if args.build_fat is not None:
  out=pathlib.Path(args.build_fat)
  progs={}
  for k,v in reg.items():
   try:
    p=pathlib.Path(v["path"])
    if p.stat().st_size>5*1024*1024: continue
    progs[k]={"path":v["rel"],"b64":base64.b64encode(p.read_bytes()).decode(),"type":v["type"],"name":v["name"]}
   except Exception as e: print(f"skip {v['rel']}: {e}")
  import json
  with open(out,"w") as f:
   f.write("#!/usr/bin/env python3\nimport base64,pathlib,os,sys,subprocess,json,argparse\nHOME=pathlib.Path.home()\nCACHE=HOME/\".shogun_cache\"\nCACHE.mkdir(exist_ok=True)\nPROGRAMS=")
   f.write(json.dumps(progs))
   f.write("\n")
   f.write("def _get(n):\n m=PROGRAMS[n]; r=base64.b64decode(m['b64']); s='.py' if m['type']=='py' else '.sh' if m['type']=='sh' else '.bin'; t=CACHE/(n+s); t.write_bytes(r); import os; os.chmod(t,0o755) if m['type']!='py' else None; return t,m\n")
   f.write("def run(k,a=None):\n a=a or []; p,m=_get(k); c=[__import__('sys').executable,str(p)]+a if m['type']=='py' else ['bash',str(p)]+a if m['type']=='sh' else [str(p)]+a; print(f\"[+] {m['path']}\"); return __import__('subprocess').call(c)\n")
   f.write("if __name__=='__main__':\n ap=argparse.ArgumentParser(); ap.add_argument('--list',action='store_true'); ap.add_argument('--run'); a,u=ap.parse_known_args();\n if a.list or len(__import__('sys').argv)==1: [print(f\"{k:35} {v['path']}\") for k,v in sorted(PROGRAMS.items())];\n elif a.run: run(a.run,u)\n")
  os.chmod(out,0o755)
  print(f"[OK] FAT {out} {out.stat().st_size/1024/1024:.2f} MB {len(progs)} caps")
  return
if __name__=="__main__": main()
