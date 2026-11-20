# 归并质检端到端核验：抽样冻结、盲审、并发交卷、裁决、幂等重试、折算估计
# 运行：cd backend && DATABASE_URL=sqlite:////tmp/qc_verify.db python ../test-artifacts/gb-1036/qc_verify.py
import os,sys,json,threading
os.environ.setdefault('DATABASE_URL','sqlite:////tmp/qc_verify.db')
os.environ.setdefault('REDIS_URL','redis://127.0.0.1:6379/9')
os.environ['SEED_DEMO']='false'
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','..','backend'))
DB='/tmp/qc_verify.db'
if os.path.exists(DB):os.remove(DB)
from fastapi.testclient import TestClient
from src.main import app
from src.database import Session
from src.models import Entrance,Alias,Candidate,MatchRun,QcPair,QcVote,User
from src.common import rows,dump
from src.matching import match
from src import qc_service
from scripts.seed_demo import seed
seed()
seed()
client=TestClient(app)
FAIL=[]
def check(name,cond,detail=''):
 print(('PASS' if cond else 'FAIL'),name,detail)
 if not cond:FAIL.append(name)
def login(email):
 r=client.post('/auth/login',json={'email':email,'password':'Address2026!'})
 assert r.status_code==200,(email,r.text)
 return {'Authorization':'Bearer '+r.json()['token']}
H={r:login(r+'@changqiao.local') for r in ['operator','supervisor','supervisor2','supervisor3','viewer']}
def drain():
 with Session() as s:
  run=MatchRun(state='queued');s.add(run);s.flush()
  result=match([dump(x) for x in rows(s,Entrance)],[dump(x) for x in rows(s,Alias)])
  run.result=result;run.state='ready'
  for d in result['candidates']:s.add(Candidate(run_id=run.id,**d))
  s.commit();return run.id,result
def qc():return client.get('/qc',headers=H['viewer']).json()['rounds']
def rnd(code):return [q for q in qc() if q['code']==code][0]
def pairset(code):return {(p['source']['id'],p['target']['id']) for p in rnd(code)['pairs']}
def vote(h,pid,verdict,note='对照门牌照片与地籍图书证复核判定'):return client.post(f'/qc/pairs/{pid}/votes',json={'verdict':verdict,'note':note},headers=H[h])

print('== 1 种子与匹配 ==')
with Session() as s:
 check('演示账号5个（含第三人核定员）',len(rows(s,User))==5)
 check('重复种子执行入口仍10个',len(rows(s,Entrance))==10)
r=client.post('/qc/rounds',json={'code':'QC-0','fraction':0.5,'seed':42},headers=H['supervisor'])
check('无就绪匹配不可创建抽查',r.status_code==409)
run1,res1=drain()
check('留出评估精确率召回率仍为1',res1['evaluation']['precision']==1 and res1['evaluation']['recall']==1)
rec={(c['source_id'],c['target_id']) for c in res1['candidates'] if not c['conflict']}
with Session() as s:
 es=rows(s,Entrance);by={e.id:e for e in es}
 frame=[(x,y) for i,x in enumerate(es) for y in es[i+1:] if x.street==y.street and x.number==y.number]
 check('同街同号框架7对（长桥路3/青石街3/河滨路1）',len(frame)==7 and sorted((x.street for x,_ in frame))==['河滨路','长桥路','长桥路','长桥路','青石街','青石街','青石街'])
 hb=[(x.id,y.id) for x,y in frame if x.street=='河滨路'][0]
 check('河滨路伍号老宅对未被推荐（漏合场景）',(min(hb),max(hb)) not in rec)
 check('长桥路18号正门-旧门牌对已推荐',any(by[a].code=='CQ-018-A' and by[b].code=='CQ-018-B' for a,b in rec))

print('== 2 抽样与冻结 ==')
r=client.post('/qc/rounds',json={'code':'QC-1','fraction':0.5,'seed':42},headers=H['supervisor'])
check('核定员创建抽查批次',r.status_code==200,r.text[:120])
q1=rnd('QC-1')
check('参照首批匹配并冻结',q1['run_id']==run1 and q1['state']=='collecting')
check('分层分母：长桥路已推荐3抽2、青石街已推荐3抽2、河滨路未推荐1抽1',q1['frame']=={'长桥路':{'recommended':{'population':3,'sampled':2}},'青石街':{'recommended':{'population':3,'sampled':2}},'河滨路':{'unrecommended':{'population':1,'sampled':1}}},json.dumps(q1['frame'],ensure_ascii=False))
with Session() as s:
 w=[p.weight for p in rows(s,QcPair) if p.round_id==q1['id']]
 check('抽样5对，权重=层总体/抽中数',len(w)==5 and sorted(set(w))==[1.0,1.5] and w.count(1.5)==4 and w.count(1.0)==1)
