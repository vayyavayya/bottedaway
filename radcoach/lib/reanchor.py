# usage: reanchor.py read.json spec.json out.json "anchor text prefix"  -> inserts at start of paragraph AFTER the anchor paragraph
import json,sys,subprocess
F,S,O,A=sys.argv[1:5]
d=json.load(open(F))["content"]; rev=d["revisionId"]
sp=json.load(open(S)); tab=sp["tab"]
t=[t for t in d["tabs"] if t["tabProperties"]["tabId"]==tab][0]
P=[el for el in t["documentTab"]["body"]["content"] if "paragraph" in el]
tx=lambda el:"".join(r.get("textRun",{}).get("content","") for r in el["paragraph"]["elements"])
i=[k for k,e in enumerate(P) if tx(e).strip().startswith(A)][0]
sp["at"]=P[i+1]["startIndex"]; sp["rev"]=rev
json.dump(sp,open(S,"w"),ensure_ascii=False)
subprocess.run(["python3","scripts/build2.py",S,O],check=True)
print("at",sp["at"],"next para:",repr(tx(P[i+1])[:40]))
