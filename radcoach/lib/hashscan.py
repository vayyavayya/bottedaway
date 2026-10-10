import json,sys
d=json.load(open(sys.argv[1]))["content"]; print(d["title"],d["revisionId"])
for t in d["tabs"]:
  P=[el for el in t["documentTab"]["body"]["content"] if "paragraph" in el]
  tx=lambda el:"".join(r.get("textRun",{}).get("content","") for r in el["paragraph"]["elements"])
  for i,el in enumerate(P):
    s=tx(el).strip()
    if "#" in s and not s.lower().startswith(("answer","update","verdict","correction","note from")):
      near=[tx(x).strip().lower() for x in P[i+1:i+4]]
      ok=any(n.startswith("answer") for n in near)
      print(("ANSWERED " if ok else "OPEN     ")+t["tabProperties"]["title"],el["startIndex"],s[s.index("#"):][:200])
