import argparse, json, math, time, csv
from pathlib import Path
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from turtlesim.msg import Pose
from turtlesim.srv import SetPen

ARRIVE=0.020
LIN_STOP=0.025
ANG_STOP=0.050
HOLD_SAMPLES=3

class Worker(Node):
    def __init__(self, strokes, robot):
        super().__init__('logo_stop_'+robot)
        self.robot=robot;self.strokes=strokes
        self.pose=None;self.pose_seq=0;self.last_pose_at=0.;self.done=False;self.failed=None
        self.pub=self.create_publisher(Twist, f'/{robot}/cmd_vel',10)
        self.sub=self.create_subscription(Pose, f'/{robot}/pose',self.pose_cb,10)
        self.pen=self.create_client(SetPen,f'/{robot}/set_pen')
        if not self.pen.wait_for_service(timeout_sec=10):raise RuntimeError(robot+' set_pen unavailable')
        self.idx=0;self.point=0;self.phase='initial_off';self.future=self.set_pen(True)
        self.t0=time.monotonic();self.phase_started=self.t0;self.hold_count=0;self.last_checked_seq=-1
        self.records=[];self.timer=self.create_timer(.05,self.tick)
    def pose_cb(self,p):
        self.pose=p;self.pose_seq+=1;self.last_pose_at=time.monotonic()
    def set_pen(self,off):
        q=SetPen.Request();q.r=0;q.g=0;q.b=0;q.width=2;q.off=int(off)
        return self.pen.call_async(q)
    def cmd(self,v=0.,w=0.):
        t=Twist();t.linear.x=float(v);t.angular.z=float(w);self.pub.publish(t)
    def stage(self,name):
        self.phase=name;self.phase_started=time.monotonic();self.hold_count=0;self.last_checked_seq=-1
    def goto(self,xy):
        p=self.pose
        dx=xy[0]-p.x;dy=xy[1]-p.y;d=math.hypot(dx,dy)
        if d < ARRIVE:
            self.cmd();return True
        a=math.atan2(dy,dx);e=math.atan2(math.sin(a-p.theta),math.cos(a-p.theta))
        self.cmd(0. if abs(e)>.23 else min(1.5,max(.12,1.75*d)),max(-3.,min(3.,5*e)))
        return False
    def stopped(self,target):
        self.cmd()
        if self.pose_seq==self.last_checked_seq:return False
        self.last_checked_seq=self.pose_seq
        p=self.pose;d=math.hypot(p.x-target[0],p.y-target[1])
        ok=d < ARRIVE and abs(p.linear_velocity)<LIN_STOP and abs(p.angular_velocity)<ANG_STOP
        self.hold_count=self.hold_count+1 if ok else 0
        if d >= ARRIVE:self.stage('travel' if self.phase=='start_settle' else 'end_correct')
        return self.hold_count>=HOLD_SAMPLES
    def capture(self,kind,target):
        p=self.pose
        self.records.append(dict(robot=self.robot,stroke_id=self.strokes[self.idx]['id'],event=kind,
            x=p.x,y=p.y,target_x=target[0],target_y=target[1],error=round(math.dist((p.x,p.y),target),6),
            linear_velocity=p.linear_velocity,angular_velocity=p.angular_velocity,elapsed=round(time.monotonic()-self.t0,3)))
    def tick(self):
        now=time.monotonic()
        if now-self.t0>2400:self.failed='global timeout';self.finish();return
        if self.pose is None:return
        if now-self.last_pose_at>2:self.failed='stale /pose for '+self.robot;self.finish();return
        if now-self.phase_started>90:self.failed='phase timeout: '+self.phase+' stroke '+str(self.idx);self.finish();return
        if self.phase in ('initial_off','pen_on','pen_off','last_off'):
            self.cmd()
            if not self.future.done():return
            if self.future.exception() is not None:self.failed='SetPen failed: '+str(self.future.exception());self.finish();return
            if self.phase=='initial_off':self.stage('travel')
            elif self.phase=='pen_on':self.point=1;self.stage('draw')
            elif self.phase=='pen_off':self.idx+=1;self.stage('travel')
            else:self.idx+=1;self.finish()
            return
        pts=self.strokes[self.idx]['points']
        if self.phase=='travel':
            if self.goto(pts[0]):self.stage('start_settle')
        elif self.phase=='start_settle':
            if self.stopped(pts[0]):
                self.capture('pen_down_request',pts[0]);self.future=self.set_pen(False);self.stage('pen_on')
        elif self.phase=='draw':
            if self.goto(pts[self.point]):
                self.point+=1
                if self.point==len(pts):self.stage('end_settle')
        elif self.phase=='end_correct':
            if self.goto(pts[-1]):self.stage('end_settle')
        elif self.phase=='end_settle':
            if self.stopped(pts[-1]):
                self.capture('pen_up_request',pts[-1]);self.future=self.set_pen(True)
                self.stage('last_off' if self.idx==len(self.strokes)-1 else 'pen_off')
                if (self.idx+1)%5==0 or self.idx+1==len(self.strokes):
                    self.get_logger().info(f'COMPLETED {self.idx+1}/{len(self.strokes)} elapsed={now-self.t0:.1f}s')
    def finish(self):
        self.cmd();self.done=True;self.timer.cancel()
        p=Path('/data/results/region_stop_verify');p.mkdir(parents=True,exist_ok=True)
        f=p/(self.robot+'.csv')
        with f.open('w',newline='') as h:
            w=csv.DictWriter(h,fieldnames=['robot','stroke_id','event','x','y','target_x','target_y','error','linear_velocity','angular_velocity','elapsed'])
            w.writeheader();w.writerows(self.records)
        self.get_logger().info(('DRAW PASS' if not self.failed else 'DRAW FAIL: '+self.failed)+f' logged={len(self.records)}')

def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--robot',required=True,choices=['turtle1','turtle2','turtle3']);a=p.parse_args()
    plan=json.loads(Path(a.plan).read_text());strokes=next(r['strokes'] for r in plan['assignments'] if r['turtle']==a.robot)
    if not strokes or len(strokes)>500:raise ValueError('bad stroke count')
    for s in strokes:
        if len(s['points'])<2:raise ValueError('one-point stroke')
        for xy in s['points']:
            if len(xy)!=2 or not all(isinstance(z,(float,int)) and math.isfinite(z) and .5<=z<=10.5 for z in xy):raise ValueError('invalid point')
    print('STOP VERIFY WORKER '+a.robot+' strokes='+str(len(strokes)),flush=True)
    rclpy.init();n=None
    try:
        n=Worker(strokes,a.robot)
        while rclpy.ok() and not n.done:rclpy.spin_once(n,timeout_sec=.1)
        if n.failed:raise RuntimeError(n.failed)
    finally:
        if n:n.cmd();n.destroy_node()
        if rclpy.ok():rclpy.shutdown()
if __name__=='__main__':main()
