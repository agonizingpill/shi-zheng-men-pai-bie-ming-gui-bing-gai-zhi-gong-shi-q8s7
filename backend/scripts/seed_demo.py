from src.database import Session,Base,engine
from src.models import *
from src.security import password_hash
from src.common import rows

def seed():
 Base.metadata.create_all(engine)
 with Session() as s:
  for name,role in [('operator','operator'),('supervisor','supervisor'),('supervisor2','supervisor'),('supervisor3','supervisor'),('viewer','viewer')]:
   if not any(x.email==name+'@changqiao.local' for x in rows(s,User)):s.add(User(email=name+'@changqiao.local',password=password_hash('Address2026!'),role=role))
  if not s.get(Registry,1):s.add(Registry(id=1,now='2026-11-18T09:00:00'))
  if not any(x.code=='CQ-018-A' for x in rows(s,Entrance)):
   for code,num,label,lat in [('CQ-018-A',18,'长桥路18号正门',31.210),('CQ-018-B',18,'长桥路十八号旧门牌',31.2101),('CQ-081',81,'长桥路81号',31.211),('CQ-018-C',18,'长桥路18号南入口',31.2102)]:
    e=Entrance(code=code,street='长桥路',number=num,label=label,lat=lat,lng=121.48);s.add(e);s.flush();a=Alias(entrance_id=e.id,text=label);s.add(a);s.flush();s.add(Evidence(alias_id=a.id,reference='照片-'+code,description='2026年11月现场门牌照片与老地籍图位置核验说明'))
   s.flush();es=rows(s,Entrance);p=Proposal(code='P031',source_id=es[1].id,target_id=es[0].id,reason='历史十八号门牌与现18号正门同宗同入口');s.add(p);s.flush();s.add(Objection(proposal_id=p.id,code='Y031',note='住户认为旧门牌对应独立南入口，申请现场复核',state='open'))
  extra=[('QS-007-A','青石街',7,'青石街7号正门',31.220,''),('QS-007-B','青石街',7,'青石街七号旧门牌',31.2201,''),('QS-007-C','青石街',7,'青石街7号西侧门',31.2202,''),('QS-009','青石街',9,'青石街9号',31.221,''),('HB-005-A','河滨路',5,'河滨路5号东门',31.230,''),('HB-005-B','河滨路',5,'临河伍号旧宅',31.2301,'地籍图载临河伍号旧宅即现河滨路5号院落，门牌照片核对老北门位置')]
  for code,street,num,label,lat,note in extra:
   if not any(x.code==code for x in rows(s,Entrance)):
    e=Entrance(code=code,street=street,number=num,label=label,lat=lat,lng=121.48);s.add(e);s.flush();a=Alias(entrance_id=e.id,text=label);s.add(a);s.flush();s.add(Evidence(alias_id=a.id,reference='照片-'+code,description=note or '2026年11月现场门牌照片与老地籍图位置核验说明'))
  s.commit()
if __name__=='__main__':seed()
