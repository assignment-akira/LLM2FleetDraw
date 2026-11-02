import argparse,json,subprocess,sys,time
from pathlib import Path
import rclpy
from rclpy.node import Node
from turtlesim.srv import Spawn

def main():
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);a=p.parse_args()
 doc=json.loads(Path(a.plan).read_text());assignments=doc['assignments'];names=[f'turtle{i}' for i in range(1,len(assignments)+1)]
 assert len(names) in (3,5) and [x['turtle'] for x in assignments]==names
 rclpy.init();node=Node('batch_fleet_setup');children=[];t=time.monotonic()
 try:
  client=node.create_client(Spawn,'/spawn')
  if not client.wait_for_service(timeout_sec=10):raise RuntimeError('/spawn unavailable')
  for j,name in enumerate(names[1:],1):
   req=Spawn.Request();req.name=name;req.x=float(5.5+.35*(j%2));req.y=float(5.5+.3*((j//2)%2));req.theta=0.
   fut=client.call_async(req);rclpy.spin_until_future_complete(node,fut,timeout_sec=10)
   if not fut.done() or fut.exception() or not fut.result() or fut.result().name!=name:raise RuntimeError('spawn failed '+name)
  for aitem in assignments:
   name=aitem['turtle']
   if not aitem['strokes']:continue
   proc=subprocess.Popen([sys.executable,'/workspace/one_turtle_logo/batch_partition/draw_fleet_stop.py','--plan',a.plan,'--robot',name]);children.append((name,proc))
  for name,proc in children:
   code=proc.wait(timeout=3600)
   print('FINISHED',name,'exit',code,flush=True)
   if code:raise RuntimeError('worker error '+name)
  print('DRAW BATCH PASS elapsed=',round(time.monotonic()-t,2),flush=True)
 finally:
  for _,proc in children:
   if proc.poll() is None:proc.terminate()
  node.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
