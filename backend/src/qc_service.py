import random
from math import ceil
from sqlalchemy import select
from .models import Entrance,Alias,Evidence,Candidate,MatchRun,QcRound,QcPair,QcVote
from .common import *
from .matching import pair_scores
def create_round(s,d):
 r=lock(s)
 run=s.scalars(select(MatchRun).where(MatchRun.state=='ready').order_by(MatchRun.id.desc())).first()
 if not run:fail('需先完成一次别名匹配计算，才能冻结抽查框架')
 es=rows(s,Entrance)
 frame=[(x,y) for i,x in enumerate(es) for y in es[i+1:] if x.street==y.street and x.number==y.number]
 if not frame:fail('没有同街同号的入口对，无法抽查')
 rec={frozenset((c.source_id,c.target_id)):c.similarity for c in rows(s,Candidate) if c.run_id==run.id and not c.conflict}
 scores=pair_scores([dump(x) for x in es],[dump(x) for x in rows(s,Alias)])
 strata={}
 for x,y in frame:strata.setdefault((x.street,frozenset((x.id,y.id)) in rec),[]).append((x,y))
 rnd=random.Random(d['seed']);q=QcRound(code=d['code'],run_id=run.id,seed=d['seed'],fraction=d['fraction'],created=r.now,frame={});s.add(q);s.flush()
 snapshot={}
 for (street,flag),items in sorted(strata.items(),key=lambda z:(z[0][0],z[0][1])):
  items.sort(key=lambda t:(t[0].id,t[1].id));total=len(items);n=min(total,max(1,ceil(total*d['fraction'])))
  chosen=rnd.sample(items,n) if n<total else list(items)
  snapshot.setdefault(street,{})['recommended' if flag else 'unrecommended']={'population':total,'sampled':n}
  for x,y in chosen:
   key=frozenset((x.id,y.id));sim=rec.get(key,scores.get((min(x.id,y.id),max(x.id,y.id)),0.0))
   s.add(QcPair(round_id=q.id,street=street,number=x.number,source_id=x.id,target_id=y.id,recommended=int(flag),similarity=round(sim,6),weight=total/n))
 q.frame=snapshot
 return q
def vote(s,pair_id,d,u):
 r=lock(s);p=get(s,QcPair,pair_id);q=get(s,QcRound,p.round_id)
 if q.state!='collecting':fail('抽查批次已封存，不再接收判定')
 if p.state=='decided':fail('该门牌对已完成核定')
 votes=[v for v in rows(s,QcVote) if v.pair_id==p.id]
 mine=[v for v in votes if v.adjudicator==u['email']]
 if mine:
  if mine[0].verdict==d['verdict']:return mine[0]
  fail('同一核定员已提交过不同判定，不可重复计票')
 v=QcVote(pair_id=p.id,adjudicator=u['email'],verdict=d['verdict'],note=d['note'],created=r.now);s.add(v);s.flush();votes.append(v)
 if p.state=='pending' and len(votes)==2:
  if votes[0].verdict==votes[1].verdict:p.state='decided';p.verdict=votes[0].verdict
  else:p.state='arbitration'
 elif p.state=='arbitration':p.state='decided';p.verdict=d['verdict']
 return v
def close(s,round_id):
 lock(s);q=get(s,QcRound,round_id)
 if q.state!='collecting':fail('抽查批次已封存')
 q.state='closed';return q
def pair_json(p,entrances,aliases,evidence,votes):
 def side(eid):
  e=entrances[eid]
  return {'id':e.id,'code':e.code,'street':e.street,'number':e.number,'label':e.label,'lat':e.lat,'lng':e.lng,'aliases':[{'id':a.id,'text':a.text,'evidence':[{'reference':v.reference,'description':v.description} for v in evidence if v.alias_id==a.id]} for a in aliases if a.entrance_id==eid]}
 d={'id':p.id,'street':p.street,'number':p.number,'state':p.state,'source':side(p.source_id),'target':side(p.target_id),'vote_count':len(votes)}
 if p.state!='pending':
  d.update({'verdict':p.verdict,'recommended':p.recommended,'similarity':p.similarity,'weight':p.weight,'votes':[{'adjudicator':v.adjudicator,'verdict':v.verdict,'note':v.note,'created':v.created} for v in votes]})
 return d
def progress(pairs):
 def count(flag):
  sel=[p for p in pairs if p.recommended==flag]
  return {'sampled':len(sel),'decided':sum(p.state=='decided' for p in sel),'arbitration':sum(p.state=='arbitration' for p in sel),'pending':sum(p.state=='pending' for p in sel)}
 return {'recommended':count(1),'unrecommended':count(0)}
def estimates(q,pairs):
 def est(flag,error_verdict):
  sel=[p for p in pairs if p.recommended==flag];decided=[p for p in sel if p.state=='decided'];errors=[p for p in decided if p.verdict==error_verdict]
  wsum=sum(p.weight for p in decided);werr=sum(p.weight for p in errors)
  group='recommended' if flag else 'unrecommended'
  return {'population':sum(q.frame[street].get(group,{}).get('population',0) for street in q.frame),'sampled':len(sel),'decided':len(decided),'unfinished':len(sel)-len(decided),'error_pairs':len(errors),'weighted_errors':round(werr,6),'rate':round(werr/wsum,6) if wsum else None}
 return {'wrong_merge':est(1,'different'),'missed_merge':est(0,'same')}
def report(s):
 entrances={x.id:x for x in rows(s,Entrance)};aliases=rows(s,Alias);evidence=rows(s,Evidence)
 votes={}
 for v in rows(s,QcVote):votes.setdefault(v.pair_id,[]).append(v)
 out=[]
 for q in rows(s,QcRound):
  pairs=[p for p in rows(s,QcPair) if p.round_id==q.id]
  out.append({**dump(q),'pairs':[pair_json(p,entrances,aliases,evidence,votes.get(p.id,[])) for p in pairs],'progress':progress(pairs),'estimates':estimates(q,pairs)})
 return {'rounds':out}
