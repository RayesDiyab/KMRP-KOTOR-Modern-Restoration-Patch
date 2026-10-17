"""Independent native stack check for the local Ebon Hawk departure fixture.
Reads the actual emitted NCS; engine arguments are popped in declaration order,
as verified against shipped K1 scripts, independent of PyKotor's interpreter.
"""
from pathlib import Path
import logging,struct,runpy
logging.disable(logging.DEBUG)
from pykotor.resource.formats.ncs import read_ncs
from pykotor.resource.formats.rim import read_rim
from pykotor.resource.type import ResourceType as R
ROOT=Path(__file__).resolve().parents[2]

def execute(raw,available=(),entering=7,planet=2,final_choice=0):
 n=read_ncs(raw);indices={id(x):i for i,x in enumerate(n.instructions)}
 stack=[];returns=[];pc=0;trace=[];avail=set(available)
 def pop(kind):
  assert stack,'stack underflow'
  t,v=stack.pop();assert t==kind,(t,v,'expected',kind);return v
 def push(t,v):stack.append((t,v))
 for step in range(1000):
  x=n.instructions[pc];name=x.ins_type.name;a=x.args;nextpc=pc+1
  if name=='CONSTI':push('i',a[0]if a[0]<0x80000000 else a[0]-0x100000000)
  elif name=='CONSTS':push('s',a[0])
  elif name=='RSADDI':push('i',0)
  elif name=='ACTION':
   number,count=a
   if number in (25,548):assert count==0;push('o',entering if number==25 else 7)
   elif number==696:
    assert count==1;slot=pop('i');push('i',int(slot in avail))
   elif number==697:
    assert count==2;slot=pop('i');template=pop('s');avail.add(slot);trace.append(('add',slot,template));push('i',1)
   elif number==708:
    assert count==2;slot=pop('i');value=pop('i');trace.append(('selectable',slot,value))
   elif number==580:
    assert count==1;key=pop('s');assert key in ('K_CURRENT_PLANET','G_FinalChoice');push('i',planet if key=='K_CURRENT_PLANET'else final_choice)
   elif number==712:
    assert count==3;callback=pop('s');forced1=pop('i');forced2=pop('i');trace.append(('picker',callback,forced1,forced2))
   else:raise AssertionError(('unexpected action',number))
  elif name=='NOTI':push('i',int(not pop('i')))
  elif name=='MOVSP':
   assert a[0]<=0 and a[0]%4==0
   for i in range(-a[0]//4):stack.pop()
  elif name=='CPTOPSP':
   assert a[1]==4;stack.append(stack[len(stack)+a[0]//4])
  elif name=='CPDOWNSP':
   assert a[1]==4;stack[len(stack)+a[0]//4]=stack[-1]
  elif name in ('EQUALOO','NEQUALOO'):
   rhs=pop('o');lhs=pop('o');push('i',int(lhs==rhs)if name=='EQUALOO'else int(lhs!=rhs))
  elif name in ('EQUALII','GTII','LOGANDII'):
   rhs=pop('i');lhs=pop('i');push('i',int(lhs==rhs)if name=='EQUALII'else int(lhs>rhs)if name=='GTII'else int(bool(lhs)and bool(rhs)))
  elif name in ('JZ','JNZ'):
   cond=pop('i')
   if (cond==0)==(name=='JZ'):nextpc=indices[id(x.jump)]
  elif name=='JMP':nextpc=indices[id(x.jump)]
  elif name=='JSR':returns.append(nextpc);nextpc=indices[id(x.jump)]
  elif name=='RETN':
   if not returns:assert not stack,stack;return trace,avail
   nextpc=returns.pop()
  else:raise AssertionError(name)
  pc=nextpc
 raise AssertionError('script did not finish')

def main():
 root=ROOT/'build/party-roster-game'
 original=read_rim(root/'modules/ebo_m12aa_s.rim').get('k_pebn_leavhawk',R.NCS)
 fixed=(root/'Override/kmrt_leave.ncs').read_bytes()
 prefix=len(fixed)-len(original)
 assert fixed[13+prefix:]==original[13:]
 expected={8,9,15,16,31}
 trace,avail=execute(fixed)
 assert avail==expected
 assert {x[1]for x in trace if x[0]=='add'}==expected
 assert {x[1]for x in trace if x[0]=='selectable'and x[2]==1}==expected
 assert [x for x in trace if x[0]=='picker']==[('picker','k_pebn_exithawk',-1,-1)]
 for initial in (expected,{0,1,2,5,7,8}):
  trace,avail=execute(fixed,initial)
  assert {x[1]for x in trace if x[0]=='add'}==expected-set(initial)
  assert avail==expected|set(initial)
 assert execute(fixed,entering=99)[0]==[]
 assert not any(x[0]=='picker'for x in execute(fixed,planet=0)[0])
 assert [x for x in execute(fixed,planet=50,final_choice=1)[0]if x[0]=='picker']==[('picker','k_pebn_exithawk',0,-1)]
 broken=root/'fixture-broken-compiler-kmrt_leave.ncs'
 if broken.exists():
  try:execute(broken.read_bytes())
  except AssertionError as e:assert 'expected' in str(e) and "'i'" in str(e),e
  else:raise AssertionError('old compiler error was not reproduced')
 print('PASS: old compiler stack-order failure reproduced; corrected native calls balance; missing slots added; existing crew retained; original departure callback reached; NPC/planet guards retained.')
if __name__=='__main__':main()
