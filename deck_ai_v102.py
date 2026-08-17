# -*- coding: utf-8 -*-
"""Lokaler sammlungsbasierter KI-Deckbauer für Just InCard v12.0.1."""
from __future__ import annotations
import re, unicodedata
from collections import Counter
from typing import Any, Dict, Iterable, List, Tuple

def norm(v):
 s=unicodedata.normalize("NFKD",str(v or "")).casefold(); s="".join(c for c in s if not unicodedata.combining(c)); return re.sub(r"[^a-z0-9]+"," ",s).strip()

def zone(card):
 t=str(card.get("type") or "").lower(); return "extra" if any(x in t for x in ("fusion","synchro","xyz","link")) else "main"

def family(card):
 t=str(card.get("type") or "").lower()
 if "spell" in t:return "spell"
 if "trap" in t:return "trap"
 if "link" in t:return "link"
 if "xyz" in t:return "xyz"
 if "synchro" in t:return "synchro"
 if "fusion" in t:return "fusion"
 if "ritual" in t:return "ritual"
 if "pendulum" in t:return "pendulum"
 return "monster"

def tags(card):
 values=[card.get("archetype"),card.get("race"),card.get("attribute"),family(card)]
 desc=norm(card.get("desc"));
 for w in ("draw","search","add","special summon","negate","destroy","banish","graveyard","friedhof","beschworen","zerstore","verbanne","hand"):
  if norm(w) in desc: values.append("fx:"+norm(w))
 lvl=card.get("level") or card.get("rank") or card.get("linkval")
 if lvl is not None: values.append("level:"+str(lvl))
 return {norm(v) for v in values if v}

def synergy(a,b):
 ta,tb=tags(a),tags(b); score=len((ta&tb)-{"monster","spell","trap"})*1.7
 aa=norm(a.get("archetype")); ab=norm(b.get("archetype")); da=norm(a.get("desc")); db=norm(b.get("desc"))
 if aa and aa==ab: score+=6
 if aa and aa in db: score+=3
 if ab and ab in da: score+=3
 fa,fb=family(a),family(b)
 if {fa,fb}=={"synchro","monster"} and ("tuner" in norm(a.get("type")) or "tuner" in norm(b.get("type"))): score+=2
 if fa=="xyz" or fb=="xyz":
  if a.get("level") and a.get("level")==b.get("level"): score+=1.5
 if fa=="pendulum" and fb=="pendulum": score+=1.5
 return score

def utility(card):
 d=norm(card.get("desc")); s=0
 for key,val in (("add",2),("search",2),("draw",2),("special summon",2),("negate",2.2),("destroy",1.4),("banish",1.7),("friedhof",1.1),("graveyard",1.1)):
  if key in d:s+=val
 if card.get("archetype"):s+=.8
 return s

def build_deck_suggestions(collection:Dict[str,Dict[str,Any]],max_suggestions:int=3)->List[Dict[str,Any]]:
 rows=[]
 for key,item in (collection or {}).items():
  c=item.get("card") or {}; n=max(0,int(item.get("count") or 0))
  if n: rows.append((str(key),c,min(3,n)))
 main=[r for r in rows if zone(r[1])=="main"]; extra=[r for r in rows if zone(r[1])=="extra"]
 if sum(n for _,_,n in main)<40:return []
 arcs=Counter(norm(c.get("archetype")) for _,c,n in main for _ in range(n) if c.get("archetype"))
 cores=[a for a,_ in arcs.most_common(max_suggestions)] or ["generic"]
 results=[]
 for core in cores:
  core_cards=[c for _,c,_ in main if core=="generic" or norm(c.get("archetype"))==core]
  def sc(row):
   _,c,n=row; base=utility(c)+(.0 if core=="generic" else (8 if norm(c.get("archetype"))==core else 0))
   if core_cards: base+=sum(synergy(c,x) for x in core_cards[:12])/max(1,min(12,len(core_cards)))
   return base
  ranked=sorted(main,key=sc,reverse=True); chosen=[]; total=0
  fam_counts=Counter()
  for key,c,owned in ranked:
   if total>=40:break
   f=family(c); desired=3 if sc((key,c,owned))>=7 else 2 if sc((key,c,owned))>=4 else 1
   take=min(owned,desired,40-total)
   if take<=0:continue
   chosen.append({"collection_key":key,"count":take,"card":c,"zone":"main","synergy_score":round(sc((key,c,owned)),2)}); total+=take; fam_counts[f]+=take
  if total<40:
   used={x["collection_key"] for x in chosen}
   for key,c,owned in ranked:
    if total>=40:break
    have=next((x["count"] for x in chosen if x["collection_key"]==key),0); add=min(owned-have,40-total)
    if add>0:
     found=next((x for x in chosen if x["collection_key"]==key),None)
     if found: found["count"]+=add
     else: chosen.append({"collection_key":key,"count":add,"card":c,"zone":"main","synergy_score":round(sc((key,c,owned)),2)})
     total+=add
  rel=[]
  for key,c,owned in extra:
   score=utility(c)+(6 if core!="generic" and norm(c.get("archetype"))==core else 0)+sum(synergy(c,x) for x in core_cards[:10])/max(1,min(10,len(core_cards)))
   rel.append((score,key,c,owned))
  for score,key,c,owned in sorted(rel,reverse=True)[:15]: chosen.append({"collection_key":key,"count":min(owned,1),"card":c,"zone":"extra","synergy_score":round(score,2)})
  side=[]
  selected={x["collection_key"] for x in chosen}
  for key,c,owned in ranked:
   if key in selected:continue
   d=norm(c.get("desc"))
   if any(w in d for w in ("negate","destroy","banish","zerstore","verbanne")): side.append({"collection_key":key,"count":min(owned,2),"card":c,"zone":"side"})
   if sum(x["count"] for x in side)>=15:break
  chosen.extend(side)
  name=(core.title()+" KI-Deck") if core!="generic" else "Synergie KI-Deck"
  score=sum(float(x.get("synergy_score") or 0)*x["count"] for x in chosen if x["zone"]!="side")/max(1,sum(x["count"] for x in chosen if x["zone"]!="side"))
  results.append({"name":name,"cards":chosen,"score":round(score,2),"strategy":f"Lokaler Synergie-Kern: {core}. Main Deck 40, Extra Deck bis 15, Side Deck bis 15.","stats":{"main":sum(x["count"] for x in chosen if x["zone"]=="main"),"extra":sum(x["count"] for x in chosen if x["zone"]=="extra"),"side":sum(x["count"] for x in chosen if x["zone"]=="side")}})
 return sorted(results,key=lambda x:x["score"],reverse=True)
