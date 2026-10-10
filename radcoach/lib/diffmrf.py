import json,sys,difflib
a=json.load(open(sys.argv[1]))["content"]; b=json.load(open(sys.argv[2]))["content"]
def texts(d):
  out={}
  for t in d["tabs"]:
    out[t["tabProperties"]["title"]]=["".join(r.get("textRun",{}).get("content","") if "textRun" in r else "[IMG]" for r in el["paragraph"]["elements"]) for el in t["documentTab"]["body"]["content"] if "paragraph" in el]
  return out
A,B=texts(a),texts(b)
for k in A:
  for l in difflib.unified_diff(B.get(k,[]),A[k],lineterm="",n=0):
    if l.startswith(("+","-")) and not l.startswith(("+++","---")): print(k,l[:250].replace("\n","⏎"))