check('抽中门牌对均同街同号',all(p['street'] in ('长桥路','青石街','河滨路') for p in q1['pairs']))
check('盲审：待判定对不揭晓原分与推荐情况',all('similarity' not in p and 'recommended' not in p and 'votes' not in p for p in q1['pairs']))
r=client.post('/qc/rounds',json={'code':'QC-2','fraction':0.5,'seed':42},headers=H['supervisor'])
check('同种子同参数抽样可复现',pairset('QC-2')==pairset('QC-1'))
r=client.post('/qc/rounds',json={'code':'QC-X','fraction':0,'seed':1},headers=H['supervisor'])
check('抽样比例越界拒绝',r.status_code==422)
r=client.post('/qc/rounds',json={'code':'QC-3','fraction':0.5,'seed':42},headers=H['operator'])
check('采集员不可创建抽查',r.status_code==403)
r=client.post('/aliases',json={'entrance_id':1,'text':'长桥路18号正门传达室'},headers=H['operator'])
check('采集员增补别名',r.status_code==200,r.text[:120])
run2,_=drain()
q1b=rnd('QC-1')
check('重跑匹配不改换样本与分母',q1b['frame']==q1['frame'] and pairset('QC-1')=={(p['source']['id'],p['target']['id']) for p in q1['pairs']} and q1b['run_id']==run1 and run2!=run1)

print('== 3 盲审、交卷与裁决 ==')
pairs={p['id']:p for p in q1['pairs']}
p1,p2,p3,p4,p5=sorted(pairs)
check('待判定进度0/5',rnd('QC-1')['progress']['recommended']['pending']+rnd('QC-1')['progress']['unrecommended']['pending']==5)
r=vote('viewer',p1,'same');check('查阅员不可判定',r.status_code==403)
r=vote('operator',p1,'same');check('采集员不可判定',r.status_code==403)
r=vote('supervisor',p1,'same');check('核定员甲交卷',r.status_code==200,r.text[:120])
p=rnd('QC-1')['pairs']
p1j=[x for x in p if x['id']==p1][0]
check('一人交卷后仍盲审',p1j['state']=='pending' and p1j['vote_count']==1 and 'similarity' not in p1j)
r=vote('supervisor2',p1,'same');check('核定员乙交卷',r.status_code==200)
p1j=[x for x in rnd('QC-1')['pairs'] if x['id']==p1][0]
check('两人一致即判定并揭晓原分与推荐情况',p1j['state']=='decided' and p1j['verdict']=='same' and 'similarity' in p1j and 'recommended' in p1j and len(p1j['votes'])==2)
r=vote('supervisor3',p1,'different');check('已判定对不再接收判定',r.status_code==409)
r=vote('supervisor',p2,'different');check('第二对甲判异址',r.status_code==200)
r=vote('supervisor',p2,'different');check('甲重试同判定不重复计票',r.status_code==200 and [x for x in rnd('QC-1')['pairs'] if x['id']==p2][0]['vote_count']==1)
r=vote('supervisor',p2,'same');check('甲改判拒绝',r.status_code==409)
r=vote('supervisor2',p2,'same');check('乙判同址触发分歧',r.status_code==200)
p2j=[x for x in rnd('QC-1')['pairs'] if x['id']==p2][0]
check('分歧进入待裁决并揭晓',p2j['state']=='arbitration' and len(p2j['votes'])==2 and 'similarity' in p2j)
r=vote('supervisor',p2,'different');check('裁决中甲重试仍不重复计票',r.status_code==200 and len([x for x in rnd('QC-1')['pairs'] if x['id']==p2][0]['votes'])==2)
r=vote('supervisor2',p2,'different');check('已交卷者不可充当第三人',r.status_code==409)
r=vote('supervisor3',p2,'same');check('第三人裁决',r.status_code==200)
p2j=[x for x in rnd('QC-1')['pairs'] if x['id']==p2][0]
check('裁决后判定为第三人结论',p2j['state']=='decided' and p2j['verdict']=='same' and len(p2j['votes'])==3)

