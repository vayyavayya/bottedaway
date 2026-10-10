import json,sys,hashlib,os
F=sys.argv[1]; ST="loop/caseck.json"
d=json.load(open(F))["content"]
st=json.load(open(ST)) if os.path.exists(ST) else {}
t=[t for t in d["tabs"] if t["tabProperties"]["tabId"]=="t.0"][0]
P=[el for el in t["documentTab"]["body"]["content"] if "paragraph" in el]
tx=lambda el:"".join(r.get("textRun",{}).get("content","") for r in el["paragraph"]["elements"])
imgs=lambda el:sum(1 for r in el["paragraph"]["elements"] if "inlineObjectElement" in r)
heads=[i for i,el in enumerate(P) if el["paragraph"]["paragraphStyle"].get("namedStyleType","").startswith("HEADING") and tx(el).startswith("Case ")]
out=[]
for h in heads:
  end=next((j for j in heads if j>h),len(P))
  blk=P[h:end]; T=[tx(e) for e in blk]
  try:
    mb=T.index("My Befund:\n"); sr=next(i for i,s in enumerate(T) if s.startswith("Signed report")); co=T.index("Correction:\n")
  except Exception: continue
  bef="".join(T[mb+1:sr]).strip()
  ph="(filled in automatically" in "".join(T[co+1:co+3])
  nimg=sum(imgs(e) for e in blk)
  if not ph: continue
  if not bef or bef.startswith("(write your Befund"): continue
  key=T[0].strip(); hsh=hashlib.md5(("".join(T[:co])).encode()).hexdigest()
  prev=st.get(key,{}); stable=prev.get("h")==hsh
  st[key]={"h":hsh,"n":prev.get("n",0)+1 if stable else 0}
  out.append(f"PENDING {key} imgs={nimg} stable_checks={st[key]['n']} start={blk[0]['startIndex']}")
for i,el in enumerate(P):
  s=tx(el).strip()
  if "#" in s and not s.lower().startswith(("answer","update","verdict","correction")):
    h=s[s.index("#"):][:80]
    near=[tx(x).strip().lower() for x in P[i+1:i+4]]
    if h in st.get("_ign_t",[]) or any(n.startswith(("answer","correction")) for n in near) or any(tx(x).strip().lower().startswith(("answer","correction")) for x in P[i+1:i+12]): continue
    out.append(f"HASH? {el['startIndex']} {h}")
json.dump(st,open(ST,"w"))
print(d["revisionId"]); print("\n".join(out) if out else "nothing pending")