print('== 4 并发交卷 ==')
def svc_vote(email,pid,verdict):
 try:
  with Session() as s:qc_service.vote(s,pid,{'verdict':verdict,'note':'并发压测书证依据'}, {'email':email});s.commit();return 200
 except Exception as e:return getattr(e,'status_code',500)
def reset(pid):
 with Session() as s:s.query(QcVote).filter(QcVote.pair_id==pid).delete();s.query(QcPair).filter(QcPair.id==pid).update({'state':'pending','verdict':''});s.commit()
reset(p3)
results=[]
t1=threading.Thread(target=lambda:results.append(svc_vote('supervisor@changqiao.local',p3,'same')))
t2=threading.Thread(target=lambda:results.append(svc_vote('supervisor2@changqiao.local',p3,'different')))
t1.start();t2.start();t1.join();t2.join()
with Session() as s:n3=len([v for v in rows(s,QcVote) if v.pair_id==p3]);st=s.get(QcPair,p3).state
check('并发交卷两人各计一票',sorted(results)==[200,200] and n3==2 and st=='arbitration',f'results={results} votes={n3} state={st}')
reset(p4)
results=[]
ts=[threading.Thread(target=lambda:results.append(svc_vote('supervisor@changqiao.local',p4,'same'))) for _ in range(5)]
[t.start() for t in ts];[t.join() for t in ts]
with Session() as s:n4=len([v for v in rows(s,QcVote) if v.pair_id==p4])
check('同一核定员并发重试不重复计票',all(x==200 for x in results) and n4==1,f'results={results} votes={n4}')
reset(p3);reset(p4)

print('== 5 折算估计与封存 ==')
plan={p1:('same','same',None),p2:('different','same','same'),p3:('different','different',None),p4:('same','different','different'),p5:('same','same',None)}
with Session() as s:
 for pid,(va,vb,vc) in plan.items():
  s.query(QcVote).filter(QcVote.pair_id==pid).delete();s.query(QcPair).filter(QcPair.id==pid).update({'state':'pending','verdict':''})
  for email,verdict in [('supervisor@changqiao.local',va),('supervisor2@changqiao.local',vb)]+([('supervisor3@changqiao.local',vc)] if vc else []):
   qc_service.vote(s,pid,{'verdict':verdict,'note':'按计划书证判定'}, {'email':email})
 s.commit()
with Session() as s:
 qp={p.id:p for p in rows(s,QcPair) if p.round_id==s.get(QcPair,p1).round_id}
 decided={pid:p for pid,p in qp.items() if p.state=='decided'}
 exp={}
 for flag,key,ev in [(1,'wrong_merge','different'),(0,'unrecommended','same')]:
  sel=[p for p in decided.values() if p.recommended==flag]
  wsum=sum(p.weight for p in sel);werr=sum(p.weight for p in sel if p.verdict==ev)
  exp[key]=(round(werr/wsum,6) if wsum else None,round(werr,6))
est=rnd('QC-1')['estimates']
check('错合率按抽中机会折算',est['wrong_merge']['rate']==exp['wrong_merge'][0] and est['wrong_merge']['weighted_errors']==exp['wrong_merge'][1],json.dumps(est['wrong_merge']))
check('漏合率按抽中机会折算',est['missed_merge']['rate']==exp['unrecommended'][0] and est['missed_merge']['weighted_errors']==exp['unrecommended'][1],json.dumps(est['missed_merge']))
check('全部判完未判完为0',est['wrong_merge']['unfinished']==0 and est['missed_merge']['unfinished']==0)
est2=rnd('QC-2')['estimates']
check('未判完批次比率缺省且单列',est2['wrong_merge']['rate'] is None and est2['missed_merge']['rate'] is None and est2['wrong_merge']['unfinished']+est2['missed_merge']['unfinished']==5)
r=client.post('/qc/rounds/%s/close'%rnd('QC-1')['id'],headers=H['supervisor'])
check('封存批次',r.status_code==200)
r=vote('supervisor',p5,'same')
check('封存后不再接收判定',r.status_code==409)
check('审计留痕',any('质检' in a['action'] or '判定' in a['action'] for a in client.get('/audit',headers=H['viewer']).json()))

print('== 结果 ==')
print('FAIL:',FAIL if FAIL else '无')
sys.exit(1 if FAIL else 0)
